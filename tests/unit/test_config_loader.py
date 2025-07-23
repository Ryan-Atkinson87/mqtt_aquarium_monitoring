import os
import pytest
from unittest.mock import patch, mock_open
from monitoring_service.config_loader import ConfigLoader


class DummyLogger:
    """A simple logger substitute for testing."""

    def __init__(self):
        self.messages = []

    def error(self, msg):
        self.messages.append(msg)
        print(f"LOG: {msg}")


# ✅ Test: All required environment variables and config values are present and valid
@patch.dict(os.environ, {"ACCESS_TOKEN": "test_token", "THINGSBOARD_SERVER": "test_server"})
@patch("builtins.open", new_callable=mock_open,
       read_data='{"poll_period": 10, "device_name": "Test", "mount_path": "/", "log_level": "INFO"}')
def test_config_loader_valid(mock_file):
    logger = DummyLogger()
    config_loader = ConfigLoader(logger)
    config = config_loader.as_dict()

    assert config["token"] == "test_token"
    assert config["server"] == "test_server"
    assert config["poll_period"] == 10
    assert config["device_name"] == "Test"
    assert config["mount_path"] == "/"
    assert config["log_level"] == "INFO"


# ❌ Test: Missing required environment variables should raise EnvironmentError
@patch.dict(os.environ, {}, clear=True)
@patch("builtins.open", new_callable=mock_open,
       read_data='{"poll_period": 10, "device_name": "Test", "mount_path": "/", "log_level": "INFO"}')
def test_missing_env_vars_raises_error(mock_file):
    logger = DummyLogger()
    with pytest.raises(EnvironmentError):
        ConfigLoader(logger)


# ❌ Test: Invalid (non-integer) poll_period value should raise ValueError
@patch.dict(os.environ, {"ACCESS_TOKEN": "test_token", "THINGSBOARD_SERVER": "test_server"})
@patch("builtins.open", new_callable=mock_open,
       read_data='{"poll_period": "invalid", "device_name": "Test", "mount_path": "/", "log_level": "INFO"}')
def test_invalid_poll_period_raises_error(mock_file):
    logger = DummyLogger()
    with pytest.raises(ValueError):
        ConfigLoader(logger)


# ❌ Test: Missing a required config key (device_name) should raise KeyError
@patch.dict(os.environ, {"ACCESS_TOKEN": "test_token", "THINGSBOARD_SERVER": "test_server"})
@patch("builtins.open", new_callable=mock_open,
       read_data='{"poll_period": 10, "mount_path": "/", "log_level": "INFO"}')  # device_name is missing
def test_missing_required_json_key_raises_error(mock_file):
    logger = DummyLogger()
    with pytest.raises(KeyError):
        ConfigLoader(logger)
