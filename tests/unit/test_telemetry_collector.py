import pytest
from unittest.mock import mock_open,patch
from monitoring_service.telemetry import TelemetryCollector
from monitoring_service.sensors.ds18b20 import DS18B20Sensor


@pytest.fixture
def collector():
    sensor = DS18B20Sensor()
    return TelemetryCollector(temperature_sensor=sensor,mount_path="/")


# _get_temperature tests
mock_data = "6a 01 4b 46 7f ff 0c 10 5e : crc=5e YES\n6a 01 4b 46 7f ff 0c 10 5e t=22625\n"


@patch("builtins.open", new_callable=mock_open, read_data=mock_data)
def test_get_temperature_reads_file_correctly(mock_file):
    with open("fake/path", "r") as f:
        lines = f.readlines()
    assert lines == ["6a 01 4b 46 7f ff 0c 10 5e : crc=5e YES\n", "6a 01 4b 46 7f ff 0c 10 5e t=22625\n"]

@patch("monitoring_service.sensors.ds18b20.DS18B20Sensor.read_temp", return_value=25.0)
def test_get_temperature_returns_valid_float(mock_temp, collector):
    result = collector._get_temperature()
    assert isinstance(result, float)
    assert 12.0 <= result <= 38.0


@patch("monitoring_service.sensors.ds18b20.DS18B20Sensor.read_temp", side_effect=RuntimeError("No DS18B20 sensor found."))
def test_get_temperature_gpio_fails_gracefully(mock_sensor, collector, caplog):
    with caplog.at_level("ERROR"):
        result = collector._get_temperature()
        assert "Error getting aquarium temperature" in caplog.text
        assert result is None


# _get_water_level tests
@patch("monitoring_service.telemetry.GPIO.input", return_value=-10)
def test_get_water_level_returns_valid_int(mock_gpio, collector):
    result = collector._get_water_level(water_level_pin=4)
    assert isinstance(result, int)
    assert 0 >= result >= -100


@patch("monitoring_service.telemetry.GPIO.input", side_effect=RuntimeError("GPIO failure"))
def test_get_water_level_gpio_fails_gracefully(mock_gpio, collector, caplog):
    with caplog.at_level("ERROR"):
        result = collector._get_water_level(water_level_pin=4)
        assert "Error getting water level" in caplog.text
        assert result is None


# _get_air_temp tests
@patch("monitoring_service.telemetry.GPIO.input", return_value=25.0)
def test_get_air_temperature_returns_valid_float(mock_gpio, collector):
    result = collector._get_air_temperature(air_temperature_pin=4)
    assert isinstance(result, float)
    assert 5 <= result <= 70


@patch("monitoring_service.telemetry.GPIO.input", side_effect=RuntimeError("GPIO failure"))
def test_get_air_temperature_gpio_fails_gracefully(mock_gpio, collector, caplog):
    with caplog.at_level("ERROR"):
        result = collector._get_air_temperature(air_temperature_pin=4)
        assert "Error getting air temperature" in caplog.text
        assert result is None


# _get_air_humidity tests
@patch("monitoring_service.telemetry.GPIO.input", return_value=55.0)
def test_get_air_humidity_returns_valid_float(mock_gpio, collector):
    result = collector._get_air_humidity(air_humidity_pin=4)
    assert isinstance(result, float)
    assert 0 <= result <= 100


@patch("monitoring_service.telemetry.GPIO.input", side_effect=RuntimeError("GPIO failure"))
def test_get_air_humidity_gpio_fails_gracefully(mock_gpio, collector, caplog):
    with caplog.at_level("ERROR"):
        result = collector._get_air_humidity(air_humidity_pin=4)
        assert "Error getting air humidity" in caplog.text
        assert result is None


# _get_water_flow_rate tests
@patch("monitoring_service.telemetry.GPIO.input", return_value=200)
def test_get_water_flow_rate_returns_valid_int(mock_gpio, collector):
    result = collector._get_water_flow_rate(water_flow_rate_pin=4)
    assert isinstance(result, int)
    assert 50 <= result <= 800


@patch("monitoring_service.telemetry.GPIO.input", side_effect=RuntimeError("GPIO failure"))
def test_get_water_flow_rate_gpio_fails_gracefully(mock_gpio, collector, caplog):
    with caplog.at_level("ERROR"):
        result = collector._get_water_flow_rate(water_flow_rate_pin=4)
        assert "Error getting water flow rate" in caplog.text
        assert result is None


# _get_turbidity tests
@patch("monitoring_service.telemetry.GPIO.input", return_value=5.0)
def test_get_turbidity_returns_valid_float(mock_gpio, collector):
    result = collector._get_turbidity(turbidity_pin=4)
    assert isinstance(result, float)
    assert 0 <= result <= 100


@patch("monitoring_service.telemetry.GPIO.input", side_effect=RuntimeError("GPIO failure"))
def test_get_turbidity_gpio_fails_gracefully(mock_gpio, collector, caplog):
    with caplog.at_level("ERROR"):
        result = collector._get_turbidity(turbidity_pin=4)
        assert "Error getting turbidity" in caplog.text
        assert result is None


# as_dict tests
def test_as_dict_returns_expected_dict(collector):
    with patch("monitoring_service.telemetry.TelemetryCollector._get_temperature", return_value=26.0), \
            patch("monitoring_service.telemetry.TelemetryCollector._get_air_temperature", return_value=25.0), \
            patch("monitoring_service.telemetry.TelemetryCollector._get_air_humidity", return_value=50.0), \
            patch("monitoring_service.telemetry.TelemetryCollector._get_water_level", return_value=-10), \
            patch("monitoring_service.telemetry.TelemetryCollector._get_water_flow_rate", return_value=200), \
            patch("monitoring_service.telemetry.TelemetryCollector._get_turbidity", return_value=5.0):

        result = collector.as_dict()

        integer_keys = ["water_level", "water_flow_rate"]
        float_keys = ["temperature", "air_temperature", "air_humidity", "turbidity"]

        assert isinstance(result, dict)

        for key in integer_keys:
            assert key in result
            assert isinstance(result[key], int)

        for key in float_keys:
            assert key in result
            assert isinstance(result[key], float)


def test_as_dict_returns_expected_dict_with_none(collector):
    with patch("monitoring_service.telemetry.TelemetryCollector._get_temperature", return_value=None), \
            patch("monitoring_service.telemetry.TelemetryCollector._get_air_temperature", return_value=25.0), \
            patch("monitoring_service.telemetry.TelemetryCollector._get_air_humidity", return_value=50.0), \
            patch("monitoring_service.telemetry.TelemetryCollector._get_water_level", return_value=-10), \
            patch("monitoring_service.telemetry.TelemetryCollector._get_water_flow_rate", return_value=200), \
            patch("monitoring_service.telemetry.TelemetryCollector._get_turbidity", return_value=5.0):

        result = collector.as_dict()

        integer_keys = ["water_level", "water_flow_rate"]
        float_keys = ["air_temperature", "air_humidity", "turbidity"]
        none_keys = ["temperature"]
        assert isinstance(result, dict)

        for key in integer_keys:
            assert key in result
            assert isinstance(result[key], int)

        for key in float_keys:
            assert key in result
            assert isinstance(result[key], float)

        for key in none_keys:
            assert key in result
            assert result[key] is None
