from monitoring_service.sensors.base import BaseSensor
from smbus3 import SMBus, i2c_msg


class WaterLevelInitError(Exception):
    pass


class WaterLevelValueError(Exception):
    pass


class WaterLevelReadError(Exception):
    pass


class I2CWaterLevelSensor(BaseSensor):
    """
    Updated driver for the Grove Water Level Sensor v1.0 (I2C).
    Reads 8 pad values from a *single* I2C address and computes
    the percentage of submerged pads.
    """

    REQUIRED_KWARGS = ["id", "bus", "low_address"]
    ACCEPTED_KWARGS = ["id", "bus", "low_address", "high_address"]
    COERCERS = {"bus": int, "low_address": int, "high_address": int}

    NUM_PADS = 8
    DEFAULT_WET_THRESHOLD = 150  # below = wet

    def __init__(
        self,
        *,
        id: str,
        bus: int | str,
        low_address: int | str,
        high_address: int | str = 0,
        kind: str = "WaterLevel",
        units: str = "percent"
    ):
        self.sensor_name = "GroveWaterLevel"
        self.sensor_kind = kind
        self.sensor_units = units

        self.sensor_id = id
        self.id = id

        # --- Bus coercion ---
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

        # --- Address coercion (we only use low_address) ---
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
                raise WaterLevelInitError(
                    f"I2C address {hex(coerced)} for {name} out of 7-bit range 0x01–0x7F"
                )
            return coerced

        self.device_address = _coerce_addr(low_address, "low_address")

        # high_address unused, but preserved for backward compatibility
        self.high_address = high_address

        # Open bus
        self._check_bus()

    # ----------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self.sensor_name

    @property
    def kind(self) -> str:
        return self.sensor_kind

    @property
    def units(self) -> str:
        return self.sensor_units

    # ----------------------------------------------------------------------

    def _check_bus(self):
        """Open /dev/i2c-{bus} and keep the handle."""
        try:
            self._smbus = SMBus(self.bus)
        except Exception as e:
            raise WaterLevelInitError(f"Failed to open I2C bus {self.bus}: {e}")

    # ----------------------------------------------------------------------

    def _read_raw_block(self) -> list[int]:
        """
        Reads 9 bytes from the device.
        Byte layout (Grove v1.0):
          [0..7] = 8 pad values
          [8]    = unused / checksum / not required
        """
        try:
            # Read 9 bytes starting at register 0x00
            data = self._smbus.read_i2c_block_data(self.device_address, 0x00, 9)
            print("DEBUG: raw=", data)
            return data
        except Exception as e:
            raise WaterLevelReadError(
                f"I2C read failed at address {hex(self.device_address)}: {e}"
            )

    # ----------------------------------------------------------------------

    def _count_wet_pads(self, pad_values: list[int]) -> int:
        """
        Counts pads that are below threshold, bottom to top,
        stopping at first dry pad.
        """
        threshold = self.DEFAULT_WET_THRESHOLD
        wet = 0
        for v in pad_values:
            if v < threshold:
                wet += 1
            else:
                break
        print("DEBUG: wet=", wet)
        return wet

    # ----------------------------------------------------------------------

    def read(self) -> dict:
        """
        Public read API. Matches the project convention of returning
        a dict {key: value} for upstream telemetry collection.
        """
        raw = self._read_raw_block()
        pad_values = raw[0:8]

        wet = self._count_wet_pads(pad_values)
        percent = (wet / self.NUM_PADS) * 100.0

        print("DEBUG: percent=", percent)
        return {"water_level": round(percent, 2)}

    # ----------------------------------------------------------------------

    def _shutdown(self):
        try:
            if getattr(self, "_smbus", None):
                self._smbus.close()
        except Exception:
            pass
        finally:
            self._smbus = None
