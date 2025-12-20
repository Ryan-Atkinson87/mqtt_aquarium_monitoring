# tests/test_i2c_water_level.py
import pytest
from types import SimpleNamespace

import monitoring_service.sensors.non_functional.i2c_water_level as wlmod
from monitoring_service.sensors.non_functional.i2c_water_level import (
    I2CWaterLevelSensor,
    WaterLevelInitError,
    WaterLevelReadError,
)


class FakeMsg:
    """Simple fake for i2c_msg.read result that is iterable (list(msg) works)."""
    def __init__(self, addr: int, length: int, data: list[int]):
        self.addr = addr
        self.length = length
        # ensure data length matches requested length
        if data is None:
            data = [0] * length
        if len(data) != length:
            raise ValueError("FakeMsg data length mismatch")
        self._data = list(data)

    def __iter__(self):
        yield from self._data

    def __len__(self):
        return len(self._data)


class FakeSMBus:
    """Fake SMBus that does nothing in i2c_rdwr. The i2c_msg.read factory
    will pre-populate FakeMsg instances with the desired data so this can be no-op."""
    def __init__(self, busnum):
        self.busnum = busnum
        self.closed = False

    def i2c_rdwr(self, *msgs):
        # Validate that msgs are FakeMsg instances
        for m in msgs:
            if not hasattr(m, "_data") and not hasattr(m, "_FakeMsg_marker"):
                # allow FakeMsg and our factory-created objects; otherwise raise to
                # surface an unexpected usage in tests or code.
                raise RuntimeError("i2c_rdwr received unexpected message type")
        # do nothing - FakeMsg already carries the data

    def close(self):
        self.closed = True


@pytest.fixture
def i2c_mapping():
    """
    Provide a mutable mapping structure accessible by the fake i2c_msg.read factory:
    mapping[(addr, length)] -> list[int]
    Tests populate this mapping before instantiating the sensor.
    """
    return {}


def setup_fakes(monkeypatch, mapping):
    """
    Monkeypatch wlmod.SMBus and wlmod.i2c_msg.read to use fakes backed by mapping.
    mapping is a dict {(addr, length): [bytes...]}. If an entry is missing, the
    factory will raise to simulate a non-responding device.
    """
    # Patch SMBus
    monkeypatch.setattr(wlmod, "SMBus", FakeSMBus)

    # Create a factory closure that returns FakeMsg reading from mapping
    def fake_i2c_msg_read(addr, length):
        # mapping key is using ints; ensure normalization
        key = (int(addr) & 0x7F, int(length))
        if key in mapping:
            data = mapping[key]
        else:
            # Strict behavior: missing mapping means "no response" -> raise to simulate NACK/absent device
            raise RuntimeError(f"No fake I2C data for addr={hex(key[0])} len={key[1]}")
        msg = FakeMsg(addr, length, data)
        msg._FakeMsg_marker = True
        msg._data = data
        return msg

    # Patch the i2c_msg namespace used in module
    fake_i2c_msg_ns = SimpleNamespace(read=fake_i2c_msg_read)
    monkeypatch.setattr(wlmod, "i2c_msg", fake_i2c_msg_ns)



def test_resolves_shifted_addresses_when_arduino_style_given(monkeypatch, i2c_mapping):
    """
    If config supplies Arduino 8-bit addresses (0x77/0x78), the code should try
    shifting them into 7-bit (0x3B/0x3C) and accept the shifted pair when present.
    """
    # Provide mapping for the shifted 7-bit pair (0x3B=59, 0x3C=60)
    low7 = 0x3B
    high7 = 0x3C
    # make both addresses respond with one zero byte for probing
    i2c_mapping[(low7, 1)] = [0x00]
    i2c_mapping[(high7, 1)] = [0x00]

    setup_fakes(monkeypatch, i2c_mapping)

    # Use Arduino style 8-bit addresses as strings
    sensor = I2CWaterLevelSensor(id="wl1", bus=1, low_address="0x77", high_address="0x78")
    assert hasattr(sensor, "addr_low") and hasattr(sensor, "addr_high")
    assert sensor.addr_low == low7
    assert sensor.addr_high == high7


def test_collect_raw_counts_sections_and_returns_mm(monkeypatch, i2c_mapping):
    """
    Provide concrete 8 + 12 bytes where first two low bytes are > threshold,
    ensure sections_triggered == 2 and level_mm == 10.0 (2 * 5 mm).
    """
    # Prepare mapping for 7-bit addresses used directly
    low7 = 0x3B
    high7 = 0x3C

    # For probing (1-byte reads) return non-error responses
    i2c_mapping[(low7, 1)] = [0x00]
    i2c_mapping[(high7, 1)] = [0x00]

    # Low 8 bytes: first two are high (>100), others zero
    low_bytes = [150, 130, 0, 0, 0, 0, 0, 0]
    # High 12 bytes: all zeros
    high_bytes = [0] * 12
    i2c_mapping[(low7, 8)] = low_bytes
    i2c_mapping[(high7, 12)] = high_bytes

    setup_fakes(monkeypatch, i2c_mapping)

    sensor = I2CWaterLevelSensor(id="wl2", bus=1, low_address=low7, high_address=high7)
    raw = sensor._collect_raw()

    assert raw["raw_bytes_low"] == low_bytes
    assert raw["raw_bytes_high"] == high_bytes
    assert raw["sections_triggered"] == 2
    assert raw["level_mm"] == pytest.approx(10.0)


def test_probe_failure_raises(monkeypatch, i2c_mapping):
    """
    When no candidate pair responds, initialization should raise WaterLevelInitError.
    Do not populate mapping so all probes fail (FakeSMBus will raise if message types mismatch).
    """
    setup_fakes(monkeypatch, i2c_mapping)

    with pytest.raises(WaterLevelInitError):
        # supply some addresses but mapping is empty (no responses set)
        I2CWaterLevelSensor(id="wl3", bus=1, low_address=0x3B, high_address=0x3C)


def test_read_io_failure_raises(monkeypatch, i2c_mapping):
    """
    Simulate an I/O error during i2c_rdwr by making the SMBus.i2c_rdwr raise.
    We'll monkeypatch the SMBus.i2c_rdwr after the sensor is constructed so
    address probing is not affected.
    """
    # Prepare mapping so address resolution succeeds
    low7 = 0x3B
    high7 = 0x3C
    i2c_mapping[(low7, 1)] = [0x00]
    i2c_mapping[(high7, 1)] = [0x00]
    i2c_mapping[(low7, 8)] = [0] * 8
    i2c_mapping[(high7, 12)] = [0] * 12

    setup_fakes(monkeypatch, i2c_mapping)

    # Build the sensor first (this runs address probing using the fake SMBus)
    sensor = I2CWaterLevelSensor(id="wl4", bus=1, low_address=low7, high_address=high7)

    # Now patch the module's SMBus class method i2c_rdwr so subsequent reads fail
    def raising_i2c_rdwr(self, *msgs):
        raise OSError("simulated I/O error")

    monkeypatch.setattr(wlmod.SMBus, "i2c_rdwr", raising_i2c_rdwr, raising=False)

    # Now calling _collect_raw should surface WaterLevelReadError
    with pytest.raises(WaterLevelReadError):
        sensor._collect_raw()

def test_non_consecutive_bits_only_counts_lsb_run(monkeypatch, i2c_mapping):
    low7, high7 = 0x3B, 0x3C
    i2c_mapping[(low7, 1)] = [0]
    i2c_mapping[(high7, 1)] = [0]
    # low bytes: bit0=1, bit1=0, bit2=1 -> not consecutive, should count only bit0 -> 1 section
    low_bytes = [150, 0, 130, 0, 0, 0, 0, 0]
    i2c_mapping[(low7, 8)] = low_bytes
    i2c_mapping[(high7, 12)] = [0]*12
    setup_fakes(monkeypatch, i2c_mapping)
    s = I2CWaterLevelSensor(id="ncb", bus=1, low_address=low7, high_address=high7)
    raw = s._collect_raw()
    assert raw["sections_triggered"] == 1
    assert raw["level_mm"] == pytest.approx(5.0)

def test_no_sections_wet_returns_zero_mm(monkeypatch, i2c_mapping):
    low7, high7 = 0x3B, 0x3C
    i2c_mapping[(low7, 1)] = [0]
    i2c_mapping[(high7, 1)] = [0]
    i2c_mapping[(low7, 8)] = [0]*8
    i2c_mapping[(high7, 12)] = [0]*12
    setup_fakes(monkeypatch, i2c_mapping)
    s = I2CWaterLevelSensor(id="none", bus=1, low_address=low7, high_address=high7)
    raw = s._collect_raw()
    assert raw["sections_triggered"] == 0
    assert raw["level_mm"] == pytest.approx(0.0)

def test_all_sections_wet_returns_full_mm(monkeypatch, i2c_mapping):
    low7, high7 = 0x3B, 0x3C
    i2c_mapping[(low7, 1)] = [0]
    i2c_mapping[(high7, 1)] = [0]
    i2c_mapping[(low7, 8)] = [200]*8
    i2c_mapping[(high7, 12)] = [200]*12
    setup_fakes(monkeypatch, i2c_mapping)
    s = I2CWaterLevelSensor(id="full", bus=1, low_address=low7, high_address=high7)
    raw = s._collect_raw()
    assert raw["sections_triggered"] == 20
    assert raw["level_mm"] == pytest.approx(100.0)

def test_address_coercion_accepts_hex_string_and_int(monkeypatch, i2c_mapping):
    low7, high7 = 0x3B, 0x3C
    i2c_mapping[(low7,1)] = [0]; i2c_mapping[(high7,1)] = [0]
    setup_fakes(monkeypatch, i2c_mapping)
    s1 = I2CWaterLevelSensor(id="a1", bus="1", low_address="0x3B", high_address="0x3C")
    assert s1.bus == 1 and s1.low_address == 0x3B and s1.high_address == 0x3C
    s2 = I2CWaterLevelSensor(id="a2", bus=1, low_address=59, high_address=60)
    assert s2.low_address == 59 and s2.high_address == 60

def test_shutdown_closes_smbus(monkeypatch, i2c_mapping):
    low7, high7 = 0x3B, 0x3C
    i2c_mapping[(low7,1)] = [0]; i2c_mapping[(high7,1)] = [0]
    i2c_mapping[(low7,8)] = [0]*8; i2c_mapping[(high7,12)] = [0]*12
    setup_fakes(monkeypatch, i2c_mapping)
    s = I2CWaterLevelSensor(id="down", bus=1, low_address=low7, high_address=high7)
    assert getattr(s, "_smbus", None) is not None
    s._shutdown()
    assert s._smbus is None or getattr(s._smbus, "closed", True)

def test_truncated_read_raises(monkeypatch, i2c_mapping):
    """
    If the device returns fewer bytes than requested (truncated read),
    the driver should raise WaterLevelReadError rather than silently mis-parsing.
    """
    low7 = 0x3B
    high7 = 0x3C

    # Probing responses (1-byte) must exist so address resolution succeeds
    i2c_mapping[(low7, 1)] = [0x00]
    i2c_mapping[(high7, 1)] = [0x00]

    # Truncated data: mapping for the 8-byte low read only contains 3 bytes (invalid)
    i2c_mapping[(low7, 8)] = [150, 120, 110]  # intentionally wrong length
    # Provide a valid 12-byte high block so the read begins but fails during msg creation
    i2c_mapping[(high7, 12)] = [0] * 12

    setup_fakes(monkeypatch, i2c_mapping)

    sensor = I2CWaterLevelSensor(id="trunc", bus=1, low_address=low7, high_address=high7)

    with pytest.raises(wlmod.WaterLevelReadError):
        # _collect_raw will attempt to construct the 8-byte FakeMsg and the factory will raise,
        # which our driver wraps as WaterLevelReadError.
        sensor._collect_raw()


def test_malformed_bytes_raise(monkeypatch, i2c_mapping):
    """
    If the i2c read returns non-integer/malformed byte values, the driver should raise.
    This simulates corrupted data or a broken fake.
    """
    low7 = 0x3B
    high7 = 0x3C

    i2c_mapping[(low7, 1)] = [0x00]
    i2c_mapping[(high7, 1)] = [0x00]

    # low 8 bytes include a None and a string - these should cause comparisons to fail
    i2c_mapping[(low7, 8)] = [150, None, "bad", 0, 0, 0, 0, 0]
    i2c_mapping[(high7, 12)] = [0] * 12

    setup_fakes(monkeypatch, i2c_mapping)

    sensor = I2CWaterLevelSensor(id="malf", bus=1, low_address=low7, high_address=high7)

    with pytest.raises(wlmod.WaterLevelReadError):
        sensor._collect_raw()


def test_reversed_addresses_accepted(monkeypatch, i2c_mapping):
    """
    If the config provides low_address > high_address (reversed), but both addresses
    actually respond on the bus, the driver should accept the pair as provided.
    """
    # We'll intentionally provide swapped addresses in config but make both respond.
    configured_low = 0x3C  # user accidentally swapped
    configured_high = 0x3B

    # Ensure both addresses respond to probes and to full reads
    i2c_mapping[(configured_low, 1)] = [0x00]
    i2c_mapping[(configured_high, 1)] = [0x00]
    i2c_mapping[(configured_low, 8)] = [200] * 8
    i2c_mapping[(configured_high, 12)] = [200] * 12

    setup_fakes(monkeypatch, i2c_mapping)

    # Construct sensor with reversed addresses — it should accept the exact pair if they reply
    sensor = I2CWaterLevelSensor(id="rev", bus=1, low_address=configured_low, high_address=configured_high)
    # The driver stores the resolved pair into addr_low/addr_high; because the provided pair responded,
    # it will adopt them as-is.
    assert sensor.addr_low == configured_low
    assert sensor.addr_high == configured_high

    # And the read should work and report full level (20 triggered sections)
    raw = sensor._collect_raw()
    assert raw["sections_triggered"] == 20
    assert raw["level_mm"] == pytest.approx(100.0)
