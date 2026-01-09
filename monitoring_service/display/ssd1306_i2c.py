"""
ssd1306_i2c.py

Provides an SSD1306 I2C OLED display implementation for rendering telemetry
snapshots.
"""

import logging
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

    def _draw_centered_text(self, text: str, center_x: int, y: int) -> None:
        """
        Draw text centered horizontally at a specific x coordinate.
        """
        # Use textbbox to get text width
        bbox = self._draw.textbbox((0, 0), text, font=self._font)
        text_width = bbox[2] - bbox[0]
        x = int(center_x - text_width / 2)
        self._draw.text((x, y), text, font=self._font, fill=255)

    def render(self, snapshot: Mapping[str, Any]) -> None:
        """
        Render a telemetry snapshot to the OLED display with labeled values and timestamp.

        Args:
            snapshot: Telemetry snapshot containing ts, water_temperature, air_temperature, and air_humidity.
        """
        if not self._should_render():
            return

        try:
            # Clear display
            self._draw.rectangle((0, 0, self._width, self._height), outline=0, fill=0)

            # Extract values
            water = snapshot.get("water_temperature")
            air = snapshot.get("air_temperature")
            humidity = snapshot.get("air_humidity")
            ts = snapshot.get("ts")

            # Column centers
            col_centers = [21, 64, 107]

            # Row Y positions
            label_y = 0
            value_y = 10
            time_y = 22

            # ---- Labels ----
            labels = ["Water", "Air", "Humidity"]
            for label, cx in zip(labels, col_centers):
                self._draw_centered_text(label, cx, label_y)

            # ---- Values ----
            water_text = f"{water:.1f}°C" if isinstance(water, (int, float)) else "--°C"
            air_text = f"{air:.1f}°C" if isinstance(air, (int, float)) else "--°C"
            humidity_text = f"{humidity:.0f}%" if isinstance(humidity, (int, float)) else "--%"

            values = [water_text, air_text, humidity_text]
            for value, cx in zip(values, col_centers):
                self._draw_centered_text(value, cx, value_y)

            # ---- Timestamp ----
            if ts:
                # If ts is a datetime object
                if isinstance(ts, (int, float)):
                    ts_dt = datetime.fromtimestamp(ts / 1000)
                else:
                    ts_dt = ts
                timestamp = ts_dt.strftime("%H:%M %d/%m/%Y")
            else:
                timestamp = "--:-- --/--/----"

            ts_width, _ = self._draw.textsize(timestamp, font=self._font)
            ts_x = int((self._width - ts_width) / 2)
            self._draw.text((ts_x, time_y), timestamp, font=self._font, fill=255)

            # Update display
            self._oled.image(self._image)
            self._oled.show()

        except Exception:
            self._logger.warning(
                "Failed to render snapshot on SSD1306 OLED display",
                exc_info=True,
            )
