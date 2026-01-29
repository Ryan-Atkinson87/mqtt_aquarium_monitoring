"""
factory.py

Provides a factory function for constructing display instances from
configuration.
"""

import logging
from typing import List, Mapping, Any

from monitoring_service.outputs.display.logging_display import LoggingDisplay
from monitoring_service.outputs.display.ssd1306_i2c import SSD1306I2CDisplay


_DISPLAY_TYPES = {
    "logging": LoggingDisplay,
    "ssd1306_i2c": SSD1306I2CDisplay,
}


def build_displays(
    displays_config: List[Mapping[str, Any]],
    logger: logging.Logger,
) -> List[Any]:
    """
    Build and initialise display instances from configuration.

    Args:
        displays_config: List of display configuration mappings.
        logger: Logger instance.

    Returns:
        List of successfully initialised display instances.
    """
    displays: List[Any] = []

    if not displays_config:
        logger.info("No displays configured.")
        return displays

    for index, display_config in enumerate(displays_config):
        if not display_config.get("enabled", False):
            continue

        display_type = display_config.get("type")
        if not display_type:
            logger.warning(
                "Display config at index %s missing type, skipping",
                index,
            )
            continue

        display_class = _DISPLAY_TYPES.get(display_type)
        if not display_class:
            logger.warning(
                "Unknown display type '%s', skipping",
                display_type,
            )
            continue

        try:
            display = display_class(display_config)
            displays.append(display)
            logger.info(
                "Initialised display type '%s'",
                display_type,
            )
        except Exception:
            logger.warning(
                "Failed to initialise display type '%s'",
                display_type,
                exc_info=True,
            )

    return displays
