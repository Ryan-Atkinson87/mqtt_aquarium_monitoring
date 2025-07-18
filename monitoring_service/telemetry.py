"""
telemetry.py

Provides the TelemetryCollector class, which gathers system metrics from a
Raspberry Pi or other Linux-based device. These metrics include CPU usage,
CPU temperature, GPU temperature, RAM usage, and disk usage.

All metrics are returned as a dictionary of telemetry data, along with a list
of any errors encountered during collection. This data is intended for use
with IoT platforms such as ThingsBoard.

Classes:
    TelemetryCollector

Usage:
    collector = TelemetryCollector()
    telemetry, errors = collector.get_telemetry()
"""


class TelemetryCollector:
    """
    Manages the collection of telemetry from the Raspberry Pi.
    Uses get_telemetry to collect telemetry from the Raspberry Pi in the form of a
    dictionary of telemetry data.
    """

    def __init__(self, logger, mount_path="/"):
        self.mount_path = mount_path
        self.logger = logger

    def _get_temperature(self):
        # TODO: create logic for reading from temperature sensor
        try:
            return 25
        except Exception as e:
            self.logger.error(f"Error getting aquarium temperature: {e}")
            return None

    def _get_water_level(self):
        # TODO: create logic for reading from water level sensor
        try:
            return -10
        except Exception as e:
            self.logger.error(f"Error getting water level: {e}")
            return None

    def _get_air_temp(self):
        # TODO: create logic for reading from dht22 sensor
        try:
            return 25
        except Exception as e:
            self.logger.error(f"Error getting air temperature: {e}")
            return None

    def _get_air_humidity(self):
        # TODO: create logic for reading from dht22 sensor
        try:
            return 50
        except Exception as e:
            self.logger.error(f"Error getting air humidity: {e}")
            return None

    def _get_water_flow_rate(self):
        # TODO: create logic for reading from flow sensor
        try:
            return 200
        except Exception as e:
            self.logger.error(f"Error getting water flow rate: {e}")
            return None

    def _get_turbidity(self):
        # TODO: create logic for reading from turbidity sensor
        try:
            return 5
        except Exception as e:
            self.logger.error(f"Error getting turbidity: {e}")
            return None

    def as_dict(self):
        """
        Return a dictionary containing the aquarium telemetry data.

        :return: dictionary containing the aquarium telemetry data.
        """
        temperature = self._get_temperature()
        water_level = self._get_water_level()

        return {
            "temperature": temperature,
            "water_level": water_level,
        }
