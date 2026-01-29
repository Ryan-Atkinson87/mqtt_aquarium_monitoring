import pytest
from typing import Any, Mapping

from monitoring_service.telemetry import TelemetryCollector
from monitoring_service.inputs.sensors.factory import SensorBundle


# ---------- Test doubles ----------

class FakeDriver:
    """Simple driver that returns a fixed dict, or raises if configured to."""
    def __init__(self, payload: Mapping[str, Any] | None = None, raise_exc: Exception | None = None):
        self._payload = payload or {}
        self._raise = raise_exc

    def read(self) -> Mapping[str, Any]:
        if self._raise:
            raise self._raise
        return dict(self._payload)

# ---------- Fixtures ----------

@pytest.fixture
def make_bundle():
    def _make(
        *,
        driver_payload: Mapping[str, Any] = None,
        keys: dict[str, str] = None,
        calibration: dict[str, dict[str, float]] = None,
        ranges: dict[str, dict[str, float]] = None,
        smoothing: dict[str, int] = None,
        interval: int | None = None,
        raise_exc: Exception | None = None,
    ) -> SensorBundle:
        driver = FakeDriver(payload=driver_payload, raise_exc=raise_exc)
        return SensorBundle(
            driver=driver,
            keys=keys or {},
            calibration=calibration or {},
            ranges=ranges or {},
            smoothing=smoothing or {},
            interval=interval,
        )
    return _make


# ---------- Mapping ----------

def test_mapping_renames_keys_and_drops_unmapped(make_bundle):
    b = make_bundle(
        driver_payload={"temperature": 21.0, "junk": 999},
        keys={"temperature": "water_temperature"},
    )
    c = TelemetryCollector(bundles=[b])
    out = c.as_dict()
    assert out == {"water_temperature": 21.0}


# ---------- Calibration ----------

def test_calibration_applies_slope_then_offset(make_bundle):
    # (21.0 * 1.1) + 2.0 = 25.1
    b = make_bundle(
        driver_payload={"temperature": 21.0},
        keys={"temperature": "water_temperature"},
        calibration={"water_temperature": {"slope": 1.1, "offset": 2.0}},
    )
    c = TelemetryCollector(bundles=[b])
    out = c.as_dict()
    assert pytest.approx(out["water_temperature"], rel=1e-6) == 25.1


def test_calibration_respects_zero_values(make_bundle):
    # slope=0.0 should zero out; offset=0.0 should not be overwritten by defaults
    b = make_bundle(
        driver_payload={"temperature": 21.0},
        keys={"temperature": "water_temperature"},
        calibration={"water_temperature": {"slope": 0.0, "offset": 0.0}},
    )
    c = TelemetryCollector(bundles=[b])
    out = c.as_dict()
    assert out["water_temperature"] == 0.0


# ---------- Smoothing (EMA) ----------

def test_smoothing_seeds_then_smooths(make_bundle, monkeypatch):
    # Configure smoothing window of 5 (alpha=2/6≈0.3333)
    b = make_bundle(
        driver_payload={"temperature": 20.0},
        keys={"temperature": "water_temperature"},
        smoothing={"water_temperature": 5},
    )
    c = TelemetryCollector(bundles=[b])

    # First call: seeds with 20.0
    out1 = c.as_dict()
    assert out1["water_temperature"] == 20.0

    # Second call: new raw value 26.0, compute EMA
    b.driver._payload = {"temperature": 26.0}
    out2 = c.as_dict()
    # ema = 0.3333*26 + 0.6667*20 = ~22.0
    assert pytest.approx(out2["water_temperature"], rel=1e-3) == 22.0


def test_smoothing_with_prev_zero_is_not_reseeded(make_bundle):
    # Prove that a previous smoothed value of 0.0 is treated as present (not falsy-reseeded)
    b = make_bundle(
        driver_payload={"v": 0.0},
        keys={"v": "x"},
        smoothing={"x": 3},  # alpha=0.5
    )
    c = TelemetryCollector(bundles=[b])

    out1 = c.as_dict()
    assert out1["x"] == 0.0

    b.driver._payload = {"v": 10.0}
    out2 = c.as_dict()
    # ema with alpha=0.5: 0.5*10 + 0.5*0 = 5
    assert out2["x"] == 5.0


# ---------- Ranges ----------

def test_ranges_inclusive_bounds_keep_value(make_bundle):
    b = make_bundle(
        driver_payload={"temperature": 40.0},
        keys={"temperature": "water_temperature"},
        ranges={"water_temperature": {"min": 0.0, "max": 40.0}},  # inclusive
    )
    c = TelemetryCollector(bundles=[b])
    out = c.as_dict()
    assert out["water_temperature"] == 40.0


def test_ranges_drop_out_of_range_value(make_bundle):
    b = make_bundle(
        driver_payload={"temperature": -5.0},
        keys={"temperature": "water_temperature"},
        ranges={"water_temperature": {"min": 0.0, "max": 40.0}},
    )
    c = TelemetryCollector(bundles=[b])
    out = c.as_dict()
    assert "water_temperature" not in out


# ---------- Intervals (per-bundle due logic) ----------

def test_interval_skips_when_not_due(make_bundle, monkeypatch):
    # interval 10s → second call at t+5 should skip, preserving first reading
    b = make_bundle(
        driver_payload={"t": 1.0},
        keys={"t": "x"},
        interval=10,
    )
    c = TelemetryCollector(bundles=[b])

    # Freeze time
    t0 = 1000.0
    monkeypatch.setattr("time.time", lambda: t0)
    out1 = c.as_dict()
    assert out1["x"] == 1.0

    # Advance 5s (not due)
    monkeypatch.setattr("time.time", lambda: t0 + 5)
    b.driver._payload = {"t": 2.0}  # would be new raw, but shouldn't be read
    out2 = c.as_dict()
    # Since we skipped, there should be no new value emitted; dict can be empty
    # because the collector only returns values from sensors it read this cycle.
    assert out2 == {}


def test_interval_reads_when_due(make_bundle, monkeypatch):
    b = make_bundle(
        driver_payload={"t": 1.0},
        keys={"t": "x"},
        interval=5,
    )
    c = TelemetryCollector(bundles=[b])

    t0 = 2000.0
    monkeypatch.setattr("time.time", lambda: t0)
    out1 = c.as_dict()
    assert out1["x"] == 1.0

    # Exactly due at +5
    monkeypatch.setattr("time.time", lambda: t0 + 5)
    b.driver._payload = {"t": 3.0}
    out2 = c.as_dict()
    assert out2["x"] == 3.0


# ---------- Driver error isolation ----------

def test_driver_failure_does_not_block_other_sensors(make_bundle):
    bad = make_bundle(
        driver_payload=None,
        keys={"temperature": "bad"},
        raise_exc=RuntimeError("boom"),
    )
    good = make_bundle(
        driver_payload={"temperature": 24.0},
        keys={"temperature": "water_temperature"},
    )
    c = TelemetryCollector(bundles=[bad, good])
    out = c.as_dict()
    assert out == {"water_temperature": 24.0}


# ---------- Merge collision policy ----------

def test_collision_last_wins(make_bundle):
    b1 = make_bundle(
        driver_payload={"temperature": 20.0},
        keys={"temperature": "water_temperature"},
    )
    b2 = make_bundle(
        driver_payload={"temp": 22.0},
        keys={"temp": "water_temperature"},  # same canonical key
    )
    c = TelemetryCollector(bundles=[b1, b2])
    out = c.as_dict()
    # Later bundle overwrites earlier value
    assert out["water_temperature"] == 22.0


# ---------- Mapping drops unmapped keys ----------

def test_unmapped_keys_are_dropped(make_bundle):
    b = make_bundle(
        driver_payload={"a": 1, "b": 2},
        keys={"a": "A"},  # no mapping for 'b'
    )
    c = TelemetryCollector(bundles=[b])
    out = c.as_dict()
    assert out == {"A": 1}
