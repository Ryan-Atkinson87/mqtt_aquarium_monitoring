# tests/hardware/test_hardware_i2c_water_level.py
import time
import pytest
import platform
from smbus3 import SMBus, i2c_msg

from monitoring_service.sensors.non_functional.i2c_water_level import (
    I2CWaterLevelSensor,
)

# Safety: only run these when explicitly requested on Pi hardware
pytestmark = pytest.mark.hardware

# Configuration for your hardware under test. Adjust if your hardware uses different addresses.
DEFAULT_BUS = 1
# Use the 7-bit addresses that your probe actually reports (confirm with i2cdetect before running).
# Common candidates based on vendor Arduino sample:
DEFAULT_LOW_ADDR_7BIT = 0x3B
DEFAULT_HIGH_ADDR_7BIT = 0x3C

# Helper: short probe using smbus to check if an address is live
def probe_address(busnum: int, addr: int, timeout_s: float = 0.5) -> bool:
    try:
        with SMBus(busnum) as bus:
            # perform a one-byte read attempt; some devices NACK instead of raising—handle OSError
            msg = i2c_msg.read(addr, 1)
            bus.i2c_rdwr(msg)
            # success if we didn't raise and got a result
            return True
    except Exception:
        return False

# Helper to skip if not running on Linux/RPi
def skip_if_not_pi():
    if platform.system() != "Linux":
        pytest.skip("Hardware tests only run on Linux (Raspberry Pi) hosts")
    # you may also add checks for CPU/board model if you want stricter gating


# 1) Smoke: device presence and basic bytes readable
@pytest.mark.hardware
def test_probe_low_and_high_addresses_present():
    """
    Preconditions:
      - Probe physically connected to Pi I2C bus DEFAULT_BUS.
      - Use i2cdetect to confirm addresses if unsure.
    Expect:
      - Both low and high addresses respond to a 1-byte probe.
    """
    skip_if_not_pi()
    bus = DEFAULT_BUS
    low = DEFAULT_LOW_ADDR_7BIT
    high = DEFAULT_HIGH_ADDR_7BIT

    assert probe_address(bus, low), f"Low address {hex(low)} not responding on /dev/i2c-{bus}"
    assert probe_address(bus, high), f"High address {hex(high)} not responding on /dev/i2c-{bus}"


# 2) Raw-read validity: returns 8 and 12 bytes and valid ranges
@pytest.mark.hardware
def test_raw_read_returns_8_and_12_bytes_and_byte_ranges():
    """
    Expect:
      - Reading 8 bytes from low and 12 from high returns lists of the correct lengths.
      - Each byte is int in 0..255.
    """
    skip_if_not_pi()
    bus = DEFAULT_BUS
    low = DEFAULT_LOW_ADDR_7BIT
    high = DEFAULT_HIGH_ADDR_7BIT

    with SMBus(bus) as sb:
        low_msg = i2c_msg.read(low, 8)
        high_msg = i2c_msg.read(high, 12)
        sb.i2c_rdwr(low_msg)
        sb.i2c_rdwr(high_msg)
        low_data = list(low_msg)
        high_data = list(high_msg)

    assert len(low_data) == 8, "Low section read not 8 bytes"
    assert len(high_data) == 12, "High section read not 12 bytes"
    for b in low_data + high_data:
        assert isinstance(b, int) and 0 <= b <= 0xFF, f"Invalid byte value {b}"


# 3) Integration: driver _collect_raw() returns mm in expected numeric range
@pytest.mark.hardware
def test_driver_collect_raw_produces_level_mm_in_range():
    """
    Expect:
      - I2CWaterLevelSensor._collect_raw returns level_mm between 0 and (20 * mm_per_section).
      - sections_triggered is 0..20.
    """
    skip_if_not_pi()
    s = I2CWaterLevelSensor(id="hw_smoke", bus=DEFAULT_BUS, low_address=DEFAULT_LOW_ADDR_7BIT, high_address=DEFAULT_HIGH_ADDR_7BIT)
    raw = s._collect_raw()
    assert "level_mm" in raw and "sections_triggered" in raw
    assert 0 <= raw["sections_triggered"] <= 20
    assert 0.0 <= raw["level_mm"] <= 100.0  # default 5 mm/section => 100 mm total
    s._shutdown()


# 4) Orientation check: when you submerge from bottom up, sections increase monotonically
@pytest.mark.hardware
def test_sections_increase_monotonic_when_probing_upwards():
    """
    Human-assisted test:
      - Start with probe dry or only bottom section wet.
      - Gradually wet the sensor upward in steps (mark water contact height).
      - At each step, confirm sections_triggered is non-decreasing and increases at expected thresholds.
    Notes:
      - This is interactive. The test only asserts monotonicity and non-zero increases.
    """
    skip_if_not_pi()
    s = I2CWaterLevelSensor(id="hw_orient", bus=DEFAULT_BUS, low_address=DEFAULT_LOW_ADDR_7BIT, high_address=DEFAULT_HIGH_ADDR_7BIT)
    prev = None
    # Allow operator to perform step changes; we'll sample up to N times with pause between steps
    samples = []
    steps = 5
    for i in range(steps):
        input(f"Step {i+1}/{steps}: adjust water level now and press Enter to capture reading...")
        raw = s._collect_raw()
        samples.append(raw["sections_triggered"])
        print(f"Captured sections_triggered: {raw['sections_triggered']}")
    # Evaluate monotonic non-decreasing
    for a, b in zip(samples, samples[1:]):
        assert b >= a, f"sections decreased from {a} -> {b}; orientation or wiring may be inverted"
    s._shutdown()


# 5) Threshold sensitivity: small splash vs sustained contact
@pytest.mark.hardware
def test_threshold_noise_vs_sustained_contact():
    """
    Purpose:
      - Verify that quick splashes produce transient changes but sustained contact yields stable reading.
    Procedure:
      - Operator performs a quick splash for ~0.5s then waits; then submerge a section and hold for 5+ seconds.
      - We sample during the transient and during the stable period.
    Expect:
      - Transient sample may flicker; stable sample should be steady for repeated reads.
    """
    skip_if_not_pi()
    s = I2CWaterLevelSensor(id="hw_noise", bus=DEFAULT_BUS, low_address=DEFAULT_LOW_ADDR_7BIT, high_address=DEFAULT_HIGH_ADDR_7BIT)

    print("Prepare a quick splash now (operator), then press Enter")
    input("Press Enter after splash...")
    # sample immediately a few times quickly
    trans = [s._collect_raw()["sections_triggered"] for _ in range(3)]
    print("Transient samples:", trans)

    print("Now submerge and hold for stable reading, then press Enter")
    input("Press Enter after stable submersion...")
    stable_samples = [s._collect_raw()["sections_triggered"] for _ in range(5)]
    print("Stable samples:", stable_samples)

    # stable samples should be equal (or within 1 section jitter)
    assert max(stable_samples) - min(stable_samples) <= 1, "Stable readings show too much jitter"
    s._shutdown()


# 6) Power cycle recovery: unplug sensor VCC then replug (manual) and confirm driver recovers
@pytest.mark.hardware
def test_power_cycle_recovery_manual():
    """
    Manual steps:
      - Operator cuts power to the sensor (or unplug connector) for ~2s, then restores.
      - After restore, run repeated reads for 30s to ensure driver recovers and returns valid bytes.
    Expect:
      - Some transient read errors may occur; ultimately ._collect_raw() returns valid structured dict
    """
    skip_if_not_pi()
    s = I2CWaterLevelSensor(id="hw_pwr", bus=DEFAULT_BUS, low_address=DEFAULT_LOW_ADDR_7BIT, high_address=DEFAULT_HIGH_ADDR_7BIT)
    print("Now power-cycle the sensor for 2-5s and press Enter when restored")
    input("Press Enter after power restored...")
    timeout = time.time() + 30
    last_err = None
    while time.time() < timeout:
        try:
            raw = s._collect_raw()
            assert "level_mm" in raw
            break
        except Exception as e:
            last_err = e
            time.sleep(1)
    else:
        pytest.fail(f"Sensor did not recover within 30s after power cycle; last error: {last_err}")
    s._shutdown()


# 7) Pull-up / bus loading check (diagnostic)
@pytest.mark.hardware
def test_bus_load_and_pullup_surface():
    """
    Diagnostic test to surface issues if pull-ups are missing or bus is noisy.
    This test performs several reads and computes mean/stddev of all bytes.
    High variance or repeated invalid reads indicate electrical issues.
    """
    skip_if_not_pi()
    s = I2CWaterLevelSensor(id="hw_pull", bus=DEFAULT_BUS, low_address=DEFAULT_LOW_ADDR_7BIT, high_address=DEFAULT_HIGH_ADDR_7BIT)
    samples = []
    for _ in range(10):
        raw = s._collect_raw()
        samples.extend(raw["raw_bytes_low"] + raw["raw_bytes_high"])
        time.sleep(0.1)
    import statistics
    std = statistics.pstdev(samples)
    mean = statistics.mean(samples)
    print(f"mean={mean:.2f} stddev={std:.2f}")
    # heuristics: if stddev is extremely high (>60) it may indicate noise; fail to draw attention
    assert std < 60, f"High noise on I2C bus: stddev={std:.2f}"
    s._shutdown()


# 8) Long read stability: repeated reads for N seconds
@pytest.mark.hardware
def test_long_read_stability():
    """
    Perform repeated reads for a period (e.g., 60s) and ensure no resource leak and acceptable failure rate.
    Expect:
      - < 5% of reads fail (exceptions).
      - No file descriptor exhaustion (OS-level). This is mostly a smoke test.
    """
    skip_if_not_pi()
    s = I2CWaterLevelSensor(id="hw_long", bus=DEFAULT_BUS, low_address=DEFAULT_LOW_ADDR_7BIT, high_address=DEFAULT_HIGH_ADDR_7BIT)
    duration = 30
    end = time.time() + duration
    successes = 0
    failures = 0
    while time.time() < end:
        try:
            _ = s._collect_raw()
            successes += 1
        except Exception:
            failures += 1
        time.sleep(0.2)
    total = successes + failures
    failure_rate = failures / total if total else 1.0
    print(f"Successes={successes} Failures={failures} Failure_rate={failure_rate:.2%}")
    assert failure_rate < 0.05, f"High failure rate during long-read: {failure_rate:.2%}"
    s._shutdown()


# 9) Collector integration (manual / local): verify health publishing and mapping
@pytest.mark.hardware
def test_collector_integration_health_and_mapping():
    """
    Integration test outline (depends on your TelemetryCollector):
      - Instantiate your TelemetryCollector with this sensor configured.
      - Let it run for a short period and inspect published telemetry for keys:
          - 'water_level_mm', optionally 'water_level_pct', 'wl_failures', 'wl_read_age_ms'
      - Assert telemetry values exist and types are numeric / int as expected.
    This test is intentionally high-level and will need to be adapted to your collector API.
    """
    skip_if_not_pi()
    pytest.skip("Collector integration test - adapt to your collector and run manually.")


# 10) Cleanup idempotency
@pytest.mark.hardware
def test_shutdown_idempotent():
    skip_if_not_pi()
    s = I2CWaterLevelSensor(id="hw_shutdown", bus=DEFAULT_BUS, low_address=DEFAULT_LOW_ADDR_7BIT, high_address=DEFAULT_HIGH_ADDR_7BIT)
    s._shutdown()
    # second call should not raise
    s._shutdown()
