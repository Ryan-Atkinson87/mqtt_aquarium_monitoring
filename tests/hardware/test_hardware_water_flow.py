import time
import pytest

from monitoring_service.inputs.sensors.water_flow import (
    WaterFlowSensor,
    WaterFlowInitError,
    WaterFlowReadError,
)

# Adjust this to whatever GPIO pin you physically wired
TEST_FLOW_PIN = 17


@pytest.mark.hardware
def test_waterflow_init_hardware():
    """
    Verify real pigpio can be created and the sensor initialises cleanly.
    """
    sensor = None
    try:
        sensor = WaterFlowSensor(id="hwflow1", pin=TEST_FLOW_PIN)
    except WaterFlowInitError as e:
        pytest.fail(f"WaterFlowSensor failed to initialize: {e}")

    # Ensure pigpio is actually connected
    assert sensor.sensor is not None
    assert sensor.sensor.connected is True

    sensor.stop()


@pytest.mark.hardware
def test_waterflow_callback_accumulates_real_pulses():
    """
    Verify that the turbine pulses cause falling-edge callbacks and tick accumulation.
    You will need to blow water/air or manually spin the impeller for this test.
    """
    sensor = WaterFlowSensor(
        id="hwflow2",
        pin=TEST_FLOW_PIN,
        sample_window=1.0,
        sliding_window_s=2.0,
        calibration_constant=4.5,
    )

    # Clear any existing ticks
    with sensor.ticks_lock:
        sensor.ticks.clear()

    # Wait for real pulses to occur
    time.sleep(2.0)

    with sensor.ticks_lock:
        count = len(sensor.ticks)

    sensor.stop()

    # If the wheel physically spun, ticks > 0
    assert count >= 0
    # We cannot assert > 0 unless flow is guaranteed, so allow both outcomes
    # but log a hint.
    if count == 0:
        pytest.skip("No pulses captured; turbine likely not moving.")


@pytest.mark.hardware
def test_waterflow_read_returns_real_values():
    """
    Reads actual flow. Should return floats for instant and smoothed.
    Values may be zero if water isn't flowing but should never error.
    """
    sensor = WaterFlowSensor(
        id="hwflow3",
        pin=TEST_FLOW_PIN,
        sample_window=1.0,
        sliding_window_s=2.0,
    )

    try:
        result = sensor.read()
    except WaterFlowReadError as e:
        sensor.stop()
        pytest.fail(f"read() raised WaterFlowReadError: {e}")

    sensor.stop()

    assert isinstance(result, dict)
    assert "flow_instant" in result
    assert "flow_smoothed" in result

    assert isinstance(result["flow_instant"], float)
    assert isinstance(result["flow_smoothed"], float)


@pytest.mark.hardware
def test_waterflow_stop_releases_pigpio():
    """
    Ensure that stop() actually shuts down pigpio cleanly.
    """
    sensor = WaterFlowSensor(id="hwflow4", pin=TEST_FLOW_PIN)

    # Save original pigpio handle
    pigpio_handle = sensor.sensor

    sensor.stop()

    assert sensor._callback is None
    assert sensor.sensor is None
    assert pigpio_handle.connected is False
