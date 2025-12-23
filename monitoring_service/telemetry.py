"""
telemetry.py

Provides the TelemetryCollector class, responsible for collecting telemetry from
configured sensor bundles. The collector applies per-bundle timing, key mapping,
calibration, smoothing, and range filtering before returning a flattened
telemetry dictionary.
"""

import time
from collections.abc import Mapping
from typing import Any

import logging
from monitoring_service import PACKAGE_LOGGER_NAME
from monitoring_service.sensors.factory import SensorBundle

logger = logging.getLogger(f"{PACKAGE_LOGGER_NAME}.telemetry")


class TelemetryCollector:
    """
    Collect telemetry from a set of SensorBundle instances.

    For each bundle, the collector enforces read intervals, invokes the sensor
    driver, and applies optional key mapping, calibration, smoothing, and range
    filtering before returning a combined telemetry payload.
    """
    def __init__(self, *, bundles: list[SensorBundle] = None):
        """
        Initialize the collector with an optional list of sensor bundles.

        Args:
            bundles (list[SensorBundle], optional): Sensor bundles to collect
            telemetry from.
        """
        self._bundles = bundles or []
        self._last_read: dict[str, float] = {}
        self._ema: dict[tuple[str, str], float] = {}

    @staticmethod
    def _bundle_id(bundle) -> str:
        """
        Build a stable identifier string for a sensor bundle based on the driver
        type and available identifying attributes.
        """
        driver = bundle.driver
        driver_name = driver.__class__.__name__
        identifier = (
            getattr(driver, "id", None)
            or getattr(driver, "sensor_id", None)
            or getattr(driver, "path", None)
            or getattr(driver, "device_file", None)
            or getattr(driver, "pin", None)
            or hex(id(bundle))
        )
        return f"{driver_name}:{identifier}"

    def _is_due(self, bundle_id: str, now: float, interval: int | None = None) -> bool:
        """
        Determine whether a bundle is due for collection based on its interval
        and last read time.
        """
        if not interval or interval <= 0:
            return True
        last = self._last_read.get(bundle_id)
        if last is None:
            return True
        return (now - last) >= interval

    @staticmethod
    def _map_keys(bundle, raw: Mapping[str, Any]) -> dict:
        """
        Map raw sensor keys to canonical telemetry keys using the bundle key map.
        """
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
        """
        Apply linear calibration to mapped telemetry values where configured.
        """
        calibrated_dict = {}
        calibration = getattr(bundle, "calibration", {}) or {}
        for raw_key, raw_value in mapped.items():
            if raw_key in calibration and isinstance(raw_value, (int, float)):
                slope = calibration[raw_key].get("slope", 1.0)
                offset = calibration[raw_key].get("offset", 0.0)
                calibrated_dict[raw_key] = (raw_value * slope) + offset
            else:
                calibrated_dict[raw_key] = raw_value
        return calibrated_dict

    def _apply_smoothing(self, bundle, calibrated: dict) -> dict:
        """
        Apply exponential moving average smoothing to telemetry values where
        configured.
        """
        smoothed_dict = {}
        uid = self._bundle_id(bundle)
        smoothing = getattr(bundle, "smoothing", {}) or {}
        for key, value in calibrated.items():
            window = smoothing.get(key)
            if not isinstance(value, (int, float)) or window is None or window < 2:
                smoothed_dict[key] = value
                continue
            prev = self._ema.get((uid, key))
            if prev is None:
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
        """
        Filter telemetry values based on configured minimum and maximum ranges.
        """
        ranged_dict = {}
        ranges = getattr(bundle, "ranges", {}) or {}
        for raw_key, raw_value in smoothed.items():
            if raw_key in ranges and isinstance(raw_value, (int, float)):
                min_value = ranges[raw_key].get("min", float("-inf"))
                max_value = ranges[raw_key].get("max", float("inf"))
                if min_value <= raw_value <= max_value:
                    ranged_dict[raw_key] = raw_value
            else:
                ranged_dict[raw_key] = raw_value
        return ranged_dict

    def as_dict(self) -> dict[str, Any]:
        """
        Collect telemetry from all due sensor bundles and return a flattened
        telemetry dictionary.
        """
        telemetry_data = {}
        now = time.time()
        for bundle in self._bundles:
            bundle_id = self._bundle_id(bundle)
            interval = getattr(bundle, "interval", None)
            if not self._is_due(bundle_id=bundle_id, now=now, interval=interval):
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
            telemetry_data.update(ranged)
        return telemetry_data
