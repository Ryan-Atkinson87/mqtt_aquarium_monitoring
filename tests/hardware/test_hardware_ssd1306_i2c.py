import time
import pytest

from monitoring_service.outputs.display.ssd1306_i2c import SSD1306I2CDisplay


@pytest.mark.hardware
def test_ssd1306_i2c_hardware_init_and_render():
    """
    Hardware test for SSD1306 I2C OLED display.

    Verifies that the display can be initialised and rendered to on
    real hardware without raising exceptions.
    """

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
        "device_name": "hardware_test_device",
        "values": {
            "water_temperature": 25.0,
            "air_temperature": 20.0,
            "air_humidity": 50.0,
        },
    }

    display.render(snapshot)

    # Give the user a moment to visually confirm output if desired
    time.sleep(1)
