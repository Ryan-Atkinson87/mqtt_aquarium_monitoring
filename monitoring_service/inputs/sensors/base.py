"""
base.py

Defines the BaseSensor abstract class, which all sensor drivers must implement.
"""


from abc import ABC, abstractmethod
from typing import Mapping, Any


class BaseSensor(ABC):
    """
    Abstract base class for all sensor drivers.

    Sensor drivers must implement read() and return a mapping of raw sensor
    readings.
    """


    @abstractmethod
    def read(self) -> Mapping[str, Any]:
        """
        Return raw sensor readings as a mapping of key-value pairs.
        """
        raise NotImplementedError
