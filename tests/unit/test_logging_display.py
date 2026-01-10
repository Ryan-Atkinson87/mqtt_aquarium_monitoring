import logging
import time

from monitoring_service.display.logging_display import LoggingDisplay


def test_logging_display_renders_snapshot(caplog):
    config = {
        "enabled": True,
        "refresh_period": 0,
    }

    display = LoggingDisplay(config)

    snapshot = {
        "ts": int(time.time() * 1000),
        "device_name": "test_device",
        "values": {
            "water_temperature": 25.123,
        },
    }

    with caplog.at_level(logging.INFO):
        display.render(snapshot)

    assert "water_temperature" in caplog.text
    assert "age=" in caplog.text


def test_logging_display_handles_missing_values(caplog):
    config = {
        "enabled": True,
        "refresh_period": 0,
    }

    display = LoggingDisplay(config)

    snapshot = {
        "ts": None,
        "device_name": "test_device",
        "values": {},
    }

    with caplog.at_level(logging.INFO):
        display.render(snapshot)

    assert "Display update" in caplog.text
