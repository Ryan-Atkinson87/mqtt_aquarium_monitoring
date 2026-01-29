"""
logging_display.py

Provides a logging based display implementation for development and testing.
"""

import logging
import time
from typing import Mapping, Any

from monitoring_service.outputs.display.base import BaseDisplay


class LoggingDisplay(BaseDisplay):
    """
    Display implementation that logs selected telemetry values instead of
    rendering them to physical hardware.
    """

    def __init__(self, config: Mapping[str, Any]) -> None:
        """
        Initialise the logging display.

        Args:
            config: Display specific configuration mapping.
        """
        super().__init__(config)
        self._logger = logging.getLogger("display.logging")

    def render(self, snapshot: Mapping[str, Any]) -> None:
        """
        Log selected telemetry values from a snapshot.

        Args:
            snapshot: Telemetry snapshot containing ts, device_name, and values.
        """
        if not self._should_render():
            return

        try:
            timestamp_ms = snapshot.get("ts")
            values = snapshot.get("values", {})

            water_temperature = values.get("water_temperature", "N/A")

            if isinstance(timestamp_ms, (int, float)):
                age_seconds = int((time.time() * 1000 - timestamp_ms) / 1000)
            else:
                age_seconds = "N/A"

            self._logger.info(
                "Display update | water_temperature=%s | age=%s seconds",
                water_temperature,
                age_seconds,
            )

        except Exception:
            self._logger.warning(
                "Failed to render snapshot on logging display",
                exc_info=True,
            )
