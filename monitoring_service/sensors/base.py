# monitoring_service/sensors/base.py

from abc import ABC, abstractmethod
from typing import Mapping, Any


class BaseSensor(ABC):
    """
    Abstract base class for all sensor drivers.
    Enforces a consistent interface (at minimum: read()).
    """

    @abstractmethod
    def read(self) -> Mapping[str, Any]:
        """
        Return driver readings as a dict-like mapping.
        Example: {"temperature": 22.4, "humidity": 45.1}
        """
        raise NotImplementedError
