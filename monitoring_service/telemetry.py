"""
telemetry.py

# TODO: Update this doc string

Provides the TelemetryCollector class, which gathers system metrics from a
Raspberry Pi or other Linux-based device. These metrics include CPU usage,
CPU temperature, GPU temperature, RAM usage, and disk usage.

All metrics are returned as a dictionary of telemetry data, along with a list
of any errors encountered during collection. This data is intended for use
with IoT platforms such as ThingsBoard.

Classes:
    TelemetryCollector

Usage:
    collector = TelemetryCollector()
    telemetry, errors = collector.get_telemetry()
"""


import time
from collections.abc import Mapping
from typing import Any

# Set up logging
import logging
from monitoring_service import PACKAGE_LOGGER_NAME
from monitoring_service.sensors.factory import SensorBundle

logger = logging.getLogger(f"{PACKAGE_LOGGER_NAME}.telemetry")

class TelemetryCollector:
    """
    Manges the collection of telemetry from a bundle sensors.
    Uses as_dict to return a dictionary of telemetry data.
    """
    def __init__(self, *, bundles:list[SensorBundle] = None):
        self._bundles = bundles
        if self._bundles is None:
            self._bundles = []
        self._last_read: dict[str, float] = {}
        self._ema: dict[tuple[str,str], float] = {}

    @staticmethod
    def _bundle_id(bundle) -> str:
        driver = bundle.driver
        driver_name = driver.__class__.__name__
        identifier = (
                getattr(driver, "id", None)
                or getattr(driver, "path", None)
                or getattr(driver, "pin", None)
                or hex(id(bundle))
        )
        return f"{driver_name}:{identifier}"

    def _is_due(self, bundle_id: str, now: float, interval: int | None = None) -> bool:
        if not interval or interval <= 0:
            return True
        last = self._last_read.get(bundle_id)
        if last is None:
            return True
        return (now - last) >= interval

    @staticmethod
    def _map_keys(bundle, raw: Mapping[str, Any]) -> dict:
        key_map = getattr(bundle, "keys", {}) or {}
        mapped_keys = {}
        for raw_key, value in raw.items():
            if raw_key in key_map:
                mapped_keys[key_map[raw_key]] = value
            else:
                logger.debug(f"Unmapped key '{raw_key}' from {bundle.driver.__class__.__name__}")

        return mapped_keys

    @staticmethod
    def _apply_calibration(bundle, mapped: dict) -> dict:
        calibrated_dict = {}
        calibration = getattr(bundle, "calibration", {}) or {}
        for raw_key, raw_value in mapped.items():
            if raw_key in calibration:
                if isinstance(raw_value, (int, float)):
                    slope = calibration[raw_key].get("slope", 1.0)
                    offset = calibration[raw_key].get("offset", 0.0)
                    calibrated_value = (raw_value * slope) + offset
                    calibrated_dict[raw_key] = calibrated_value
                else:
                    calibrated_dict[raw_key] = raw_value
                    logger.debug(f"None number '{raw_value}' from {bundle.driver.__class__.__name__}")
            else:
                calibrated_dict[raw_key] = raw_value

        return calibrated_dict

    def _apply_smoothing(self, bundle, calibrated: dict) -> dict:
        smoothed_dict = {}
        uid = self._bundle_id(bundle)
        smoothing = getattr(bundle, "smoothing", {}) or {}

        for key, value in calibrated.items():
            window = smoothing.get(key)

            # Pass through if non-numeric or no valid window
            if not isinstance(value, (int, float)) or window is None or window < 2:
                smoothed_dict[key] = value
                continue

            prev = self._ema.get((uid, key))
            if prev is None:
                # Seed EMA with the first value
                self._ema[(uid, key)] = value
                smoothed_dict[key] = value
                continue

            alpha = 2 / (window + 1)
            smoothed = (alpha * value) + ((1 - alpha) * prev)
            self._ema[(uid, key)] = smoothed
            smoothed_dict[key] = smoothed

        return smoothed_dict

    @staticmethod
    def _apply_ranges(bundle, smoothed: dict) -> dict:
        ranged_dict = {}
        ranges = getattr(bundle, "ranges", {}) or {}

        for raw_key, raw_value in smoothed.items():
            if raw_key in ranges:
                if isinstance(raw_value, (int, float)):
                    min_value = ranges[raw_key].get("min", float("-inf"))
                    max_value = ranges[raw_key].get("max", float("inf"))
                    if min_value <= raw_value <= max_value:
                        ranged_dict[raw_key] = raw_value
                    else:
                        logger.debug(f"Value outside of range '{raw_value}' from {bundle.driver.__class__.__name__}")
                else:
                    ranged_dict[raw_key] = raw_value
                    logger.debug(f"None number '{raw_value}' from {bundle.driver.__class__.__name__}")
            else:
                ranged_dict[raw_key] = raw_value

        return ranged_dict

    def as_dict(self) -> dict[str, Any]:
        telemetry_data = {}
        now = time.time()

        for bundle in self._bundles:
            bundle_id = self._bundle_id(bundle)
            bundle_interval = getattr(bundle, "interval", None)

            read_now = self._is_due(bundle_id=bundle_id, now=now, interval=bundle_interval)
            if not read_now:
                continue

            try:
                raw = bundle.driver.read()
            except Exception as e:
                logger.warning(f"Read failed for {bundle_id}: {e}")
                continue

            mapped = self._map_keys(bundle, raw)
            calibrated = self._apply_calibration(bundle, mapped)
            smoothed = self._apply_smoothing(bundle, calibrated)
            ranged = self._apply_ranges(bundle, smoothed)

            self._last_read[bundle_id] = now

            for key, value in ranged.items():
                telemetry_data[key] = value

        return telemetry_data

