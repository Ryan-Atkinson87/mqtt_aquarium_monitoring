# monitoring_service/sensors/water_flow.py
"""
Make sure pigpiod is installed and running on the pi:
sudo apt update
sudo apt install pigpio python3-pigpio
sudo systemctl enable pigpiod
sudo systemctl start pigpiod

sudo systemctl status pigpiod
"""
import pigpio
import time
import collections
import threading
from typing import Tuple, Dict

from monitoring_service.sensors.gpio_sensor import GPIOSensor, GPIOValueError

class WaterFlowInitError(Exception):
    pass

class WaterFlowValueError(Exception):
    pass

class WaterFlowReadError(Exception):
    pass

class WaterFlowSensor(GPIOSensor):
    REQUIRED_KWARGS = ["id", "pin"]
    ACCEPTED_KWARGS = [
        "id",
        "pin",
        "sample_window",
        "sliding_window_s",
        "glitch_us",
        "calibration_constant",
    ]
    COERCERS = {"pin": int}

    def __init__(
        self,
        *,
        id: str | None = None,
        pin: int | None = None,
        sample_window: float | None = 1.0,
        sliding_window_s: float | None = 3.0,
        glitch_us: int | None = 200,
        calibration_constant: float | None = 4.5,
        kind: str = "Flow",
        units: str = "l/min",
    ):
        # metadata
        self.sensor_name = "WaterFlow"
        self.sensor_kind = kind
        self.sensor_units = units

        # configuration
        self.sensor_id: str | None = id
        self.pin: int | None = pin
        # ensure numeric types
        self.sample_window: float = float(sample_window) if sample_window is not None else 1.0
        self.sliding_window_s: float = float(sliding_window_s) if sliding_window_s is not None else 3.0
        self.glitch_us: int = int(glitch_us) if glitch_us is not None else 200
        self.calibration_constant: float = float(calibration_constant) if calibration_constant is not None else 4.5

        # runtime fields
        self.sensor: pigpio.pi | None = None  # pigpio connection (kept open)
        self._cb = None                         # callback handle
        self.ticks = collections.deque()        # store pigpio ticks (µs)
        self.ticks_lock = threading.Lock()

        # id convenience
        self.id = self.sensor_id

        # validate and initialise
        self._check_pin()
        self._init_pigpio()
        self._configure_pigpio()
        # start collecting immediately; if you prefer to control lifecycle call start() yourself
        self.start()

    # --- Properties ---------------------------------------------------------
    @property
    def name(self) -> str:
        return self.sensor_name

    @property
    def kind(self) -> str:
        return self.sensor_kind

    @property
    def units(self) -> str:
        return self.sensor_units

    # --- Internals ----------------------------------------------------------
    def _check_pin(self) -> None:
        """
        Use the generic GPIO check but re-raise as driver-specific exception
        so tests and callers see WaterFlowValueError.
        """
        try:
            super()._check_pin()
        except GPIOValueError as e:
            raise WaterFlowValueError(str(e)) from e

    def _init_pigpio(self) -> None:
        """Create persistent pigpio connection and verify it's connected."""
        try:
            self.sensor = pigpio.pi()
        except Exception as e:
            raise WaterFlowInitError(f"Error creating pigpio instance: {e}") from e

        if not getattr(self.sensor, "connected", False):
            # ensure we raise a clear init error if pigpiod not available
            raise WaterFlowInitError("Unable to connect to pigpiod. Is the pigpiod daemon running?")

    def _configure_pigpio(self) -> None:
        """Configure pin and glitch filter once at startup."""
        try:
            if self.sensor is None:
                raise WaterFlowInitError("pigpio not initialized")
            self.sensor.set_mode(self.pin, pigpio.INPUT)
            self.sensor.set_pull_up_down(self.pin, pigpio.PUD_UP)
            # set_glitch_filter is the correct API for microsecond-level filtering
            self.sensor.set_glitch_filter(self.pin, int(self.glitch_us))
        except Exception as e:
            raise WaterFlowInitError(f"Error configuring pigpio: {e}") from e

    def start(self) -> None:
        """Register callback and begin collecting ticks. Safe to call multiple times."""
        if self.sensor is None:
            self._init_pigpio()
            self._configure_pigpio()

        if self._cb is None:
            # register callback on falling edge; callback keeps work tiny
            self._cb = self.sensor.callback(self.pin, pigpio.FALLING_EDGE, self._call_back)

    def stop(self) -> None:
        """Cancel callback and stop pigpio connection. Safe to call multiple times."""
        try:
            if self._cb is not None:
                try:
                    self._cb.cancel()
                except Exception:
                    pass
                self._cb = None
            if self.sensor is not None:
                try:
                    self.sensor.stop()
                except Exception:
                    pass
                self.sensor = None
        except Exception:
            # stop should not raise to callers
            pass

    def _call_back(self, gpio: int, level: int, tick: int) -> None:
        """
        Minimal work in callback: append tick and trim old entries.
        level==0 indicates the falling edge (we registered for falling).
        """
        if level != 0:
            return
        with self.ticks_lock:
            self.ticks.append(tick)
            # trim older ticks outside sliding window
            cutoff_us = int(self.sliding_window_s * 1_000_000)
            while self.ticks and pigpio.tickDiff(self.ticks[0], tick) > cutoff_us:
                self.ticks.popleft()

    def _get_instant_and_smoothed(self) -> Tuple[float, float]:
        """
        Compute and return (flow_instant_l_min, flow_smoothed_l_min).
        Uses pigpio.tickDiff to handle wraparound safely.
        """
        if self.sensor is None:
            raise WaterFlowReadError("pigpio not initialized")

        with self.ticks_lock:
            n = len(self.ticks)
            if n < 2:
                return 0.0, 0.0
            first = self.ticks[0]
            last = self.ticks[-1]
            total_time_us = pigpio.tickDiff(first, last)
            if total_time_us <= 0:
                return 0.0, 0.0

            pulses_per_sec = (n - 1) / (total_time_us / 1_000_000)

            # high-resolution instant freq from last two ticks if available
            if n >= 2:
                last_two_dt = pigpio.tickDiff(self.ticks[-2], self.ticks[-1])
                if last_two_dt > 0:
                    inst_freq = 1_000_000 / last_two_dt
                else:
                    inst_freq = pulses_per_sec
            else:
                inst_freq = pulses_per_sec

            flow_smoothed = pulses_per_sec / float(self.calibration_constant)
            flow_instant = inst_freq / float(self.calibration_constant)
            return float(flow_instant), float(flow_smoothed)

    # --- Public read() -----------------------------------------------------
    def read(self) -> Dict[str, float]:
        """
        Ensure callback is running, allow sample_window seconds for accumulation,
        compute rates from the collected ticks, and return canonical keys.

        Note: this does not stop pigpio nor cancel the callback. Call stop()
        when shutting down the driver.
        """
        if self.sensor is None:
            raise WaterFlowReadError("pigpio not initialized")

        # ensure callback running (idempotent)
        self.start()

        # allow pulses to accumulate for sample_window seconds
        # this keeps compatibility with your previous blocking read behaviour
        time.sleep(float(self.sample_window))

        try:
            flow_instant, flow_smoothed = self._get_instant_and_smoothed()
            return {
                "flow_instant": flow_instant,
                "flow_smoothed": flow_smoothed,
            }
        except Exception as e:
            raise WaterFlowReadError(f"Error reading flow: {e}") from e

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass
