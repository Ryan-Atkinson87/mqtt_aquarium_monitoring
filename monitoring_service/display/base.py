"""
base.py

Defines the BaseDisplay abstract class, which all display drivers must implement.
"""

from abc import ABC, abstractmethod
from typing import Mapping, Any
import time


class BaseDisplay(ABC):
    """
    Abstract base class for all display drivers.

    Display drivers consume already collected telemetry snapshots and render
    them to an output device. Displays do not own timing, polling, or data
    collection.
    """

    def __init__(self, config: Mapping[str, Any]) -> None:
        """
        Initialise the display with its configuration.

        Args:
            config: Display specific configuration mapping.
        """
        self._config = config
        self._refresh_period = int(config.get("refresh_period", 0))
        self._last_render_ts: float = 0.0

    def _should_render(self) -> bool:
        """
        Determine whether enough time has passed to allow a render.

        Returns:
            True if rendering should proceed, False otherwise.
        """
        if self._refresh_period <= 0:
            return True

        now = time.time()
        if (now - self._last_render_ts) >= self._refresh_period:
            self._last_render_ts = now
            return True

        return False

    @abstractmethod
    def render(self, snapshot: Mapping[str, Any]) -> None:
        """
        Render a telemetry snapshot to the display.

        Args:
            snapshot: Telemetry snapshot containing ts, device_name, and values.
        """
        raise NotImplementedError
