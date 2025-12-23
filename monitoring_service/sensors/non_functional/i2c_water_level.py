"""
i2c_water_level.py

Provides an I2C-based water level sensor driver.
"""


from monitoring_service.sensors.base import BaseSensor
from smbus3 import SMBus, i2c_msg

class WaterLevelInitError(Exception):
    """
    Raised when the water level sensor fails during initialization.
    """
    pass

class WaterLevelValueError(Exception):
    """
    Raised when the water level sensor is misconfigured or given invalid values.
    """
    pass

class WaterLevelReadError(Exception):
    """
    Raised when reading data from the water level sensor fails.
    """
    pass

class I2CWaterLevelSensor(BaseSensor):
    """
    I2C-based water level sensor driver.

    Reads raw section data from paired I2C addresses and derives a relative
    water level measurement.
    """
    REQUIRED_KWARGS = ["id", "bus", "low_address", "high_address"]
    ACCEPTED_KWARGS = ["id", "bus", "low_address", "high_address"]
    COERCERS = {"bus": int, "low_address": int, "high_address": int}

    def __init__(self, *, id: str,
                 bus: int | str,
                 low_address: int | str,
                 high_address: int | str,
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
            # keep this check conservative; adjust if you support other adapters
            raise WaterLevelInitError(f"I2C bus {coerced_bus} out of allowed range 0..3")

        self.bus = coerced_bus

        # --- address coercion helper ---
        def _coerce_addr(val, name):
            if isinstance(val, int):
                coerced = val
            elif isinstance(val, str):
                try:
                    coerced = int(val, 0)
                except (ValueError, TypeError) as e:
                    raise WaterLevelInitError(f"Invalid I2C address string for {name}: {val}") from e
            else:
                raise WaterLevelInitError(f"Unsupported type for I2C address {name}: {type(val).__name__}")

            # quick sanity, allow values that may be 7-bit or 8-bit notation;
            # exact resolution/probing happens in _check_address
            if not (0x01 <= coerced <= 0x7F):
                raise WaterLevelInitError(f"I2C address {hex(coerced)} for {name} out of 7-bit range 0x01–0x7F")
            return coerced

        self.low_address = _coerce_addr(low_address, "low_address")
        self.high_address = _coerce_addr(high_address, "high_address")

        self.consecutive_failures = 0
        self.last_success_ts = None

        # open bus and resolve address variants
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
        """
        Open /dev/i2c-{bus} and keep the handle for reuse.
        """
        try:
            self._smbus = SMBus(self.bus)
        except FileNotFoundError as e:
            raise WaterLevelInitError(f"I2C bus {self.bus} not found (no /dev/i2c-{self.bus})") from e
        except PermissionError as e:
            raise WaterLevelInitError(f"Permission denied opening I2C bus {self.bus}") from e
        except OSError as e:
            raise WaterLevelInitError(f"Failed to open I2C bus {self.bus}: {e}") from e

    def _probe_pair(self, low: int, high: int) -> bool:
        """
        Return True if both addresses respond to a 1-byte probe read.
        """
        try:
            self._smbus.i2c_rdwr(i2c_msg.read(low, 1))
            self._smbus.i2c_rdwr(i2c_msg.read(high, 1))
            return True
        except Exception:
            return False

    def _check_address(self):
        """
        Validate/resolve the configured low/high addresses.

        Behaviour:
        - First try the provided addresses as-is (likely 7-bit).
        - If that fails, try the right-shifted variants (handles Arduino 8-bit notation).
        - If that fails, try a small set of common fallback pairs.
        - Sets self.addr_low and self.addr_high to the working 7-bit addresses.
        """
        if not getattr(self, "_smbus", None):
            raise WaterLevelInitError("I2C bus not open before checking address")

        candidates = []

        # prefer user-provided pair first
        candidates.append((self.low_address, self.high_address))

        # try interpreting provided values as 8-bit (shift right)
        try:
            candidates.append((self.low_address >> 1, self.high_address >> 1))
        except Exception:
            pass

        # common known 7-bit pairs for this module (7-bit equivalents of Arduino sample)
        candidates.extend([
            (0x3B, 0x3C),  # common for some Grove modules
            (0x3C, 0x3D),
        ])

        tried = []
        for low, high in candidates:
            # normalize to int and ensure in 7-bit range
            try:
                low_i = int(low) & 0x7F
                high_i = int(high) & 0x7F
            except Exception:
                continue

            tried.append((low_i, high_i))
            if self._probe_pair(low_i, high_i):
                self.addr_low = low_i
                self.addr_high = high_i
                return

        # if none responded, raise including attempted candidates for debugging
        raise WaterLevelInitError(f"Could not contact water-level device on bus {self.bus}. Tried: {tried}")

    # --- Reading -----------------------------------------------------------

    def _collect_raw(self) -> dict:
        """
        Read raw I2C bytes and derive a relative water level in millimetres.

        Validates returned data and raises WaterLevelReadError on malformed/truncated reads.
        """
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
            raise WaterLevelReadError(
                f"I2C read failed from {hex(getattr(self, 'addr_low', 0))}/{hex(getattr(self, 'addr_high', 0))}: {e}"
            ) from e

        sections = low_data + high_data  # expected 20 items

        # Validate length
        if len(sections) != 20:
            raise WaterLevelReadError(
                f"Truncated I2C read: expected 20 bytes, got {len(sections)} (low={len(low_data)}, high={len(high_data)})"
            )

        # Validate types and ranges for each byte
        for i, v in enumerate(sections):
            if not isinstance(v, int):
                raise WaterLevelReadError(
                    f"Malformed I2C byte at section {i}: expected int 0..255, got {type(v).__name__}")
            if not (0 <= v <= 0xFF):
                raise WaterLevelReadError(f"I2C byte out of range at section {i}: {v}")

        # Arduino example threshold
        THRESHOLD = 100
        touch_val = 0
        for i, val in enumerate(sections):
            if val > THRESHOLD:
                touch_val |= (1 << i)

        # Count consecutive triggered sections from the bottom (LSB)
        trig_sections = 0
        tmp_val = touch_val
        while tmp_val & 0x01:
            trig_sections += 1
            tmp_val >>= 1

        # Convert to millimetres; default 20 sections => 100 mm total => 5 mm/section
        mm_per_section = 5.0
        level_mm = trig_sections * mm_per_section

        return {
            "raw_bytes_low": low_data,
            "raw_bytes_high": high_data,
            "sections_triggered": trig_sections,
            "level_mm": level_mm
        }

    def read(self) -> dict:
        """
        Return the current water level reading as a canonical mapping {'water_level': <float mm>}.
        """
        raw = self._collect_raw()
        return {"water_level": raw["level_mm"]}

    def _shutdown(self):
        """
        Close the I2C bus handle if open.
        """
        try:
            if getattr(self, "_smbus", None):
                self._smbus.close()
        except Exception:
            pass
        finally:
            self._smbus = None
