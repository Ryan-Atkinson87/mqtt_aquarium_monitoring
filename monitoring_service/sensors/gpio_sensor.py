# monitoring_service/sensors/gpio_sensor.py

from monitoring_service.sensors.base import BaseSensor
from monitoring_service.sensors.constants import VALID_GPIO_PINS

class GPIOValueError(Exception):
    pass

class GPIOSensor(BaseSensor):
    """
    Intermediate helper for GPIO-based sensors.
    BaseSensor is already an ABC, so don't re-declare ABC here to avoid MRO issues.
    """

    def _check_pin(self) -> None:
        # Expect the factory to supply a 'pin' attribute (and to coerce types).
        if not hasattr(self, "pin"):
            raise GPIOValueError("Sensor missing required attribute 'pin'")

        if not isinstance(self.pin, int):
            # fixed typo: use self.pin, not self.self.pin
            raise GPIOValueError(f"Invalid pin type: expected int, got {type(self.pin).__name__}")

        if self.pin not in VALID_GPIO_PINS:
            raise GPIOValueError(f"Pin {self.pin} is not a valid GPIO pin on this device.")
