"""
waveshare_147_st7789.py

Waveshare 1.47" LCD (SKU 22224)
Controller: ST7789V3
Resolution: 172x320 (windowed inside 240x320 GRAM)
SPI mode 0, RGB565
"""

import time
import logging
from typing import Mapping, Any

import spidev
import RPi.GPIO as GPIO

from monitoring_service.outputs.display.base import BaseDisplay
from monitoring_service.outputs.display.font_5x7 import FONT_5X7
from monitoring_service.outputs.status_model import DisplayStatus


class Waveshare147ST7789Display(BaseDisplay):
    WIDTH = 172
    HEIGHT = 320

    # Critical for this panel
    X_OFFSET = 34
    Y_OFFSET = 0

    MAX_SPI_CHUNK = 4096  # spidev limit

    def __init__(self, config: Mapping[str, Any]) -> None:
        super().__init__(config)
        self._validate_config(config)

        self._logger = logging.getLogger(
            "monitoring_service.display.waveshare_147_st7789"
        )

        pins = config["pins"]
        spi_cfg = config["spi"]

        self._dc_pin = pins["dc"]
        self._reset_pin = pins["reset"]
        self._backlight_pin = pins["backlight"]

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._dc_pin, GPIO.OUT)
        GPIO.setup(self._reset_pin, GPIO.OUT)
        GPIO.setup(self._backlight_pin, GPIO.OUT)

        self._spi = spidev.SpiDev()
        self._spi.open(spi_cfg["bus"], spi_cfg["device"])
        self._spi.mode = spi_cfg.get("mode", 0)
        self._spi.max_speed_hz = spi_cfg.get("max_speed_hz", 10_000_000)

        self._logger.info(
            "Init ST7789 1.47: %dx%d offset=(%d,%d)",
            self.WIDTH,
            self.HEIGHT,
            self.X_OFFSET,
            self.Y_OFFSET,
        )

        self._hardware_reset()
        self._init_display()

        GPIO.output(self._backlight_pin, GPIO.HIGH)

        # Framebuffer (RGB565)
        self._framebuffer = bytearray(self.WIDTH * self.HEIGHT * 2)

    # ------------------------------------------------------------------

    @staticmethod
    def _validate_config(config: Mapping[str, Any]) -> None:
        if "spi" not in config:
            raise ValueError("Display config missing 'spi'")
        if "pins" not in config:
            raise ValueError("Display config missing 'pins'")

        for key in ("bus", "device"):
            if key not in config["spi"]:
                raise ValueError(f"SPI config missing '{key}'")

        for pin in ("dc", "reset", "backlight"):
            if pin not in config["pins"]:
                raise ValueError(f"Pin config missing '{pin}'")

    @staticmethod
    def _u16(value: int) -> bytes:
        return value.to_bytes(2, "big")

    @staticmethod
    def _rgb565(r: int, g: int, b: int) -> bytes:
        value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        return value.to_bytes(2, "big")

    # ------------------------------------------------------------------

    def _hardware_reset(self) -> None:
        GPIO.output(self._reset_pin, GPIO.LOW)
        time.sleep(0.05)
        GPIO.output(self._reset_pin, GPIO.HIGH)
        time.sleep(0.05)

    def _write_command(self, cmd: int) -> None:
        GPIO.output(self._dc_pin, GPIO.LOW)
        self._spi.writebytes([cmd])

    def _write_data(self, data: bytes) -> None:
        GPIO.output(self._dc_pin, GPIO.HIGH)
        for i in range(0, len(data), self.MAX_SPI_CHUNK):
            self._spi.writebytes(data[i : i + self.MAX_SPI_CHUNK])

    # ------------------------------------------------------------------

    def _init_display(self) -> None:
        self._logger.info("Initializing ST7789")

        self._write_command(0x01)  # SWRESET
        time.sleep(0.15)

        self._write_command(0x11)  # SLPOUT
        time.sleep(0.15)

        self._write_command(0x3A)  # COLMOD
        self._write_data(b"\x55")  # RGB565

        # MADCTL — critical (matches Waveshare)
        self._write_command(0x36)
        self._write_data(b"\x70")

        self._write_command(0x29)  # DISPON
        time.sleep(0.05)

    # ------------------------------------------------------------------

    def _set_window(self) -> None:
        x0 = self.X_OFFSET
        x1 = self.X_OFFSET + self.WIDTH - 1
        y0 = self.Y_OFFSET
        y1 = self.Y_OFFSET + self.HEIGHT - 1

        self._write_command(0x2A)
        self._write_data(self._u16(x0) + self._u16(x1))

        self._write_command(0x2B)
        self._write_data(self._u16(y0) + self._u16(y1))

        self._write_command(0x2C)

    # ------------------------------------------------------------------

    def _draw_char(self, x: int, y: int, char: str, color: bytes) -> None:
        glyph = FONT_5X7.get(char.upper())
        if not glyph:
            return

        for col, bits in enumerate(glyph):
            for row in range(7):
                if bits & (1 << row):
                    px = x + col
                    py = y + row
                    if 0 <= px < self.WIDTH and 0 <= py < self.HEIGHT:
                        idx = (py * self.WIDTH + px) * 2
                        self._framebuffer[idx : idx + 2] = color

    def draw_text(self, x: int, y: int, text: str, color: bytes) -> None:
        cx = x
        for ch in text:
            self._draw_char(cx, y, ch, color)
            cx += 6

    # ------------------------------------------------------------------

    def render(self, snapshot: Mapping[str, Any]) -> None:
        if not self._should_render():
            return

        try:
            self._logger.debug("Rendering frame")
            status = DisplayStatus.from_snapshot(snapshot)

            # Clear framebuffer (white)
            self._framebuffer[:] = self._rgb565(255, 255, 255) * (
                self.WIDTH * self.HEIGHT
            )

            white = self._rgb565(255, 255, 255)
            green = self._rgb565(0, 255, 0)
            red = self._rgb565(255, 0, 0)

            self.draw_text(5, 5, status.device_name, white)
            # self.draw_text(
            #     5,
            #     20,
            #     "NET: OK" if status.connected else "NET: DOWN",
            #     green if status.connected else red,
            # )

            if status.water_temperature is not None:
                self.draw_text(
                    5,
                    35,
                    f"WATER:{status.water_temperature:.1f}C",
                    white,
                )

            self._set_window()
            self._write_data(self._framebuffer)

        except Exception:
            self._logger.warning("Render failed", exc_info=True)