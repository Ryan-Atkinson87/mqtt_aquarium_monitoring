# i2c_water_level.py

from monitoring_service.sensors.base import BaseSensor
from smbus3 import SMBus, i2c_msg

class WaterLevelInitError(Exception):
    pass

class WaterLevelValueError(Exception):
    pass

class WaterLevelReadError(Exception):
    pass

class I2CWaterLevelSensor(BaseSensor):
    REQUIRED_KWARGS = ["id", "bus", "address"]
    ACCEPTED_KWARGS = ["id", "bus", "address"]
    COERCERS = {"bus": int, "address": int}
    def __init__(self, *, id: str | None = None,
                 bus: int | None = None,
                 address: int | None = None,
                 kind: str = "WaterLevel",
                 units: str = "mm"):
        self.sensor = None
        self.sensor_name = "GroveWaterLevel"
        self.sensor_kind = kind
        self.sensor_units = units

        self.sensor_id: str | None = id

        if isinstance(bus, int):
            pass
        elif isinstance(bus, str):
            try:
                bus = int(bus, 0)
            except ValueError as e:
                raise ValueError(f"Invalid I2C bus string: {bus}") from e
        else:
            raise TypeError(f"Unsupported type for I2C bus: {type(bus).__name__}")
        self.bus: int | None = bus

        if isinstance(address, int):
            pass
        elif isinstance(address, str):
            try:
                address = int(address, 0)  # <— smart trick
            except ValueError as e:
                raise WaterLevelInitError(f"Invalid I2C address string: {address}") from e
        else:
            raise WaterLevelInitError(f"Unsupported type for I2C address: {type(address).__name__}")

        if not (0x03 <= address <= 0x77):
            raise WaterLevelInitError(f"I2C address {hex(address)} out of range 0x03–0x77")

        self.address = address
        self.id = self.sensor_id
        self.consecutive_failures = 0
        self.last_success_ts = None

        self._check_bus()
        self._check_address()

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

    def _check_bus(self):
        try:
            self._smbus = SMBus(self.bus)
        except FileNotFoundError as e:
            raise WaterLevelInitError(f"I2C bus {self.bus} not found (no /dev/i2c-{self.bus})") from e
        except PermissionError as e:
            raise WaterLevelInitError(f"Permission denied opening I2C bus {self.bus}") from e
        except OSError as e:
            raise WaterLevelInitError(f"Failed to open I2C bus {self.bus}: {e}") from e

    def _resolve_addresses(self):
        candidates = []

        if getattr(self, "address", None) is not None:
            a = int(self.address)
            candidates.append((a, a + 1))
            if a > 0x7:
                a7 = a >> 1
                candidates.append((a7, a7 + 1))
            candidates.append((0x3B, 0x3C))

        candidates.extend([
            (0x3B, 0x3C),
            (0x3C, 0x3D),
            (0x1E, 0x1F),
        ])

        for low, high in candidates:
            try:
                self._smbus.i2c_rdwr(i2c_msg.read(low, 1))
                self._smbus.i2c_rdwr(i2c_msg.read(high, 1))
                self.addr_low = low
                self.addr_high = high
                return
            except Exception:
                continue

        raise WaterLevelInitError(f"Could not detect water-level device on bus {self.bus}. "
                                  f"Tried address pairs: {candidates!r}")

    def _check_address(self):
        if not getattr(self, "_smbus", None):
            raise WaterLevelInitError("I2C bus not open before checking address")

        self._resolve_addresses()

    def _collect_raw(self) -> dict:
        if not getattr(self, "_smbus", None):
            self._smbus = SMBus(self.bus)

        if not hasattr(self, "addr_low") or not hasattr(self, "addr_high"):
            raise WaterLevelReadError("Sensor addresses not resolved; call _check_address() first")

        try:
            low_msg = i2c_msg.read(self.addr_low, 8)
            high_msg = i2c_msg.read(self.addr_high, 12)
            self._smbus.i2c_rdwr(low_msg)
            self._smbus.i2c_rdwr(high_msg)
            low_data = list(low_msg)
            high_data = list(high_msg)
        except Exception as e:
            raise WaterLevelReadError(f"I2C read failed from {hex(self.addr_low)}/{hex(self.addr_high)}: {e}") from e

        sections = low_data + high_data

        THRESHOLD = 100
        touch_val = 0
        for i, val in enumerate(sections):
            if val > THRESHOLD:
                touch_val |= (1 << i)

        trig_sections = 0
        tmp_val = touch_val
        while tmp_val & 0x01:
            trig_sections += 1
            tmp_val >>= 1

        mm_per_section = 5.0
        level_mm = trig_sections * mm_per_section

        return {
            "raw_bytes_low": low_data,
            "raw_bytes_high": high_data,
            "sections_triggered": trig_sections,
            "level_mm": level_mm
        }

    def read(self) -> dict:
        raw = self._collect_raw()
        return {"water_level": raw["level_mm"]}

    def _shutdown(self):
        try:
            if getattr(self, "_smbus", None):
                self._smbus.close()
        except Exception:
            pass
        finally:
            self._smbus = None
