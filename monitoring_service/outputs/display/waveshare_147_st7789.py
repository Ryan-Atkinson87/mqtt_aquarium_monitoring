"""
waveshare_147_st7789.py
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
    X_OFFSET = 34
    Y_OFFSET = 0

    MAX_SPI_CHUNK = 4096

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
        self._spi.max_speed_hz = spi_cfg.get("max_speed_hz", 40_000_000)

        self._hardware_reset()
        self._init_display()
        GPIO.output(self._backlight_pin, GPIO.HIGH)

    @staticmethod
    def _validate_config(config: Mapping[str, Any]) -> None:
        if "spi" not in config:
            raise ValueError("Display config missing 'spi' section")
        if "pins" not in config:
            raise ValueError("Display config missing 'pins' section")

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

    def _hardware_reset(self) -> None:
        GPIO.output(self._reset_pin, GPIO.LOW)
        time.sleep(0.05)
        GPIO.output(self._reset_pin, GPIO.HIGH)
        time.sleep(0.05)

    def _write_command(self, command: int) -> None:
        GPIO.output(self._dc_pin, GPIO.LOW)
        self._spi.writebytes([command])

    def _write_data(self, data: bytes) -> None:
        GPIO.output(self._dc_pin, GPIO.HIGH)
        for offset in range(0, len(data), self.MAX_SPI_CHUNK):
            chunk = data[offset : offset + self.MAX_SPI_CHUNK]
            self._spi.writebytes(chunk)

    def _init_display(self) -> None:
        self._write_command(0x01)
        time.sleep(0.15)

        self._write_command(0x11)
        time.sleep(0.15)

        self._write_command(0x3A)
        self._write_data(b"\x55")  # RGB565

        self._write_command(0x36)
        self._write_data(b"\x00")

        self._write_command(0x29)

    def _set_window(self) -> None:
        x_start = self.X_OFFSET
        x_end = self.X_OFFSET + self.WIDTH - 1
        y_start = self.Y_OFFSET
        y_end = self.Y_OFFSET + self.HEIGHT - 1

        self._write_command(0x2A)
        self._write_data(self._u16(x_start) + self._u16(x_end))

        self._write_command(0x2B)
        self._write_data(self._u16(y_start) + self._u16(y_end))

        self._write_command(0x2C)

    def _clear_screen(self) -> None:
        black = b"\x00\x00"
        line = black * self.WIDTH

        for _ in range(self.HEIGHT):
            self._write_data(line)

    def _draw_pixel(self, x: int, y: int, color: bytes) -> None:
        if x < 0 or y < 0 or x >= self.WIDTH or y >= self.HEIGHT:
            return

        self._write_command(0x2A)
        self._write_data(
            self._u16(x + self.X_OFFSET) + self._u16(x + self.X_OFFSET)
        )

        self._write_command(0x2B)
        self._write_data(self._u16(y) + self._u16(y))

        self._write_command(0x2C)
        self._write_data(color)

    def _draw_char(self, x: int, y: int, char: str, color: bytes) -> None:
        glyph = FONT_5X7.get(char.upper())
        if not glyph:
            return

        for col, bits in enumerate(glyph):
            for row in range(7):
                if bits & (1 << row):
                    self._draw_pixel(x + col, y + row, color)

    def draw_text(self, x: int, y: int, text: str, color: bytes) -> None:
        cursor_x = x
        for char in text:
            self._draw_char(cursor_x, y, char, color)
            cursor_x += 6

    def render(self, snapshot: Mapping[str, Any]) -> None:
        if not self._should_render():
            return

        try:
            status = DisplayStatus.from_snapshot(snapshot)

            self._set_window()
            self._clear_screen()

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

            water_temp = getattr(status, "water_temperature", None)
            if water_temp is not None:
                self.draw_text(
                    5,
                    35,
                    f"WATER:{water_temp:.1f}C",
                    white,
                )

        except Exception:
            self._logger.warning("Render failed", exc_info=True)