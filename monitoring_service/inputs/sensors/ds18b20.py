"""
ds18b20.py

Provides a sensor driver for the DS18B20 1-Wire temperature sensor.
"""

import glob
import os
from monitoring_service.inputs.sensors.base import BaseSensor


class DS18B20ReadError(Exception):
    """
    Raised when the DS18B20 sensor fails to return a valid reading.
    """
    pass


class DS18B20Sensor(BaseSensor):
    """
    DS18B20 temperature sensor driver.

    Parameters
    ----------
    id : str | None
        The 1-Wire sensor id, e.g. "28-00000abcdef".
        If a directory path is provided together with an id, the device file is
        constructed as <base_dir>/<id>/w1_slave.

    path : str | None
        Either a full path to the device file ".../w1_slave" OR a base directory
        like "/sys/bus/w1/devices/". If a full file is provided, discovery is skipped.
        If a directory is provided with an id, the device file is constructed.
    kind : str
        Human-readable kind, defaults to "Temperature".
    units : str
        Units, defaults to "C".
    """

    # Factory uses these for validation + filtering.
    REQUIRED_ANY_OF = [{"id"}, {"path"}]
    ACCEPTED_KWARGS = {"id", "path"}

    def __init__(self, *, id: str | None = None, path: str | None = None,
                 kind: str = "Temperature", units: str = "C"):
        self.sensor_name = "ds18b20"
        self.sensor_kind = kind
        self.sensor_units = units

        self.UPPER_LIMIT = 125
        self.LOWER_LIMIT = -55

        self.sensor_id: str | None = id

        self.base_dir: str = "/sys/bus/w1/devices"
        self.device_file: str | None = None

        if path:
            norm = path.rstrip("/")
            if os.path.isfile(norm):
                self.device_file = norm
                self.path = self.device_file
                self.id = self.sensor_id
                return
            else:
                self.base_dir = norm

        if self.sensor_id:
            self.device_file = os.path.join(self.base_dir, self.sensor_id, "w1_slave")

        self.id = self.sensor_id
        self.path = self.device_file

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

    def _discover_device_file(self) -> str:
        """
        Discover and return a DS18B20 device file under base_dir or raise.
        """
        # Typical glob: /sys/bus/w1/devices/28-*/w1_slave
        candidates = glob.glob(os.path.join(self.base_dir, "28-*", "w1_slave"))
        if not candidates:
            raise DS18B20ReadError("No DS18B20 sensor found.")
        return candidates[0]

    def _get_device_file(self) -> str:
        """
        Return a concrete device file path, never None.
        """
        if self.device_file:
            return self.device_file
        self.device_file = self._discover_device_file()
        self.path = self.device_file
        return self.device_file

    def _read_temp(self) -> float:
        """
        Read temperature in Celsius from the device file.
        """
        device_file = self._get_device_file()
        with open(device_file, "r") as f:
            lines = f.readlines()

        if not lines or not lines[0].strip().endswith("YES"):
            raise DS18B20ReadError("Sensor CRC check failed")

        pos = lines[1].find("t=")
        if pos == -1:
            raise DS18B20ReadError("Temperature reading not found")

        try:
            return float(lines[1][pos + 2:]) / 1000.0
        except ValueError:
            raise DS18B20ReadError("Malformed temperature value")

    # --- Public API ---------------------------------------------------------

    def read(self) -> dict:
        """
        Read the current temperature from the DS18B20 sensor.

        Returns:
            dict: Mapping with a single key "temperature" (float, °C).
        """
        temp_c = self._read_temp()
        return {"temperature": temp_c}
