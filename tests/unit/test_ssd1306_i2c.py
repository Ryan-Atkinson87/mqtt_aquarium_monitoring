import sys
import time
from unittest.mock import MagicMock

# ---- Mock hardware modules BEFORE import ----
sys.modules["board"] = MagicMock()
sys.modules["busio"] = MagicMock()
sys.modules["adafruit_ssd1306"] = MagicMock()

from monitoring_service.outputs.display.ssd1306_i2c import SSD1306I2CDisplay


def test_ssd1306_display_init_and_render():
    mock_oled = MagicMock()
    sys.modules["adafruit_ssd1306"].SSD1306_I2C.return_value = mock_oled

    config = {
        "enabled": True,
        "refresh_period": 0,
        "width": 128,
        "height": 32,
        "address": 0x3C,
    }

    display = SSD1306I2CDisplay(config)

    snapshot = {
        "ts": int(time.time() * 1000),
        "device_name": "test_device",
        "values": {
            "water_temperature": 24.5,
            "air_temperature": 19.2,
            "air_humidity": 45.0,
        },
    }

    display.render(snapshot)

    mock_oled.image.assert_called_once()
    mock_oled.show.assert_called()
