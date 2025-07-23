import pytest
from unittest.mock import patch, MagicMock
from monitoring_service.TBClientWrapper import TBClientWrapper


@pytest.fixture
def dummy_logger():
    class DummyLogger:
        def error(self, msg):
            print(f"LOG ERROR: {msg}")

        def warning(self, msg):
            print(f"LOG WARNING: {msg}")

    return DummyLogger()


@pytest.fixture
def client(dummy_logger):
    return TBClientWrapper(tb_server="test_server", tb_token="test_token", logger=dummy_logger)


def test_connect_success(dummy_logger):
    mock_client = MagicMock()
    client = TBClientWrapper("server", "token", dummy_logger, client_class=lambda *args, **kwargs: mock_client)
    client.connect()
    mock_client.connect.assert_called_once()


@patch("monitoring_service.TBClientWrapper.TBDeviceMqttClient")
def test_connect_failure_logs_and_raises(mock_mqtt, client):
    mock_mqtt.return_value.connect.side_effect = Exception("connection failed")

    with pytest.raises(Exception):
        client.connect()


@patch("monitoring_service.TBClientWrapper.TBDeviceMqttClient")
def test_send_telemetry_skips_empty(mock_mqtt, client):
    client.send_telemetry({})
    mock_mqtt.return_value.send_telemetry.assert_not_called()


def test_send_telemetry_success(dummy_logger):
    mock_client = MagicMock()
    client = TBClientWrapper("server", "token", dummy_logger, client_class=lambda *args, **kwargs: mock_client)
    client.send_telemetry({"cpu": 50})
    mock_client.send_telemetry.assert_called_once()


def test_send_attributes_success(dummy_logger):
    mock_client = MagicMock()
    client = TBClientWrapper("server", "token", dummy_logger, client_class=lambda *args, **kwargs: mock_client)
    client.send_attributes({"device_name": "test_device"})
    mock_client.send_attributes.assert_called_once_with({"device_name": "test_device"})


def test_disconnect_success(dummy_logger):
    mock_client = MagicMock()
    client = TBClientWrapper("server", "token", dummy_logger, client_class=lambda *args, **kwargs: mock_client)
    client.disconnect()
    mock_client.disconnect.assert_called_once()
