
import time
import collections
import threading
import pytest
from unittest import mock

# This test module assumes your project is importable as monitoring_service
# and that the WaterFlowSensor lives at monitoring_service.sensors.water_flow.WaterFlowSensor
from monitoring_service.sensors.water_flow import (
    WaterFlowSensor,
    WaterFlowInitError,
    WaterFlowValueError,
    WaterFlowReadError,
)

import pigpio as real_pigpio  # will be monkeypatched in tests


# --- Helpers / Fakes ------------------------------------------------------

class FakeCallback:
    def __init__(self):
        self.cancelled = False
        self.cancel_calls = 0

    def cancel(self):
        self.cancelled = True
        self.cancel_calls += 1


class FakePi:
    def __init__(self, connected=True):
        self.connected = connected
        self.callback_calls = []
        self._tick_start = int(time.time() * 1_000_000)

    def callback(self, pin, edge, func):
        self.callback_calls.append((pin, edge, func))
        class CB:
            def cancel(self):
                pass
        return CB()

    def set_mode(self, pin, mode):
        pass

    def set_pull_up_down(self, pin, pud):
        pass

    def set_glitch_filter(self, pin, glitch_us):
        pass

    def stop(self):
        self.connected = False

    def get_current_tick(self):
        # Return a "current" tick in microseconds
        # Ensure it’s beyond any ticks you inject in the test
        return int(time.time() * 1_000_000) % (2**32)


# monkeypatch helper to feed ticks to the sensor instance
def feed_ticks(sensor, ticks):
    """Directly populate the tick deque (thread-safe)"""
    with sensor.ticks_lock:
        sensor.ticks.clear()
        for t in ticks:
            sensor.ticks.append(t)


# --- Tests ---------------------------------------------------------------

def test_waterflow_init_valid_pin(monkeypatch):
    fake_pi = FakePi(connected=True)
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    # instantiate with valid pin (assumes VALID_GPIO_PINS allows 17 in your project)
    s = WaterFlowSensor(id="f1", pin=17)
    assert s.sensor is not None
    assert s._callback is not None
    # cleanup
    s.stop()


def test_waterflow_init_pigpio_not_running(monkeypatch):
    fake_pi = FakePi(connected=False)
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    with pytest.raises(WaterFlowInitError):
        WaterFlowSensor(id="f1", pin=17)


def test_waterflow_init_pigpio_throws(monkeypatch):
    def boom():
        raise Exception("boom")
    monkeypatch.setattr("pigpio.pi", boom)
    with pytest.raises(WaterFlowInitError):
        WaterFlowSensor(id="f1", pin=17)


def test_waterflow_start_registers_callback(monkeypatch):
    fake_pi = FakePi(connected=True)
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    s = WaterFlowSensor(id="f1", pin=17)
    # callback registered on init via start()
    assert fake_pi.callback_calls, "callback should have been registered"
    # idempotent start
    prev = len(fake_pi.callback_calls)
    s.start()
    assert len(fake_pi.callback_calls) == prev, "start() should be idempotent"
    s.stop()


def test_waterflow_callback_adds_ticks(monkeypatch):
    fake_pi = FakePi(connected=True)
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    s = WaterFlowSensor(id="f1", pin=17)
    # simulate callback invocation: find registered function and call it
    pin, edge, fn = fake_pi.callback_calls[0]
    # call with falling edge (level=0)
    fn(pin, 0, 1000000)
    with s.ticks_lock:
        assert len(s.ticks) == 1
        assert s.ticks[0] == 1000000
    s.stop()


def test_waterflow_callback_sliding_window_purges_old_ticks(monkeypatch):
    fake_pi = FakePi(connected=True)
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    # use a small sliding window for test
    s = WaterFlowSensor(id="f1", pin=17, sliding_window_s=1.0)
    pin, edge, fn = fake_pi.callback_calls[0]
    # append ticks at t=0, t=0.6s, then new tick at t=2s -> should purge first two
    fn(pin, 0, 0)
    fn(pin, 0, 600000)
    fn(pin, 0, 2000000)
    with s.ticks_lock:
        # only the last tick should remain because window=1s at last tick
        assert len(s.ticks) == 1
        assert s.ticks[0] == 2000000
    s.stop()


def test_waterflow_get_flow_no_ticks(monkeypatch):
    fake_pi = FakePi(connected=True)
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    s = WaterFlowSensor(id="f1", pin=17)
    feed_ticks(s, [])
    inst, smooth = s._get_instant_and_smoothed()
    assert inst == 0.0 and smooth == 0.0
    s.stop()


def test_waterflow_get_flow_single_tick(monkeypatch):
    fake_pi = FakePi(connected=True)
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    s = WaterFlowSensor(id="f1", pin=17)
    feed_ticks(s, [1_000_000])
    inst, smooth = s._get_instant_and_smoothed()
    assert inst == 0.0 and smooth == 0.0
    s.stop()


def test_waterflow_get_flow_valid_sequence(monkeypatch):
    fake_pi = FakePi(connected=True)
    fake_pi._current_tick = 700_000
    fake_pi.get_current_tick = lambda: fake_pi._current_tick
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    s = WaterFlowSensor(id="f1", pin=17, calibration_constant=4.5)
    # ticks spaced 200000us apart => 5 Hz
    ticks = [0, 200000, 400000, 600000]
    feed_ticks(s, ticks)
    inst, smooth = s._get_instant_and_smoothed()
    # pulses_per_sec should be (n-1) / total_time_seconds = 3 / 0.6 = 5
    assert pytest.approx(smooth, rel=1e-3) == 5.0 / 4.5
    assert pytest.approx(inst, rel=1e-3) == 5.0 / 4.5
    s.stop()


def test_waterflow_get_flow_with_wraparound(monkeypatch):
    fake_pi = FakePi(connected=True)
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    # monkeypatch pigpio.tickDiff to simulate wraparound calculation
    original_tickdiff = real_pigpio.tickDiff
    monkeypatch.setattr("pigpio.tickDiff", lambda t1, t2: (t2 - t1) if t2 >= t1 else ( (2**32 + t2) - t1 ))
    s = WaterFlowSensor(id="f1", pin=17, calibration_constant=4.5)
    # simulate wrap: first tick near uint32 max, last tick small
    max_val = 2**32 - 1000
    ticks = [max_val, max_val + 200000, 200000]  # note: values here are synthetic; tickDiff handles wrap
    # use normalized small ints since we overrode tickDiff
    normalized = [4294000000, 4294200000, 200000]
    feed_ticks(s, normalized)
    inst, smooth = s._get_instant_and_smoothed()
    # we just ensure it doesn't raise and returns floats
    assert isinstance(inst, float) and isinstance(smooth, float)
    s.stop()


def test_waterflow_read_waits_sample_window(monkeypatch):
    fake_pi = FakePi(connected=True)
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    s = WaterFlowSensor(id="f1", pin=17, sample_window=0.01)
    # monkeypatch time.sleep to avoid real wait and to assert it was called
    called = {}
    def fake_sleep(sec):
        called['sec'] = sec
    monkeypatch.setattr("time.sleep", fake_sleep)
    # call read and ensure we returned a dict
    ret = s.read()
    assert 'flow_instant' in ret and 'flow_smoothed' in ret
    assert called.get('sec') == 0.01
    s.stop()


def test_waterflow_read_raises_on_compute_error(monkeypatch):
    fake_pi = FakePi(connected=True)
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    s = WaterFlowSensor(id="f1", pin=17)
    # force _get_instant_and_smoothed to raise
    def boom():
        raise Exception("boom")
    s._get_instant_and_smoothed = boom
    with pytest.raises(WaterFlowReadError):
        s.read()
    s.stop()


def test_waterflow_stop_cancels_callback_and_stops_pigpio(monkeypatch):
    fake_pi = FakePi(connected=True)
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    s = WaterFlowSensor(id="f1", pin=17)
    cb_handle = s._callback
    assert cb_handle is not None
    s.stop()
    # callback should be cancelled and sensor stopped
    assert s._callback is None
    assert s.sensor is None


def test_waterflow_stop_idempotent(monkeypatch):
    fake_pi = FakePi(connected=True)
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    s = WaterFlowSensor(id="f1", pin=17)
    s.stop()
    # second stop should not raise
    s.stop()


def test_waterflow_del_calls_stop(monkeypatch):
    fake_pi = FakePi(connected=True)
    monkeypatch.setattr("pigpio.pi", lambda: fake_pi)
    s = WaterFlowSensor(id="f1", pin=17)
    # replace stop with a spy
    called = {}
    def spy_stop():
        called['stop'] = True
    s.stop = spy_stop
    # trigger __del__
    s.__del__()
    assert called.get('stop', False) is True
