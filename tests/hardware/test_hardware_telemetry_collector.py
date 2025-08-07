import pytest
import platform
import pytest
from monitoring_service.telemetry import TelemetryCollector
from monitoring_service.sensors.ds18b20 import DS18B20Sensor

pytestmark = pytest.mark.skipif(
    not any(platform.machine().startswith(arch) for arch in ("arm", "aarch64")),
    reason="Hardware tests only run on Raspberry Pi"
)

@pytest.mark.hardware
def test_get_temperature_reads_real_value():
    sensor = DS18B20Sensor()
    collector = TelemetryCollector(temperature_sensor=sensor)
    temp = collector._get_temperature()
    print(f"Temperature reading: {temp}")
    assert isinstance(temp, float)
    assert -10.0 <= temp <= 50.0