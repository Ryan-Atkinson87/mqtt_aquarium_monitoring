"""
config_loader.py

Load configuration from environment variables and an optional JSON config file.
The loader validates required environment values and exposes a merged
configuration dictionary via as_dict().

If a config.json file cannot be located or loaded, an empty configuration is
used. Startup currently fails only if required environment variables are
missing.

Classes:
    ConfigLoader

Usage:
    loader = ConfigLoader(logger)
    config = loader.as_dict()
"""

# TODO: config loader doesn't currently fail when no config is available, fix this.

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict, Optional

ETC_CONFIG_PATH = Path("/etc/trive_aquasense/config.json")
DEFAULT_CONFIG_FILENAME = "config.json"


def _safe_log(logger, level: str, msg: str) -> None:
    """
    Log a message using the provided logger while safely handling missing or
    nonstandard logger implementations.
    """

    if logger is None:
        return
    fn = getattr(logger, level.lower(), None)
    if callable(fn):
        try:
            fn(msg)
        except Exception:
            pass

def _load_json_config(path: Optional[Path], logger=None) -> Dict[str, Any]:
    """
    Load JSON configuration from the given file path.

    Returns an empty dict if the file cannot be read.
    """
    if not path:
        raise FileNotFoundError("ConfigLoader: config path was not resolved")
    try:
        with open(path, "r") as file:  # <- use builtins.open so tests can mock it
            return json.load(file)
    except Exception as e:
        _safe_log(logger, "error", f"ConfigLoader: failed reading {path}: {e}")
        raise


class ConfigLoader:
    """
    Load and validate configuration from environment variables and an optional
    JSON config file.

    Required environment variables:
        ACCESS_TOKEN
        THINGSBOARD_SERVER

    JSON:
        If present, a config.json file may define core configuration values such as
        device_name and mount_path.

    JSON keys (examples):
      - poll_period (int ≥ 1)
      - device_name (str)
      - mount_path (str)
      - log_level (str, default "INFO")
      - sensors (list)
    """


    # TODO: config loader doesn't currently fail when no config is available, fix this.

    def __init__(self, logger):
        """
        Initialize the loader, read environment variables, attempt to load a JSON
        config file, and parse core configuration fields.

        Args:
            logger (Logger): Logger instance for diagnostic output.
        """

        self.logger = logger

        self.token = os.getenv("ACCESS_TOKEN")
        self.server = os.getenv("THINGSBOARD_SERVER")

        # Resolve and load config.json (hard fail if missing or unreadable)
        self.config_path = self._resolve_config_path()
        self.config = _load_json_config(self.config_path, self.logger)

        self._validate_or_raise()

        self.poll_period = self._get_poll_period()
        self.device_name = self._get_device_name()
        self.mount_path = self._get_mount_path()
        self.log_level = self._get_log_level()

    def as_dict(self) -> Dict[str, Any]:
        """
        Return the merged configuration dictionary with environment variables
        taking precedence over JSON values.
        """
        merged: Dict[str, Any] = {
            "token": self.token,
            "server": self.server,
            "poll_period": self.poll_period,
            "device_name": self.device_name,
            "mount_path": self.mount_path,
            "log_level": self.log_level,
        }

        for key, value in self.config.items():
            if key not in merged or merged[key] in (None, "", []):
                merged[key] = value

        _safe_log(self.logger, "info", f"ConfigLoader: keys loaded: {list(merged.keys())}")
        _safe_log(self.logger, "info",
                  f"ConfigLoader: sensors present: {'sensors' in merged and bool(merged.get('sensors'))}")
        _safe_log(
            self.logger,
            "info",
            f"ConfigLoader: displays present: {'displays' in merged and bool(merged.get('displays'))}",
        )

        return merged

    def _validate_or_raise(self) -> None:
        """
        Validate that required environment variables are present.

        Raises:
            EnvironmentError: If required environment variables are missing.
        """
        missing = []
        if not self.token:
            missing.append("ACCESS_TOKEN")
        if not self.server:
            missing.append("THINGSBOARD_SERVER")
        if missing:
            msg = f"Missing required environment variables: {', '.join(missing)}"
            _safe_log(self.logger, "error", msg)
            raise EnvironmentError(msg)

    def _get_poll_period(self) -> int:
        """
        Parse and return the poll_period value from the JSON config.

        Returns:
            int: Polling interval in seconds.

        Raises:
            ValueError: If poll_period is invalid.
        """
        raw_value = self.config.get("poll_period", 60)
        try:
            poll = int(raw_value)
            if poll < 1:
                raise ValueError("poll_period must be ≥ 1")
            return poll
        except (ValueError, TypeError) as e:
            _safe_log(self.logger, "error", f"Invalid poll_period: {raw_value} ({e})")
            raise

    def _get_device_name(self) -> str:
        """
        Retrieve and validate the device_name from the JSON config.

        Returns:
            str: The configured device name.

        Raises:
            KeyError: If device_name is missing.
            ValueError: If device_name is invalid.
        """
        try:
            value = self.config["device_name"]
            if not isinstance(value, str) or not value.strip():
                raise ValueError("device_name must be a non-empty string")
            return value
        except KeyError:
            _safe_log(self.logger, "error", "Missing required config: device_name")
            raise
        except (ValueError, TypeError) as e:
            _safe_log(self.logger, "error", f"Invalid device_name: {self.config.get('device_name')} ({e})")
            raise

    def _resolve_config_path(self) -> Path:
        env_path = os.getenv("CONFIG_PATH")
        if env_path:
            path = Path(env_path).expanduser().resolve()
            if path.is_file():
                self.logger.info(f"ConfigLoader: using config from CONFIG_PATH env var: {path}")
                return path
            raise FileNotFoundError(f"CONFIG_PATH set but file does not exist: {path}")

        if ETC_CONFIG_PATH.is_file():
            self.logger.info(f"ConfigLoader: using config from {ETC_CONFIG_PATH}")
            return ETC_CONFIG_PATH

        project_root = Path.cwd()
        local_path = project_root / DEFAULT_CONFIG_FILENAME
        if local_path.is_file():
            self.logger.warning(
                f"ConfigLoader: using local dev config at {local_path} (NOT /etc)"
            )
            return local_path

        raise FileNotFoundError(
            "ConfigLoader: no config.json found via CONFIG_PATH, /etc, or project directory"
        )

    def _get_mount_path(self) -> str:
        """
        Retrieve and validate the mount_path from the JSON config.

        Returns:
            str: The configured mount path.

        Raises:
            KeyError: If mount_path is missing.
            ValueError: If mount_path is invalid.
        """
        try:
            value = self.config["mount_path"]
            if not isinstance(value, str) or not value:
                raise ValueError("mount_path must be a string")
            return value
        except KeyError:
            _safe_log(self.logger, "error", "Missing required config: mount_path")
            raise
        except (ValueError, TypeError) as e:
            _safe_log(self.logger, "error", f"Invalid mount_path: {self.config.get('mount_path')} ({e})")
            raise

    def _get_log_level(self) -> str:
        """
        Retrieve the log_level from the JSON config or default to "INFO".

        Returns:
            str: The configured logging level.
        """
        value = self.config.get("log_level", "INFO")
        try:
            return str(value)
        except (ValueError, TypeError) as e:
            _safe_log(self.logger, "error", f"Invalid log_level: {value} ({e})")
            raise
