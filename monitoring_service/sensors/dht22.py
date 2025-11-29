# dht22.py

"""
Driver module for dht22 sensor
"""
import adafruit_dht
import board
from monitoring_service.sensors.gpio_sensor import GPIOSensor, GPIOValueError
from typing import Any

class DHT22InitError(Exception):
    pass

class DHT22ValueError(Exception):
    pass

class DHT22ReadError(Exception):
    pass

class DHT22Sensor(GPIOSensor):
    # Factory uses these for validation + filtering.
    REQUIRED_KWARGS = ["id", "pin"]
    ACCEPTED_KWARGS = ["id", "pin"]
    COERCERS = {"pin": int}

    def __init__(self, *, id: str | None = None, pin: int | None = None,
                 kind: str = "Temperature", units: str = "C"):
        self.sensor = None
        self.sensor_name = "DHT22"
        self.sensor_kind = kind
        self.sensor_units = units

        self.sensor_id: str | None = id
        self.pin: int | None = pin
        self._check_pin()

        self.id = self.sensor_id

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

    def _check_pin(self) -> None:
        """
        Use the generic GPIO check but re-raise as DHT22ValueError so tests
        and callers see driver-specific exceptions.
        """
        try:
            super()._check_pin()
        except GPIOValueError as e:
            raise DHT22ValueError(str(e)) from e

    def _create_sensor(self) -> Any:
        try:
            pin_ref = getattr(board, f"D{self.pin}")
            self.sensor = adafruit_dht.DHT22(pin_ref)
        except Exception as e:
            raise DHT22InitError(f"Failed to create DHT22 sensor on pin {self.pin}: {e}")
        return self.sensor

    # --- Public API ---------------------------------------------------------

    def read(self):
        return_dict = {}

        if self.sensor is None:
            self._create_sensor()

        try:
            temperature = self.sensor.temperature
        except Exception as e:
            raise DHT22ReadError(f"Failed to read DHT22 sensor temperature: {e}")
        if temperature is None:
            raise DHT22ReadError("Temperature reading returned None")
        try:
            humidity = self.sensor.humidity
        except Exception as e:
            raise DHT22ReadError(f"Failed to read DHT22 sensor humidity: {e}")
        if humidity is None:
            raise DHT22ReadError("Humidity reading returned None")

        return_dict["temperature"] = temperature
        return_dict["humidity"] = humidity

        return return_dict
