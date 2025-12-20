"""
water_flow.py

Water flow sensor driver using pigpio pulse timing.

This driver measures flow rate by counting GPIO pulses from a hall-effect
flow sensor and converting pulse frequency into litres per minute.
"""

# Operational notes:
# Make sure pigpiod is installed and running on the Pi:
#   sudo apt update
#   sudo apt install pigpio python3-pigpio
#   sudo systemctl enable pigpiod
#   sudo systemctl start pigpiod
#
#   sudo systemctl status pigpiod

import pigpio
import time
import collections
import threading
from typing import Tuple, Dict

from monitoring_service.sensors.gpio_sensor import GPIOSensor, GPIOValueError

class WaterFlowInitError(Exception):
    """
    Raised when the Water Flow sensor cannot be initialised.
    """
    pass

class WaterFlowValueError(Exception):
    """
    Raised when the Water Flow sensor is misconfigured or given invalid values.
    """
    pass

class WaterFlowReadError(Exception):
    """
    Raised when reading data from the Water Flow sensor fails.
    """
    pass

class WaterFlowStopError(Exception):
    """
    Raised when stopping the Water Flow sensor fails.
    """
    pass

class WaterFlowSensor(GPIOSensor):
    """
    GPIO-based water flow sensor using pigpio pulse callbacks.

    The sensor begins collecting pulses immediately on initialization and
    maintains a sliding window of recent ticks for rate calculation.

    Lifecycle:
        - pigpio is initialized during construction
        - A GPIO callback is registered automatically
        - read() blocks briefly to allow pulse accumulation
        - stop() should be called during shutdown to release pigpio resources
    """
    # Factory uses these for validation + filtering.
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
        identity: str | None = None,
        pin: int | None = None,
        sample_window: float | None = 1.0,
        sliding_window_s: float | None = 3.0,
        glitch_us: int | None = 200,
        calibration_constant: float | None = 4.5,
        kind: str = "Flow",
        units: str = "l/min",
    ):
        self.sensor_name = "WaterFlow"
        self.sensor_kind = kind
        self.sensor_units = units

        self.sensor_id: str | None = identity
        self.pin: int | None = pin

        self.sample_window: float = float(sample_window) if sample_window is not None else 1.0
        self.sliding_window_s: float = float(sliding_window_s) if sliding_window_s is not None else 3.0
        self.glitch_us: int = int(glitch_us) if glitch_us is not None else 200
        self.calibration_constant: float = float(calibration_constant) if calibration_constant is not None else 4.5

        self.sensor: pigpio.pi | None = None
        self._callback = None
        self.ticks = collections.deque()
        self.ticks_lock = threading.Lock()

        self.id = self.sensor_id

        self._check_pin()
        self._init_pigpio()
        self._configure_pigpio()
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
        """
        Create a pigpio connection and verify that pigpiod is available.
        """
        try:
            self.sensor = pigpio.pi()
        except Exception as e:
            raise WaterFlowInitError(f"Error creating pigpio instance: {e}") from e

        if not getattr(self.sensor, "connected", False):
            raise WaterFlowInitError("Unable to connect to pigpiod. Is the pigpiod daemon running?")

    def _configure_pigpio(self) -> None:
        """
        Configure pin and glitch filter once at startup.
        """
        try:
            if self.sensor is None:
                raise WaterFlowInitError("pigpio not initialized")
            self.sensor.set_mode(self.pin, pigpio.INPUT)
            self.sensor.set_pull_up_down(self.pin, pigpio.PUD_UP)
            self.sensor.set_glitch_filter(self.pin, int(self.glitch_us))
        except Exception as e:
            raise WaterFlowInitError(f"Error configuring pigpio: {e}") from e

    def start(self) -> None:
        """
        Register a pigpio callback and begin collecting pulse ticks.

        This method is idempotent. Once started, pulse collection continues in
        the background until stop() is called.
        """
        if self.sensor is None:
            self._init_pigpio()
            self._configure_pigpio()

        if self._callback is None:
            self._callback = self.sensor.callback(self.pin, pigpio.FALLING_EDGE, self._call_back)

    def stop(self) -> None:
        """
        Cancel callback and stop pigpio connection. Safe to call multiple times.
        """
        try:
            if self._callback is not None:
                try:
                    self._callback.cancel()
                except Exception as e:
                    raise WaterFlowStopError(f"Error cancelling callback: {e}") from e
                self._callback = None
            if self.sensor is not None:
                try:
                    self.sensor.stop()
                except Exception as e:
                    raise WaterFlowStopError(f"Error stopping pigpio: {e}") from e
                self.sensor = None
        except Exception as e:
            raise WaterFlowStopError(f"Error stopping: {e}") from e

    def _call_back(self, gpio: int, level: int, tick: int) -> None:
        """
        Callback handler for GPIO falling edges.

        Appends the tick timestamp and trims entries outside the sliding window.
        level == 0 indicates a falling edge.
        """
        if level != 0:
            return
        with self.ticks_lock:
            self.ticks.append(tick)
            cutoff_us = int(self.sliding_window_s * 1_000_000)
            while self.ticks and pigpio.tickDiff(self.ticks[0], tick) > cutoff_us:
                self.ticks.popleft()

    def _get_instant_and_smoothed(self) -> Tuple[float, float]:
        """
        Compute and return (flow_instant_l_min, flow_smoothed_l_min).

        Old ticks are trimmed during read-time calculations.
        Uses pigpio.tickDiff to handle wraparound safely.
        """

        if self.sensor is None:
            raise WaterFlowReadError("pigpio not initialized")

        now = self.sensor.get_current_tick()

        with self.ticks_lock:
            cutoff_us = int(self.sliding_window_s * 1_000_000)
            while self.ticks and pigpio.tickDiff(self.ticks[0], now) > cutoff_us:
                self.ticks.popleft()

            n = len(self.ticks)
            if n < 2:
                return 0.0, 0.0

            first = self.ticks[0]
            last = self.ticks[-1]
            total_time_us = pigpio.tickDiff(first, last)
            if total_time_us <= 0:
                return 0.0, 0.0

            pulses_per_sec = (n - 1) / (total_time_us / 1_000_000)

            last_two_dt = pigpio.tickDiff(self.ticks[-2], self.ticks[-1])
            if last_two_dt > 0:
                inst_freq = 1_000_000 / last_two_dt
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

        self.start()

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
        self.stop()
