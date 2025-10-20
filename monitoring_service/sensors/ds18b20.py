# ds18b20.py

import glob
import os
from monitoring_service.sensors.base import BaseSensor

class DS18B20ReadError(Exception):
    """Raised when the DS18B20 sensor fails to return a valid reading."""
    pass

class DS18B20Sensor(BaseSensor):
    """
    # TODO: Expand on this doc string,class docstring → describe parameters: sensor_id, base_path, kind, units.
    Handles reading from the DS18B20 sensor.
    """
    REQUIRED_ANY_OF = [{"id"}, {"path"}]
    ACCEPTED_KWARGS = {"id", "path"}

    def __init__(self, *, id: str | None = None, path: str | None = None, kind="Temperature", units="C"):
        self.sensor_id = id
        self.base_dir = path
        self.sensor_name = "ds18b20"
        self.sensor_kind = kind
        self.sensor_units = units
        self.UPPER_LIMIT = 125
        self.LOWER_LIMIT = -55

    @property
    def name(self):
        return self.sensor_name

    @property
    def kind(self):
        return self.sensor_kind

    @property
    def units(self):
        return self.sensor_units

    def _get_device_file(self):
        if self.sensor_id:
            # Ensure base_dir exists and build path
            device_file = os.path.join(self.base_dir, self.sensor_id, "w1_slave")
        else:
            # Auto-discover the first DS18B20 if no id provided
            device_folders = glob.glob(os.path.join(self.base_dir, "28-*"))
            if not device_folders:
                raise DS18B20ReadError("No DS18B20 sensor found.")
            device_file = os.path.join(device_folders[0], "w1_slave")

        return device_file

    def _read_temp(self):
        device_file = self._get_device_file()
        with open(device_file, 'r') as f:
            lines = f.readlines()
        if lines[0].strip()[-3:] != 'YES':
            raise DS18B20ReadError("Sensor CRC check failed")
        equals_pos = lines[1].find('t=')
        if equals_pos == -1:
            raise DS18B20ReadError("Temperature reading not found")
        return float(lines[1][equals_pos + 2:]) / 1000.0

    def read(self):
        # TODO: Add doc string, read() docstring → “Returns: dict {‘temperature’: float °C}”.
        temp = self._read_temp()
        return_dict = {
            "temperature": temp,
        }

        return return_dict

    # def health(self):
    #     pass

    # def close(self):
    #     pass