import time
import pytest

from monitoring_service.outputs.display.waveshare_147_st7789 import (
    Waveshare147ST7789Display
)

@pytest.mark.hardware
def test_waveshare_display_initializes_and_renders():
    config = {
        "refresh_period": 1,
        "spi": {
            "bus": 0,
            "device": 0,
            "mode": 0,
            "max_speed_hz": 40000000,
        },
        "pins": {
            "dc": 25,
            "reset": 27,
            "backlight": 18,
        },
    }

    display = Waveshare147ST7789Display(config)

    snapshot = {
        "device_name": "test-device",
        "connected": True,
        "last_publish_ok": True,
        "ts": time.time(),
        "values": {
            "cpu_temp_c": 42.5,
            "water_temp_c": 23.1,
            "flow_present": True,
        },
    }

    display.render(snapshot)
    time.sleep(2)

    assert True
