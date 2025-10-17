import os
import glob
import platform
import pytest

from monitoring_service.telemetry import TelemetryCollector
from monitoring_service.sensors.factory import SensorFactory

pytestmark = pytest.mark.skipif(
    not any(platform.machine().startswith(arch) for arch in ("arm", "aarch64")),
    reason="Hardware tests only run on Raspberry Pi"
)

@pytest.mark.hardware
def test_ds18b20_hardware_read_via_factory():
    """
    Discover a real DS18B20 on the Pi, build a SensorBundle via SensorFactory,
    inject into TelemetryCollector, and assert a sane temperature in °C.
    """
    # 1) Find a DS18B20 device on the 1-Wire bus
    device_dirs = glob.glob("/sys/bus/w1/devices/28-*")
    if not device_dirs:
        pytest.skip("No DS18B20 devices detected under /sys/bus/w1/devices/28-*")

    sensor_id = os.path.basename(device_dirs[0])  # e.g. "28-00000abcdef"

    # 2) Build config expected by SensorFactory
    config = {
        "sensors": [
            {
                "type": "ds18b20",
                "id": sensor_id,                       # prefer id over path for clarity
                "keys": {"temperature": "water_temperature"},  # map driver key -> canonical key
                # Optional guard rails so garbage doesn't leak:
                "ranges": {"water_temperature": {"min": -20.0, "max": 85.0}},
                # No calibration/smoothing/interval needed for a basic hardware sanity check
            }
        ]
    }

    # 3) Build bundles and collector
    factory = SensorFactory()
    bundles = factory.build_all(config)
    assert len(bundles) == 1, "Expected exactly one DS18B20 bundle"

    collector = TelemetryCollector(bundles=bundles)

    # 4) Read once and validate
    telemetry = collector.as_dict()
    assert "water_temperature" in telemetry, "Mapped key missing from telemetry output"

    value = telemetry["water_temperature"]
    assert isinstance(value, (int, float)), "Temperature should be numeric"
    # DS18B20 spec: -55..125°C, but your aquarium should not be insane.
    assert -10.0 <= value <= 50.0, f"Unreasonable water temperature: {value}°C"


@pytest.mark.hardware
def test_ds18b20_hardware_read_with_path_via_factory():
    """
    Same as above but configures using the sensor's absolute device file path instead of id.
    Useful if your factory supports both and you want to validate either route.
    """
    device_dirs = glob.glob("/sys/bus/w1/devices/28-*")
    if not device_dirs:
        pytest.skip("No DS18B20 devices detected under /sys/bus/w1/devices/28-*")

    device_dir = device_dirs[0]
    device_file = os.path.join(device_dir, "w1_slave")

    config = {
        "sensors": [
            {
                "type": "ds18b20",
                "path": device_file,                    # use path this time
                "keys": {"temperature": "water_temperature"},
                "ranges": {"water_temperature": {"min": -20.0, "max": 85.0}},
            }
        ]
    }

    factory = SensorFactory()
    bundles = factory.build_all(config)
    assert len(bundles) == 1

    collector = TelemetryCollector(bundles=bundles)
    telemetry = collector.as_dict()

    assert "water_temperature" in telemetry
    value = telemetry["water_temperature"]
    assert isinstance(value, (int, float))
    assert -10.0 <= value <= 50.0
