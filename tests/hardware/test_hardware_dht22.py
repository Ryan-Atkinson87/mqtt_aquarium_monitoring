import os
import time
import platform
import pytest

from monitoring_service.inputs.sensors import SensorFactory
from monitoring_service.telemetry import TelemetryCollector

pytestmark = pytest.mark.skipif(
    not any(platform.machine().startswith(arch) for arch in ("arm", "aarch64")),
    reason="Hardware tests only run on Raspberry Pi"
)

def _pick_gpio_from_env(default: int = 17) -> int:
    """Allow overriding the DHT22 pin via env var DHT22_GPIO. Defaults to 17."""
    val = os.environ.get("DHT22_GPIO", str(default))
    try:
        return int(val)
    except ValueError:
        return default

@pytest.mark.hardware
def test_dht22_hardware_read_via_factory_once():
    """
    Build a DHT22 SensorBundle via SensorFactory and read once through TelemetryCollector.
    Tolerate the first few transient failures by retrying for up to 10 seconds.
    """
    pin = _pick_gpio_from_env(17)
    sensor_id = f"gpio{pin}"

    config = {
        "sensors": [
            {
                "type": "dht22",
                "id": sensor_id,
                "pin": pin,
                "keys": {
                    "temperature": "air_temperature",
                    "humidity": "air_humidity",
                },
                "ranges": {
                    "air_temperature": {"min": -40.0, "max": 80.0},
                    "air_humidity": {"min": 0.0, "max": 100.0},
                },
                # no calibration or smoothing needed for a hardware smoke test
                "interval": 1,
            }
        ]
    }

    factory = SensorFactory()
    bundles = factory.build_all(config)
    assert len(bundles) == 1, "Expected exactly one DHT22 bundle"

    collector = TelemetryCollector(bundles=bundles)

    deadline = time.time() + 10.0  # retry window
    telemetry = {}
    while time.time() < deadline:
        telemetry = collector.as_dict()
        if "air_temperature" in telemetry and "air_humidity" in telemetry:
            break
        time.sleep(0.5)  # give sensor a moment and avoid hammering

    assert "air_temperature" in telemetry, "Missing air_temperature from telemetry"
    assert "air_humidity" in telemetry, "Missing air_humidity from telemetry"

    t = telemetry["air_temperature"]
    h = telemetry["air_humidity"]

    assert isinstance(t, (int, float)), "air_temperature should be numeric"
    assert isinstance(h, (int, float)), "air_humidity should be numeric"

    # Sanity ranges for a room with a fish tank nearby
    assert -10.0 <= t <= 50.0, f"Unreasonable air_temperature: {t} °C"
    assert 0.0 <= h <= 100.0, f"Unreasonable air_humidity: {h} %RH"

@pytest.mark.hardware
def test_dht22_invalid_pin_skipped_by_factory():
    from monitoring_service.inputs.sensors import SensorFactory

    bad_pin = 999
    config = {
        "sensors": [
            {
                "type": "dht22",
                "id": f"gpio{bad_pin}",
                "pin": bad_pin,
                "keys": {
                    "temperature": "air_temperature",
                    "humidity": "air_humidity",
                },
            }
        ]
    }

    factory = SensorFactory()

    sensors = factory.build_all(config)

    # Sensor should be skipped, not created, and factory should not raise.
    assert sensors == [] or all(s.id != f"gpio{bad_pin}" for s in sensors)

