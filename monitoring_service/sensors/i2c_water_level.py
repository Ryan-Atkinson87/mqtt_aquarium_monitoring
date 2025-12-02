from monitoring_service.sensors.base import BaseSensor
from smbus3 import SMBus, i2c_msg

class WaterLevelInitError(Exception):
    pass

class WaterLevelValueError(Exception):
    pass

class WaterLevelReadError(Exception):
    pass

class I2CWaterLevelSensor(BaseSensor):
    # *** CHANGED *** removed high_address from required fields
    REQUIRED_KWARGS = ["id", "bus", "low_address"]
    ACCEPTED_KWARGS = ["id", "bus", "low_address", "high_address"]
    COERCERS = {"bus": int, "low_address": int, "high_address": int}

    def __init__(self, *, id: str,
                 bus: int | str,
                 low_address: int | str,
                 high_address: int | str | None = None,   # *** CHANGED ***
                 kind: str = "WaterLevel",
                 units: str = "mm"):
        self.sensor = None
        self.sensor_name = "GroveWaterLevel"
        self.sensor_kind = kind
        self.sensor_units = units

        self.sensor_id = id
        self.id = id

        # --- bus coercion ---
        if isinstance(bus, int):
            coerced_bus = bus
        elif isinstance(bus, str):
            try:
                coerced_bus = int(bus, 0)
            except (ValueError, TypeError) as e:
                raise WaterLevelInitError(f"Invalid I2C bus string: {bus}") from e
        else:
            raise WaterLevelInitError(f"Unsupported type for I2C bus: {type(bus).__name__}")

        if not (0 <= coerced_bus <= 3):
            raise WaterLevelInitError(f"I2C bus {coerced_bus} out of allowed range 0..3")

        self.bus = coerced_bus

        # --- address coercion helper ---
        def _coerce_addr(val, name):
            if val is None:
                return None   # *** CHANGED ***
            if isinstance(val, int):
                coerced = val
            elif isinstance(val, str):
                try:
                    coerced = int(val, 0)
                except (ValueError, TypeError) as e:
                    raise WaterLevelInitError(f"Invalid I2C address string for {name}: {val}") from e
            else:
                raise WaterLevelInitError(f"Unsupported type for I2C address {name}: {type(val).__name__}")

            if not (0x01 <= coerced <= 0x7F):
                raise WaterLevelInitError(f"I2C address {hex(coerced)} for {name} out of 7-bit range 0x01–0x7F")
            return coerced

        self.low_address = _coerce_addr(low_address, "low_address")

        # *** CHANGED *** allow high_address to be None
        self.high_address = _coerce_addr(high_address, "high_address") if high_address is not None else None

        self.consecutive_failures = 0
        self.last_success_ts = None

        # open bus and resolve address
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

    # --- Bus / Address helpers ---------------------------------------------

    def _check_bus(self):
        try:
            self._smbus = SMBus(self.bus)
        except FileNotFoundError as e:
            raise WaterLevelInitError(f"I2C bus {self.bus} not found (no /dev/i2c-{self.bus})") from e
        except PermissionError as e:
            raise WaterLevelInitError(f"Permission denied opening I2C bus {self.bus}") from e
        except OSError as e:
            raise WaterLevelInitError(f"Failed to open I2C bus {self.bus}: {e}") from e

    def _check_address(self):
        """
        *** CHANGED ***
        v1.0 Grove Water Level uses ONE address (0x77).
        Ignore high_address and only probe low_address.
        """
        if not getattr(self, "_smbus", None):
            raise WaterLevelInitError("I2C bus not open before checking address")

        candidates = []

        # user-provided low_address
        candidates.append(self.low_address)

        # right-shift variant if user gave 8-bit
        try:
            candidates.append(self.low_address >> 1)
        except Exception:
            pass

        # fallback known address for v1.0: 0x77
        candidates.append(0x77)

        tried = []
        for addr in candidates:
            try:
                addr_i = int(addr) & 0x7F
            except Exception:
                continue

            tried.append(addr_i)

            # probe single address
            try:
                self._smbus.i2c_rdwr(i2c_msg.read(addr_i, 1))
                self.addr = addr_i     # *** CHANGED ***
                return
            except Exception:
                continue

        raise WaterLevelInitError(f"Could not contact water-level device on bus {self.bus}. Tried: {tried}")

    # --- Reading -----------------------------------------------------------

    def _collect_raw(self) -> dict:
        """
        *** CHANGED ***
        v1.0 Grove Water Level returns 20 bytes from ONE I2C address.
        First 8 bytes = low block
        Next 12 bytes = high block
        """
        if not getattr(self, "_smbus", None):
            self._smbus = SMBus(self.bus)

        if not hasattr(self, "addr"):
            raise WaterLevelReadError("Sensor address not resolved; call _check_address() first")

        try:
            msg = i2c_msg.read(self.addr, 20)          # *** CHANGED ***
            self._smbus.i2c_rdwr(msg)
            data = list(msg)
        except Exception as e:
            raise WaterLevelReadError(
                f"I2C read failed from {hex(getattr(self, 'addr', 0))}: {e}"
            ) from e

        if len(data) != 20:
            raise WaterLevelReadError(
                f"Truncated I2C read: expected 20 bytes, got {len(data)}"
            )

        # split like before (unchanged)
        low_data = data[:8]
        high_data = data[8:]

        for i, v in enumerate(data):
            if not isinstance(v, int) or not (0 <= v <= 255):
                raise WaterLevelReadError(f"Malformed I2C byte at index {i}: {v}")

        THRESHOLD = 100
        touch_val = 0
        for i, val in enumerate(data):
            if val > THRESHOLD:
                touch_val |= (1 << i)

        trig_sections = 0
        tmp = touch_val
        while tmp & 0x01:
            trig_sections += 1
            tmp >>= 1

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
