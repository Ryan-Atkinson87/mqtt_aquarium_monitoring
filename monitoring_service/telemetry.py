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


import glob
import logging
import os

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    from unittest import mock

    GPIO = mock.MagicMock()


class TelemetryCollector:
    """
    Manages the collection of telemetry from the Raspberry Pi.
    Uses get_telemetry to collect telemetry from the Raspberry Pi in the form of a
    dictionary of telemetry data.
    """

    def __init__(self, temperature_sensor=None, logger=None, mount_path="/"):
        self.mount_path = mount_path
        self.logger = logger or logging.getLogger(__name__)
        self.temperature_sensor = temperature_sensor

    def _get_temperature(self):
        try:
            return self.temperature_sensor.read_temp()
        except Exception as e:
            self.logger.error(f"Error getting aquarium temperature: {e}")
            return None

    def _get_water_level(self, water_level_pin):
        # TODO: create logic for reading from water level sensor
        try:
            return GPIO.input(water_level_pin)
        except RuntimeError as e:
            self.logger.error(f"Error getting water level: {e}")
            return None

    def _get_air_temperature(self, air_temperature_pin):
        # TODO: create logic for reading from dht22 sensor
        try:
            return GPIO.input(air_temperature_pin)
        except RuntimeError as e:
            self.logger.error(f"Error getting air temperature: {e}")
            return None

    def _get_air_humidity(self, air_humidity_pin):
        # TODO: create logic for reading from dht22 sensor
        try:
            return GPIO.input(air_humidity_pin)
        except RuntimeError as e:
            self.logger.error(f"Error getting air humidity: {e}")
            return None

    def _get_water_flow_rate(self, water_flow_rate_pin):
        # TODO: create logic for reading from flow sensor
        try:
            return GPIO.input(water_flow_rate_pin)
        except RuntimeError as e:
            self.logger.error(f"Error getting water flow rate: {e}")
            return None

    def _get_turbidity(self, turbidity_pin):
        # TODO: create logic for reading from turbidity sensor
        try:
            return GPIO.input(turbidity_pin)
        except RuntimeError as e:
            self.logger.error(f"Error getting turbidity: {e}")
            return None

    def as_dict(self):
        """
        Return a dictionary containing the aquarium telemetry data.

        :return: dictionary containing the aquarium telemetry data.
        """
        temperature = self._get_temperature()
        water_level = self._get_water_level()
        air_temperature = self._get_air_temperature()
        air_humidity = self._get_air_humidity()
        water_flow_rate = self._get_water_flow_rate()
        turbidity = self._get_turbidity()

        return {
            "temperature": temperature,
            "water_level": water_level,
            "air_temperature": air_temperature,
            "air_humidity": air_humidity,
            "water_flow_rate": water_flow_rate,
            "turbidity": turbidity,
        }

