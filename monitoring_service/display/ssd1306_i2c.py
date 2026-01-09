"""
ssd1306_i2c.py

Provides an SSD1306 I2C OLED display implementation for rendering telemetry
snapshots.
"""

import logging
import time
from datetime import datetime
from typing import Mapping, Any

from PIL import Image, ImageDraw, ImageFont

import board
import busio
import adafruit_ssd1306

from monitoring_service.display.base import BaseDisplay


class SSD1306I2CDisplay(BaseDisplay):
    """
    SSD1306-based I2C OLED display implementation.
    """

    def __init__(self, config: Mapping[str, Any]) -> None:
        """
        Initialise the SSD1306 I2C OLED display.

        Args:
            config: Display specific configuration mapping.
        """
        super().__init__(config)
        self._logger = logging.getLogger("display.ssd1306")

        self._width = int(config.get("width", 128))
        self._height = int(config.get("height", 32))
        self._address = int(config.get("address", 0x3C))

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self._oled = adafruit_ssd1306.SSD1306_I2C(
                self._width,
                self._height,
                i2c,
                addr=self._address,
            )

            self._oled.fill(0)
            self._oled.show()

            self._image = Image.new("1", (self._width, self._height))
            self._draw = ImageDraw.Draw(self._image)
            self._font = ImageFont.load_default()

            self._line_height = 10

            self._logger.info(
                "SSD1306 OLED initialised (%sx%s @ 0x%X)",
                self._width,
                self._height,
                self._address,
            )

        except Exception:
            self._logger.error(
                "Failed to initialise SSD1306 I2C OLED display",
                exc_info=True,
            )
            raise

    def render(self, snapshot: Mapping[str, Any]) -> None:
        """
        Render a telemetry snapshot to the OLED display.

        Args:
            snapshot: Telemetry snapshot containing ts, device_name, and values.
        """
        if not self._should_render():
            return

        try:
            self._draw.rectangle(
                (0, 0, self._width, self._height),
                outline=0,
                fill=0,
            )

            values = snapshot.get("values", {})
            timestamp_ms = snapshot.get("ts")

            water_temperature = values.get("water_temperature")

            if isinstance(water_temperature, (int, float)):
                temperature_text = f"{water_temperature:.1f}"
            else:
                temperature_text = "--.-"

            if isinstance(timestamp_ms, (int, float)):
                dt = datetime.fromtimestamp(timestamp_ms / 1000)
                time_text = dt.strftime("%H:%M")
                date_text = dt.strftime("%d/%m/%Y")
            else:
                time_text = "--:--"
                date_text = "--/--/----"

            left_x = 0
            right_x = 64

            self._draw.text(
                (left_x, 0),
                temperature_text,
                font=self._font,
                fill=255,
            )

            self._draw.text(
                (right_x, 0),
                time_text,
                font=self._font,
                fill=255,
            )

            self._draw.text(
                (right_x, self._line_height),
                date_text,
                font=self._font,
                fill=255,
            )

            self._oled.image(self._image)
            self._oled.show()

        except Exception:
            self._logger.warning(
                "Failed to render snapshot on SSD1306 OLED display",
                exc_info=True,
            )
