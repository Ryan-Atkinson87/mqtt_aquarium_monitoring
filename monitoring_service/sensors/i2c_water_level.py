from monitoring_service.sensors.base import BaseSensor
from smbus3 import SMBus
from typing import List

class WaterLevelInitError(Exception):
    pass

class WaterLevelValueError(Exception):
    pass

class WaterLevelReadError(Exception):
    pass

class I2CWaterLevelSensor(BaseSensor):
    """
    Updated I2C driver for the Grove-style water level ladder.
    Reads 9 bytes from a single I2C address (first 8 = pads).
    Interprets pad bytes into a percent (0.0..100.0).

    Behaviour:
    - Configurable thresholds (wet_threshold, dry_threshold) via driver config
    - Spike correction and neighbour-resolution for transition bytes
    - No logging in driver; raises domain exceptions
    """

    REQUIRED_KWARGS = ["id", "bus", "low_address"]
    ACCEPTED_KWARGS = ["id", "bus", "low_address", "high_address",
                       "wet_threshold", "dry_threshold"]
    COERCERS = {"bus": int, "low_address": int, "high_address": int,
                "wet_threshold": int, "dry_threshold": int}

    NUM_PADS = 8
    DEFAULT_WET_THRESHOLD = 120    # <= this -> wet
    DEFAULT_DRY_THRESHOLD = 200    # >= this -> dry

    def __init__(
        self,
        *,
        id: str,
        bus: int | str,
        low_address: int | str,
        high_address: int | str = 0,
        kind: str = "WaterLevel",
        units: str = "percent",
        wet_threshold: int | None = None,
        dry_threshold: int | None = None,
    ):
        self.sensor_name = "GroveWaterLevel"
        self.sensor_kind = kind
        self.sensor_units = units

        self.sensor_id = id
        self.id = id

        # bus coercion
        if isinstance(bus, int):
            coerced_bus = bus
        elif isinstance(bus, str):
            try:
                coerced_bus = int(bus, 0)
            except Exception as e:
                raise WaterLevelInitError(f"Invalid I2C bus string: {bus}") from e
        else:
            raise WaterLevelInitError(f"Unsupported type for I2C bus: {type(bus).__name__}")

        if not (0 <= coerced_bus <= 3):
            raise WaterLevelInitError(f"I2C bus {coerced_bus} out of allowed range 0..3")

        self.bus = coerced_bus

        # address coercion (use low_address as device address)
        def _coerce_addr(val, name):
            if isinstance(val, int):
                coerced = val
            elif isinstance(val, str):
                try:
                    coerced = int(val, 0)
                except Exception as e:
                    raise WaterLevelInitError(f"Invalid I2C address string for {name}: {val}") from e
            else:
                raise WaterLevelInitError(f"Unsupported type for I2C address {name}: {type(val).__name__}")
            if not (0x01 <= coerced <= 0x7F):
                raise WaterLevelInitError(f"I2C address {hex(coerced)} for {name} out of 7-bit range 0x01–0x7F")
            return coerced

        self.device_address = _coerce_addr(low_address, "low_address")
        # preserve for backward compatibility
        self.high_address = high_address

        # thresholds (allow override from config)
        self.wet_threshold = int(wet_threshold) if wet_threshold is not None else self.DEFAULT_WET_THRESHOLD
        self.dry_threshold = int(dry_threshold) if dry_threshold is not None else self.DEFAULT_DRY_THRESHOLD
        if not (0 <= self.wet_threshold < self.dry_threshold <= 255):
            raise WaterLevelValueError("Invalid wet/dry thresholds")

        # open bus
        try:
            self._smbus = SMBus(self.bus)
        except Exception as e:
            raise WaterLevelInitError(f"Failed to open I2C bus {self.bus}: {e}")

    # ----------------- low-level read ---------------------------------------
    def _read_raw_block(self) -> List[int]:
        """
        Read a 9-byte block from address 0x00. Raises WaterLevelReadError on failure.
        """
        if not getattr(self, "_smbus", None):
            try:
                self._smbus = SMBus(self.bus)
            except Exception as e:
                raise WaterLevelReadError(f"Failed to open I2C bus for read: {e}")

        try:
            data = self._smbus.read_i2c_block_data(self.device_address, 0x00, 9)
        except Exception as e:
            raise WaterLevelReadError(f"I2C read failed at address {hex(self.device_address)}: {e}")
        if not isinstance(data, list) or len(data) < 8:
            raise WaterLevelReadError(f"Truncated or malformed read: expected >=8 pad bytes, got {data}")
        return data

    # ----------------- interpretation helpers --------------------------------
    def _classify_pad_values(self, pad_values: List[int]) -> List[int]:
        """
        Classify raw pad values to state codes:
          1 = wet, 0 = dry, -1 = transition (fuzzy)
        """
        state = []
        for v in pad_values:
            if not isinstance(v, int):
                raise WaterLevelReadError(f"Malformed pad value: {v}")
            if v <= self.wet_threshold:
                state.append(1)
            elif v >= self.dry_threshold:
                state.append(0)
            else:
                state.append(-1)
        return state

    def _resolve_transitions_and_spikes(self, state: List[int]) -> List[int]:
        """
        Resolve -1 transition states using neighbours, then fix isolated spikes.
        This mutates a copy and returns resolved 0/1 states.
        """
        resolved = list(state)
        n = len(resolved)

        # Resolve transition (-1): favour wet if any neighbor wet, else dry.
        for i in range(n):
            if resolved[i] == -1:
                left = resolved[i-1] if i-1 >= 0 else 0
                right = resolved[i+1] if i+1 < n else 0
                resolved[i] = 1 if (left == 1 or right == 1) else 0

        # Spike correction: isolated dry between wets -> flip to wet
        for i in range(1, n-1):
            if resolved[i-1] == 1 and resolved[i+1] == 1 and resolved[i] == 0:
                resolved[i] = 1

        return resolved

    def _count_contiguous_wet_from_bottom(self, resolved_state: List[int]) -> int:
        count = 0
        for s in resolved_state:
            if s == 1:
                count += 1
            else:
                break
        return count

    # ----------------- public API -------------------------------------------
    def read(self) -> dict:
        """
        Returns canonical telemetry mapping:
          {"water_level": percent}
        """
        raw = self._read_raw_block()
        pad_values = raw[0:self.NUM_PADS]

        state = self._classify_pad_values(pad_values)
        resolved = self._resolve_transitions_and_spikes(state)
        wet_count = self._count_contiguous_wet_from_bottom(resolved)

        percent = (wet_count / float(self.NUM_PADS)) * 100.0
        return {"water_level": round(percent, 2)}

    # ----------------- shutdown ---------------------------------------------
    def _shutdown(self):
        try:
            if getattr(self, "_smbus", None):
                self._smbus.close()
        except Exception:
            pass
        finally:
            self._smbus = None
