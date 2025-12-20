"""
gpio_sensor.py

Provides a base helper class for GPIO-based sensors, including shared GPIO
validation logic.
"""


from monitoring_service.sensors.base import BaseSensor
from monitoring_service.sensors.constants import VALID_GPIO_PINS

class GPIOValueError(Exception):
    """
    Raised when a GPIO sensor is misconfigured or uses an invalid GPIO pin.
    """
    pass

class GPIOSensor(BaseSensor):
    """
    Base class for sensors that use a GPIO pin.

    Provides shared validation logic for GPIO pin configuration.
    """

    def _check_pin(self) -> None:
        """
        Validate that the sensor has a valid GPIO pin configured.

        Expects the instance to define a `pin` attribute containing a valid
        integer GPIO pins.
        """
        # Expect the factory to supply a 'pin' attribute (and to coerce types).
        if not hasattr(self, "pin"):
            raise GPIOValueError("Sensor missing required attribute 'pin'")

        if not isinstance(self.pin, int):
            # fixed typo: use self.pin, not self.self.pin
            raise GPIOValueError(f"Invalid pin type: expected int, got {type(self.pin).__name__}")

        if self.pin not in VALID_GPIO_PINS:
            raise GPIOValueError(f"Pin {self.pin} is not a valid GPIO pin on this device.")
