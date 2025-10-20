"""
config_loader.py

Loads environment + JSON configuration and exposes a merged dict.
- Env: .env (ACCESS_TOKEN, THINGSBOARD_SERVER)
- JSON: config.json (path via CONFIG_PATH/AQUARIUM_CONFIG or common defaults)

Usage:
    config = ConfigLoader(logger).as_dict()
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv


def _safe_log(logger, level: str, msg: str) -> None:
    """Log without exploding if logger is None."""
    if logger is None:
        return
    getattr(logger, level.lower(), logger.info)(msg)


def _project_root() -> Path:
    # monitoring_service/ -> parent is repo root
    return Path(__file__).resolve().parent.parent


def _find_config_path(logger=None) -> Optional[Path]:
    """Resolve config.json path from env or sensible defaults."""
    # 1) Env overrides
    for key in ("CONFIG_PATH", "AQUARIUM_CONFIG"):
        p = os.environ.get(key)
        if p:
            path = Path(p).expanduser().resolve()
            if path.is_file():
                _safe_log(logger, "info", f"ConfigLoader: using {key}={path}")
                return path
            _safe_log(logger, "warning", f"ConfigLoader: {key} set but not a file: {path}")

    # 2) Common locations (in priority order)
    candidates = [
        Path.cwd() / "config.json",                       # run dir
        _project_root() / "config.json",                  # repo root
        _project_root() / "config" / "config.json",       # repo/config/config.json
    ]
    for c in candidates:
        if c.is_file():
            _safe_log(logger, "info", f"ConfigLoader: discovered config at {c}")
            return c

    _safe_log(logger, "warning", "ConfigLoader: no config.json found via env or defaults")
    return None


def _load_json_config(path: Optional[Path], logger=None) -> Dict[str, Any]:
    if not path:
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        _safe_log(logger, "error", f"ConfigLoader: failed reading {path}: {e}")
        return {}


class ConfigLoader:
    """
    Loads env + JSON, validates required fields, and returns a merged dict via as_dict().

    Required env:
      - ACCESS_TOKEN
      - THINGSBOARD_SERVER

    JSON keys (examples):
      - poll_period (int ≥ 1)
      - device_name (str)
      - mount_path (str)
      - log_level (str, default "INFO")
      - sensors (list)  <-- merged in; not strictly required here
    """

    def __init__(self, logger):
        load_dotenv()
        self.logger = logger

        # Required env
        self.token = os.getenv("ACCESS_TOKEN")
        self.server = os.getenv("THINGSBOARD_SERVER")

        # Find + load JSON
        self.config_path: Optional[Path] = _find_config_path(self.logger)
        self.config: Dict[str, Any] = _load_json_config(self.config_path, self.logger)

        # Validate env before touching JSON-derived fields
        self._validate_or_raise()

        # Parse core fields from JSON (with validation/defaults)
        self.poll_period = self._get_poll_period()
        self.device_name = self._get_device_name()
        self.mount_path = self._get_mount_path()
        self.log_level = self._get_log_level()

    def as_dict(self) -> Dict[str, Any]:
        """
        Return the merged configuration dict.
        Env values win if both sources provide the same key.
        """
        merged: Dict[str, Any] = {
            "token": self.token,
            "server": self.server,
            "poll_period": self.poll_period,
            "device_name": self.device_name,
            "mount_path": self.mount_path,
            "log_level": self.log_level,
        }

        # Include everything else from JSON that wasn't already set,
        # notably 'sensors' and any future top-level keys.
        for k, v in self.config.items():
            if k not in merged or merged[k] in (None, "", []):
                merged[k] = v

        # Visibility
        _safe_log(self.logger, "info", f"ConfigLoader: keys loaded: {list(merged.keys())}")
        _safe_log(self.logger, "info", f"ConfigLoader: sensors present: {'sensors' in merged and bool(merged.get('sensors'))}")
        return merged

    # ----------------- internal validation/parsers -----------------

    def _validate_or_raise(self) -> None:
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
        try:
            val = self.config["device_name"]
            if not isinstance(val, str) or not val.strip():
                raise ValueError("device_name must be a non-empty string")
            return val
        except KeyError:
            _safe_log(self.logger, "error", "Missing required config: device_name")
            raise
        except (ValueError, TypeError) as e:
            _safe_log(self.logger, "error", f"Invalid device_name: {self.config.get('device_name')} ({e})")
            raise

    def _get_mount_path(self) -> str:
        try:
            val = self.config["mount_path"]
            if not isinstance(val, str) or not val:
                raise ValueError("mount_path must be a string")
            return val
        except KeyError:
            _safe_log(self.logger, "error", "Missing required config: mount_path")
            raise
        except (ValueError, TypeError) as e:
            _safe_log(self.logger, "error", f"Invalid mount_path: {self.config.get('mount_path')} ({e})")
            raise

    def _get_log_level(self) -> str:
        val = self.config.get("log_level", "INFO")
        try:
            return str(val)
        except (ValueError, TypeError) as e:
            _safe_log(self.logger, "error", f"Invalid log_level: {val} ({e})")
            raise
