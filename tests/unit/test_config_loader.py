import os
from pathlib import Path
import pytest
from unittest.mock import patch, mock_open

from monitoring_service.config_loader import ConfigLoader


class DummyLogger:
    """Minimal logger substitute for testing."""

    def __init__(self):
        self.messages = []

    def info(self, msg):
        self.messages.append(msg)

    def warning(self, msg):
        self.messages.append(msg)

    def error(self, msg):
        self.messages.append(msg)


# ----------------------------
# Valid configuration
# ----------------------------

@patch.dict(os.environ, {"ACCESS_TOKEN": "test_token", "THINGSBOARD_SERVER": "test_server"})
@patch("monitoring_service.config_loader.ConfigLoader._resolve_config_path")
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data='{"poll_period": 10, "device_name": "TestDevice", "mount_path": "/", "log_level": "INFO"}',
)
def test_config_loader_valid(mock_file, mock_resolve_path):
    mock_resolve_path.return_value = Path("/fake/config.json")

    logger = DummyLogger()
    loader = ConfigLoader(logger)
    config = loader.as_dict()

    assert config["token"] == "test_token"
    assert config["server"] == "test_server"
    assert config["poll_period"] == 10
    assert config["device_name"] == "TestDevice"
    assert config["mount_path"] == "/"
    assert config["log_level"] == "INFO"


# ----------------------------
# Missing environment variables
# ----------------------------

@patch.dict(os.environ, {}, clear=True)
@patch("monitoring_service.config_loader.ConfigLoader._resolve_config_path")
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data='{"poll_period": 10, "device_name": "TestDevice", "mount_path": "/", "log_level": "INFO"}',
)
def test_missing_env_vars_raises_error(mock_file, mock_resolve_path):
    mock_resolve_path.return_value = Path("/fake/config.json")

    logger = DummyLogger()
    with pytest.raises(EnvironmentError):
        ConfigLoader(logger)


# ----------------------------
# Invalid poll_period
# ----------------------------

@patch.dict(os.environ, {"ACCESS_TOKEN": "test_token", "THINGSBOARD_SERVER": "test_server"})
@patch("monitoring_service.config_loader.ConfigLoader._resolve_config_path")
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data='{"poll_period": "invalid", "device_name": "TestDevice", "mount_path": "/", "log_level": "INFO"}',
)
def test_invalid_poll_period_raises_value_error(mock_file, mock_resolve_path):
    mock_resolve_path.return_value = Path("/fake/config.json")

    logger = DummyLogger()
    with pytest.raises(ValueError):
        ConfigLoader(logger)


# ----------------------------
# Missing required JSON key: device_name
# ----------------------------

@patch.dict(os.environ, {"ACCESS_TOKEN": "test_token", "THINGSBOARD_SERVER": "test_server"})
@patch("monitoring_service.config_loader.ConfigLoader._resolve_config_path")
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data='{"poll_period": 10, "mount_path": "/", "log_level": "INFO"}',
)
def test_missing_device_name_raises_key_error(mock_file, mock_resolve_path):
    mock_resolve_path.return_value = Path("/fake/config.json")

    logger = DummyLogger()
    with pytest.raises(KeyError):
        ConfigLoader(logger)


# ----------------------------
# Missing config file entirely
# ----------------------------

@patch.dict(os.environ, {"ACCESS_TOKEN": "test_token", "THINGSBOARD_SERVER": "test_server"})
@patch("monitoring_service.config_loader.ConfigLoader._resolve_config_path")
def test_missing_config_file_raises_filenotfound(mock_resolve_path):
    mock_resolve_path.side_effect = FileNotFoundError("No config found")

    logger = DummyLogger()
    with pytest.raises(FileNotFoundError):
        ConfigLoader(logger)
