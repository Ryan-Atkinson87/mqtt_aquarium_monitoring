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
        """Detect the I2C address for the V1.0 Grove Water Level Sensor."""
        bus = SMBus(self.bus)

        # V1.0 sensor only responds at 0x77
        possible = [0x77]

        for addr in possible:
            try:
                bus.read_byte(addr)  # probe
                self.addr_low = addr
                bus.close()
                return
            except Exception:
                continue

            bus.close()
            raise WaterLevelReadError("No Grove Water Level sensor detected at address 0x77")


    # --- Reading -----------------------------------------------------------

    def _collect_raw(self) -> dict:
        """Read 8 bytes from the V1.0 Grove Water Level Sensor."""

        if not getattr(self, "_smbus", None):
            self._smbus = SMBus(self.bus)

        if not hasattr(self, "addr_low"):
            raise WaterLevelReadError("Address not initialised; call _check_address() first")

        try:
            msg = i2c_msg.read(self.addr_low, 8)
            self._smbus.i2c_rdwr(msg)
            data = list(msg)
        except Exception as e:
            raise WaterLevelReadError(
                f"I2C read failed from {hex(self.addr_low)}: {e}"
            ) from e

        print("DEBUG RAW:", data)  # VERY IMPORTANT for tuning

        # Observed in your earlier logs:
        # Dry pads ≈ 230–255
        # Wet pads ≈ 3–120
        DRY_THRESHOLD = 180  # will tune based on your output

        wet = [v < DRY_THRESHOLD for v in data]

        # Count contiguous wet pads from bottom
        triggered = 0
        for w in wet:
            if w:
                triggered += 1
            else:
                break

        # V1.0 has 8 pads → ~100 mm → ~12.5mm per pad
        mm_per_section = 12.5
        level_mm = triggered * mm_per_section

        return {
            "raw_bytes": data,
            "sections_triggered": triggered,
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
