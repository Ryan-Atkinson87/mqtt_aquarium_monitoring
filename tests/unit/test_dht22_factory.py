# tests/unit/test_factory_dht22.py
import sys
import types
import pytest

# Fake external libs before importing factory and drivers
fake_board = types.ModuleType("board")
setattr(fake_board, "D17", object())
sys.modules["board"] = fake_board

class _FakeDHT22Device:
    def __init__(self, pin):
        self._pin = pin
        self._temp = 23.1
        self._hum = 56.2
    @property
    def temperature(self): return self._temp
    @property
    def humidity(self): return self._hum

class _FakeAdafruitDHT(types.ModuleType):
    def __init__(self):
        super().__init__("adafruit_dht")
        self._device = _FakeDHT22Device
    def DHT22(self, pin): return self._device(pin)

sys.modules["adafruit_dht"] = _FakeAdafruitDHT()

from monitoring_service.sensors.factory import SensorFactory, SensorBundle
from monitoring_service.exceptions import InvalidSensorConfigError

@pytest.fixture
def factory():
    return SensorFactory(registry=None)

@pytest.fixture
def dht22_cfg_base():
    return {
        "type": "dht22",
        "id": "gpio17",
        "pin": 17,
        "keys": {
            "temperature": "air_temperature",
            "humidity": "air_humidity",
        },
        "calibration": {
            "air_temperature": {"offset": 0.0, "slope": 1.0},
            "air_humidity": {"offset": 0.0, "slope": 1.0},
        },
        "ranges": {
            "air_temperature": {"min": -40, "max": 80},
            "air_humidity": {"min": 0, "max": 100},
        },
        "smoothing": {},
        "interval": 5,
    }

def test_dht22_build_happy_path(factory, dht22_cfg_base):
    bundle = factory.build(dht22_cfg_base)
    assert isinstance(bundle, SensorBundle)
    assert bundle.interval == 5
    assert set(bundle.keys.keys()) == {"temperature", "humidity"}
    assert bundle.keys["temperature"] == "air_temperature"

def test_dht22_requires_all_required_kwargs(factory, dht22_cfg_base):
    # Remove id to violate REQUIRED_KWARGS = {"id","pin"} if you kept it that way
    cfg = dict(dht22_cfg_base)
    cfg.pop("id")
    with pytest.raises(InvalidSensorConfigError):
        factory.build(cfg)

    cfg = dict(dht22_cfg_base)
    cfg.pop("pin")
    with pytest.raises(InvalidSensorConfigError):
        factory.build(cfg)

def test_dht22_pin_string_is_coerced_then_validated(factory, dht22_cfg_base):
    cfg = dict(dht22_cfg_base)
    cfg["pin"] = "17"
    bundle = factory.build(cfg)
    assert isinstance(bundle, SensorBundle)

def test_smoothing_must_be_int_ge_one(factory, dht22_cfg_base):
    cfg = dict(dht22_cfg_base)
    cfg["smoothing"] = {"air_temperature": 0}
    with pytest.raises(InvalidSensorConfigError):
        factory.build(cfg)
    cfg["smoothing"] = {"air_temperature": 1.5}
    with pytest.raises(InvalidSensorConfigError):
        factory.build(cfg)
    cfg["smoothing"] = {"air_temperature": 1}
    bundle = factory.build(cfg)
    assert bundle.smoothing["air_temperature"] == 1

def test_interval_validation(factory, dht22_cfg_base):
    cfg = dict(dht22_cfg_base)
    cfg["interval"] = None
    assert factory.build(cfg).interval is None
    for bad in (0, -1, 1.2, "5"):
        cfg = dict(dht22_cfg_base)
        cfg["interval"] = bad
        with pytest.raises(InvalidSensorConfigError):
            factory.build(cfg)

def test_factory_misconfigured_required_kwargs_subset(factory, dht22_cfg_base, monkeypatch):
    """
    Simulate a driver that declares REQUIRED_KWARGS containing a name not in ACCEPTED_KWARGS.
    Factory should fail fast with a clear error.
    """
    from monitoring_service.sensors.base import BaseSensor

    class BadDriver(BaseSensor):
        REQUIRED_KWARGS = {"pin", "id", "missing_param"}
        ACCEPTED_KWARGS = {"pin", "id"}  # missing_param is not accepted
        def __init__(self, *, pin: int, id: str):
            self.pin = pin
            self.id = id

    factory.register("badtype", BadDriver)
    cfg = dict(dht22_cfg_base)
    cfg["type"] = "badtype"
    with pytest.raises(InvalidSensorConfigError) as e:
        factory.build(cfg)
    assert "misconfigured" in str(e.value) or "REQUIRED_KWARGS" in str(e.value)
