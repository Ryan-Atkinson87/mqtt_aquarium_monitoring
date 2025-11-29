# tests/unit/test_dht22_sensor.py
import sys
import types
import pytest

# --- Fake external libs before importing the driver ---
fake_board = types.ModuleType("board")
setattr(fake_board, "D17", object())
sys.modules["board"] = fake_board

class _FakeDHT22Device:
    def __init__(self, pin):
        # pin is a board.Dxx object; we just store it
        self._pin = pin
        self._temp = 24.3
        self._hum = 58.7

    @property
    def temperature(self):
        return self._temp

    @property
    def humidity(self):
        return self._hum

class _FakeAdafruitDHT(types.ModuleType):
    def __init__(self):
        super().__init__("adafruit_dht")
        self._device = _FakeDHT22Device

    def DHT22(self, pin):
        return self._device(pin)

sys.modules["adafruit_dht"] = _FakeAdafruitDHT()

# Now import after fakes are in place
from monitoring_service.sensors.dht22 import (
    DHT22Sensor,
    DHT22ValueError,
    DHT22ReadError,
)
from monitoring_service.sensors.constants import VALID_GPIO_PINS

@pytest.fixture
def sensor_ok():
    # Use a known good pin that exists in VALID_GPIO_PINS and we provided as board.D17
    assert 17 in VALID_GPIO_PINS, "VALID_GPIO_PINS must include 17 for this test"
    return DHT22Sensor(id="gpio17", pin=17)

def test_check_pin_rejects_bad_type():
    from monitoring_service.sensors.dht22 import DHT22Sensor, DHT22ValueError
    # Pin must be an int. If the factory coerces, good, but direct driver init must reject.
    with pytest.raises(DHT22ValueError):
        DHT22Sensor(id="x", pin="17")  # wrong type on purpose

def test_check_pin_rejects_invalid_pin_number():
    from monitoring_service.sensors.dht22 import DHT22Sensor, DHT22ValueError
    from monitoring_service.sensors.constants import VALID_GPIO_PINS

    bad_pin = max(VALID_GPIO_PINS) + 10
    with pytest.raises(DHT22ValueError):
        DHT22Sensor(id="x", pin=bad_pin)

def test_read_success(sensor_ok, monkeypatch):
    # Ensure the fake device returns expected values
    result = sensor_ok.read()
    assert set(result.keys()) == {"temperature", "humidity"}
    assert isinstance(result["temperature"], float)
    assert isinstance(result["humidity"], float)

def test_read_raises_on_none_temperature(sensor_ok, monkeypatch):
    # Force temperature to None
    device = sensor_ok._create_sensor()
    def _temp_none():
        return None
    monkeypatch.setattr(device.__class__, "temperature", property(lambda self: _temp_none()))
    with pytest.raises(DHT22ReadError):
        sensor_ok.read()

def test_read_raises_on_none_humidity(sensor_ok, monkeypatch):
    # Force humidity to None
    device = sensor_ok._create_sensor()
    def _hum_none():
        return None
    monkeypatch.setattr(device.__class__, "humidity", property(lambda self: _hum_none()))
    with pytest.raises(DHT22ReadError):
        sensor_ok.read()
