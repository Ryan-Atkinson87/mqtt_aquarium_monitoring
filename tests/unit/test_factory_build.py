import pytest

from monitoring_service.inputs.sensors.factory import SensorFactory, SensorBundle
from monitoring_service.inputs.sensors.ds18b20 import DS18B20Sensor
from monitoring_service.exceptions import (
    InvalidSensorConfigError,
    UnknownSensorTypeError,
)

# ---------- Fixtures ----------

@pytest.fixture
def factory():
    # Use default registry with ds18b20 already registered
    return SensorFactory(registry=None)

@pytest.fixture
def base_valid_cfg():
    # Minimal valid sensor block using id (flat config)
    return {
        "type": "ds18b20",
        "id": "28-00000abc123",
        "path": "/sys/bus/w1/devices/",  # present but id should take precedence
        "keys": {"temperature": "water_temperature"},
        "calibration": {"water_temperature": {"offset": 0.0, "slope": 1.0}},
        "ranges": {"water_temperature": {"min": 0.0, "max": 40.0}},
        "smoothing": {"water_temperature": 3},
        "interval": 5,
    }

# ---------- Happy path ----------

def test_build_valid_id_path_present(factory, base_valid_cfg):
    bundle = factory.build(base_valid_cfg)
    assert isinstance(bundle, SensorBundle)
    assert set(bundle.keys.keys()) == {"temperature"}
    assert bundle.keys["temperature"] == "water_temperature"
    # calibration/ranges/smoothing carried through
    assert "water_temperature" in bundle.calibration
    assert "water_temperature" in bundle.ranges
    assert "water_temperature" in bundle.smoothing
    assert bundle.interval == 5
    # driver constructed
    assert isinstance(bundle.driver, DS18B20Sensor)

def test_build_valid_with_path_only(factory, base_valid_cfg):
    cfg = dict(base_valid_cfg)
    cfg.pop("id")
    bundle = factory.build(cfg)
    assert isinstance(bundle.driver, DS18B20Sensor)

def test_build_valid_with_id_only(factory, base_valid_cfg):
    cfg = dict(base_valid_cfg)
    # allow missing/None interval
    cfg["interval"] = None
    bundle = factory.build(cfg)
    assert bundle.interval is None

# ---------- Type resolution ----------

def test_unknown_sensor_type(factory, base_valid_cfg):
    cfg = dict(base_valid_cfg)
    cfg["type"] = "unknown_sensor"
    with pytest.raises(UnknownSensorTypeError):
        factory.build(cfg)

# ---------- keys map ----------

def test_missing_keys_map(factory, base_valid_cfg):
    cfg = dict(base_valid_cfg)
    cfg.pop("keys")
    with pytest.raises(InvalidSensorConfigError):
        factory.build(cfg)

def test_empty_keys_map(factory, base_valid_cfg):
    cfg = dict(base_valid_cfg)
    cfg["keys"] = {}
    with pytest.raises(InvalidSensorConfigError):
        factory.build(cfg)

# ---------- calibration validation (offset/slope dict) ----------

def test_calibration_requires_offset_and_slope(factory, base_valid_cfg):
    cfg = dict(base_valid_cfg)
    cfg["calibration"] = {"water_temperature": {"offset": 0.1}}  # missing slope
    with pytest.raises(InvalidSensorConfigError):
        factory.build(cfg)

def test_calibration_values_must_be_numeric(factory, base_valid_cfg):
    cfg = dict(base_valid_cfg)
    cfg["calibration"] = {"water_temperature": {"offset": "a", "slope": 1.0}}
    with pytest.raises(InvalidSensorConfigError):
        factory.build(cfg)

def test_calibration_canonical_key_must_exist(factory, base_valid_cfg):
    cfg = dict(base_valid_cfg)
    cfg["calibration"] = {"bogus": {"offset": 0.0, "slope": 1.0}}
    with pytest.raises(InvalidSensorConfigError):
        factory.build(cfg)

# ---------- ranges validation (dict with min/max) ----------

@pytest.mark.parametrize("bad_ranges", [
    {"water_temperature": {"min": 10}},                       # missing max
    {"water_temperature": {"max": 40}},                       # missing min
    {"water_temperature": {"min": "x", "max": 40}},           # non-numeric
    {"water_temperature": {"min": 40, "max": 10}},            # min >= max
    {"bogus": {"min": 0, "max": 40}},                         # unknown canonical key
])
def test_ranges_invalid(factory, base_valid_cfg, bad_ranges):
    cfg = dict(base_valid_cfg)
    cfg["ranges"] = bad_ranges
    with pytest.raises(InvalidSensorConfigError):
        factory.build(cfg)

# ---------- smoothing validation (int >= 1 per canonical key) ----------

@pytest.mark.parametrize("smoothing", [
    {"water_temperature": 0},
    {"water_temperature": -1},
    {"water_temperature": 1.5},
    {"bogus": 2},  # unknown canonical key
])
def test_smoothing_invalid(factory, base_valid_cfg, smoothing):
    cfg = dict(base_valid_cfg)
    cfg["smoothing"] = smoothing
    with pytest.raises(InvalidSensorConfigError):
        factory.build(cfg)

def test_smoothing_valid(factory, base_valid_cfg):
    cfg = dict(base_valid_cfg)
    cfg["smoothing"] = {"water_temperature": 1}
    bundle = factory.build(cfg)
    assert bundle.smoothing["water_temperature"] == 1

# ---------- interval validation (optional int >= 1) ----------

@pytest.mark.parametrize("interval", [None, 1, 10])
def test_interval_valid_values(factory, base_valid_cfg, interval):
    cfg = dict(base_valid_cfg)
    cfg["interval"] = interval
    bundle = factory.build(cfg)
    assert bundle.interval == interval

@pytest.mark.parametrize("interval", [0, -1, 1.2, "5"])
def test_interval_invalid_values(factory, base_valid_cfg, interval):
    cfg = dict(base_valid_cfg)
    cfg["interval"] = interval
    with pytest.raises(InvalidSensorConfigError):
        factory.build(cfg)

# ---------- required any-of (id OR path) ----------

def test_missing_both_id_and_path(factory, base_valid_cfg):
    cfg = dict(base_valid_cfg)
    cfg.pop("id")
    cfg.pop("path")
    with pytest.raises(InvalidSensorConfigError):
        factory.build(cfg)

# ---------- build_all ----------

def test_build_all_with_list(factory, base_valid_cfg):
    bundles = factory.build_all([base_valid_cfg])
    assert len(bundles) == 1
    assert isinstance(bundles[0], SensorBundle)

def test_build_all_with_dict(factory, base_valid_cfg):
    bundles = factory.build_all({"sensors": [base_valid_cfg]})
    assert len(bundles) == 1

def test_build_all_skips_invalid_and_logs(factory, base_valid_cfg, caplog):
    bad = dict(base_valid_cfg)
    bad["keys"] = {}  # invalid
    with caplog.at_level("WARNING"):
        bundles = factory.build_all([base_valid_cfg, bad])
    assert len(bundles) == 1
    # ensure a warning mentioning skip is present
    assert any("Skipping sensor" in r.message for r in caplog.records)

# ---------- registry override warning ----------

def test_register_override_warns(factory, caplog):
    with caplog.at_level("WARNING"):
        factory.register("ds18b20", DS18B20Sensor)
    assert any("Overriding driver" in r.message for r in caplog.records)
