# factory.py

"""
What factory.py owns

A registry mapping sensor type → driver class (e.g., "ds18b20" → DS18B20Sensor).

Logic to build a driver from a single validated config entry.

Validation that metadata (keys, calibration, ranges, smoothing, interval) is coherent.

It returns a bundle that the collector can use without knowing driver internals.
"""

from typing import Optional
from monitoring_service.sensors import ds18b20
from dataclasses import dataclass, field
from monitoring_service.sensors.base import BaseSensor
from monitoring_service.exceptions import (InvalidSensorConfigError, UnknownSensorTypeError, FactoryError)

# Set up logging
from monitoring_service import PACKAGE_LOGGER_NAME
import logging
logger = logging.getLogger(f"{PACKAGE_LOGGER_NAME}.{__name__.split('.')[-1]}")

@dataclass
class SensorBundle:
    # The constructed driver (e.g., DS18B20Sensor())
    driver: BaseSensor
    # Maps driver outputs → canonical keys
    keys: dict[str, str] = field(default_factory=dict)
    # Calibration config per canonical key
    calibration: dict[str, dict[str,float]] = field(default_factory=dict)
    # Range limits per canonical key
    ranges: dict[str, dict[str,int]] = field(default_factory=dict)
    # Smoothing config per canonical key
    smoothing: dict[str, int] = field(default_factory=dict)
    # Optional read frequency
    interval: Optional[int] = None

class SensorFactory:
    def __init__(self, registry: dict[str, type[BaseSensor]] | None = None):
        if registry is None:
            self._registry = {
                "ds18b20": ds18b20.DS18B20Sensor,
            }
        else:
            self._registry = registry

    def register(self, sensor_type: str, driver_class: type[BaseSensor]):
        """
        Adds/overrides an entry in the registry.
        Use at startup to register built-in drivers (e.g., DS18B20), and later for additional drivers.
        """
        if not isinstance(sensor_type, str):
            raise InvalidSensorConfigError("sensor_type must be a string")

        sensor_type = sensor_type.strip().lower()
        if not sensor_type:
            raise InvalidSensorConfigError("sensor_type cannot be empty or whitespace")

        if not issubclass(driver_class, BaseSensor):
            raise InvalidSensorConfigError("driver_class must be a subclass of BaseSensor")

        old_driver = self._registry.get(sensor_type)
        if old_driver is not None:
            logger.warning(
                f"Overriding driver for '{sensor_type}': "
                f"{old_driver.__name__} → {driver_class.__name__}"
            )

        self._registry[sensor_type] = driver_class

    def build(self, sensor_config):
        """
        Input: one validated sensor config block (dict-like).
        Steps (conceptual):
        - Extract type, keys, calibration, ranges, smoothing, interval, plus driver-specific params (id, pins, path, etc.).
        - Lookup driver class in the registry; if missing → UnknownSensorTypeError.
        - Check keys exists and is non-empty; else → InvalidSensorConfigError.
        - Validate that calibration/ranges/smoothing reference only canonical keys present in keys.values(). If not → InvalidSensorConfigError.
        - Validate driver-specific required fields (e.g., DS18B20 needs id or allows auto-discovery with path; GPIO drivers need pin). If missing → InvalidSensorConfigError.
        - Construct the driver with only the params it needs (don’t pass the whole config blindly).
        - Normalize optional metadata: if calibration/ranges/smoothing/interval are absent, set to {}/None.
        - Return a SensorBundle with the driver + metadata.
        Output: a ready-to-use SensorBundle.
        """

        sensor_type = sensor_config.get("type")
        if not isinstance(sensor_type, str) or not sensor_type.strip():
            raise InvalidSensorConfigError("Missing or invalid 'type' in sensor configuration")
        sensor_type = sensor_type.strip().lower()

        keys_map = sensor_config.get("keys")
        if not isinstance(keys_map, dict) or not keys_map:
            raise InvalidSensorConfigError("Missing or invalid 'keys' in sensor configuration")

        canonical = set(keys_map.values())

        calibration_map = sensor_config.get("calibration") or {}
        for key, cal in calibration_map.items():
            # check key is a non-empty string
            if not isinstance(key, str) or not key.strip():
                raise InvalidSensorConfigError(f"'{key}' in calibration_map must be a string.")
            # check key is in keys_map
            if key not in canonical:
                raise InvalidSensorConfigError(f"metadata references unknown canonical key '{key}' in calibration_map")
            # check for a dictionary value
            if not isinstance(cal, dict):
                raise InvalidSensorConfigError(f"Calibration for '{key}' must be a dict with 'offset' and 'slope'")
            # check correct keys are in dictionary
            if "offset" not in cal or "slope" not in cal:
                raise InvalidSensorConfigError(f"Calibration for '{key}' must include 'offset' and 'slope'")
            # check values are of correct type
            if not isinstance(cal["offset"], (int, float)) or not isinstance(cal["slope"], (int, float)):
                raise InvalidSensorConfigError(f"Calibration values for '{key}' must be numeric")

        ranges_map = sensor_config.get("ranges") or {}
        # Validate ranges_map
        for key, limits in ranges_map.items():

            # check key is a non-empty string
            if not isinstance(key, str) or not key.strip():
                raise InvalidSensorConfigError(
                    f"'{key}' in ranges_map must be a string."
                )
            # check key is present in keys_map
            if key not in canonical:
                raise InvalidSensorConfigError(
                    f"metadata references unknown canonical key '{key}' in ranges_map"
                )

            # check limits is dictionary
            if not isinstance(limits, dict):
                raise InvalidSensorConfigError(f"Range for '{key}' must be a dict with 'min' and 'max'")
            # check limits contains min and max
            if "min" not in limits or "max" not in limits:
                raise InvalidSensorConfigError(f"Range for '{key}' must include 'min' and 'max'")

            low = limits["min"]
            high = limits["max"]

            # check range values are numeric
            if not all(isinstance(x, (int, float)) for x in (low, high)):
                raise InvalidSensorConfigError(f"Range values for '{key}' must be numeric")
            # check low is less than high
            if low >= high:
                raise InvalidSensorConfigError(f"Invalid range for '{key}': min ({low}) must be less than max ({high})")

        smoothing_map = sensor_config.get("smoothing") or {}

        # Validate smoothing_map
        for key, value in smoothing_map.items():
            # check key is a non-empty string
            if not isinstance(key, str) or not key.strip():
                raise InvalidSensorConfigError(
                    f"'{key}' in smoothing_map must be a string."
                )
            # check key is present in keys_map
            if key not in canonical:
                raise InvalidSensorConfigError(
                    f"metadata references unknown canonical key '{key}' in smoothing_map"
                )
            # Check value is either an int of float
            if not isinstance(value, int):
                raise InvalidSensorConfigError(
                    f"Smoothing for '{key}' must be a numeric value: {value}"
                )
            if value < 1:
                raise InvalidSensorConfigError(
                    f"Smoothing for '{key}' must be less than or equal to 1: {value}"
                )


        interval = sensor_config.get("interval")
        # Limit interval to more than 1 second
        if interval is None:
            interval = None
        elif not isinstance(interval, int) or interval < 1:
            raise InvalidSensorConfigError("'interval' must be an integer ≥ 1 if provided")



        driver_class = self._registry.get(sensor_type)
        if driver_class is None:
            raise UnknownSensorTypeError(
                unknown_type=sensor_type,
                known_types=list(self._registry.keys()),
                sensor_id=sensor_config.get("id")
            )

        driver_config = sensor_config

        required_any_of = getattr(driver_class, "REQUIRED_ANY_OF", [])
        accepted_kwargs = getattr(driver_class, "ACCEPTED_KWARGS", set())
        coercers = getattr(driver_class, "COERCERS", {})

        filtered_kwargs = {}

        for key, value in driver_config.items():
            if key in accepted_kwargs:
                filtered_kwargs[key] = value

        if required_any_of:
            has_valid_group = False

            for group in required_any_of:
                # Check if every required key in this group exists and has a non-empty value
                if all(
                        key in filtered_kwargs and filtered_kwargs[key] not in (None, "", [])
                        for key in group
                ):
                    has_valid_group = True
                    break

            if not has_valid_group:
                raise InvalidSensorConfigError(
                    f"{driver_class.__name__} requires at least one of the following sets of fields: {required_any_of}"
                )
        for field_name, cast in coercers.items():
            if field_name in filtered_kwargs:
                try:
                    filtered_kwargs[field_name] = cast(filtered_kwargs[field_name])
                except Exception as e:
                    raise InvalidSensorConfigError(
                        f"Invalid type for '{field_name}' in {driver_class.__name__}: expected {cast.__name__}"
                    ) from e

        try:
            driver = driver_class(**filtered_kwargs)
        except Exception as e:
            raise InvalidSensorConfigError(
                f"Failed to instantiate {driver_class.__name__}: {e}",
                sensor_type=sensor_type,
                sensor_id=sensor_config.get("id"),
                cause=e,
            ) from e

        return SensorBundle(
            driver=driver,
            keys=keys_map,
            calibration=calibration_map,
            ranges=ranges_map,
            smoothing=smoothing_map,
            interval=interval
        )

    def build_all(self, config) -> list[SensorBundle]:
        """
        Build all sensors from either:
          - a list of sensor config dicts, or
          - a dict containing a "sensors" list.
        Returns a list of successfully built SensorBundle objects.
        Any sensor that fails to build is logged and skipped.
        """
        # 1) Normalise input to a list of sensor configs
        if isinstance(config, dict) and "sensors" in config:
            sensors_cfgs = config.get("sensors")
        elif isinstance(config, list):
            sensors_cfgs = config
        else:
            raise InvalidSensorConfigError(
                "build_all expects a list of sensor configs or a dict containing a 'sensors' list"
            )

        if not isinstance(sensors_cfgs, list):
            raise InvalidSensorConfigError("'sensors' must be a list")

        bundles: List[SensorBundle] = []

        # 2) Build each sensor, skip on per-item failure
        for idx, sensor_cfg in enumerate(sensors_cfgs):
            try:
                bundle = self.build(sensor_cfg)
                bundles.append(bundle)

            except FactoryError as e:
                # Prefer structured context if present on the exception
                sensor_type = getattr(e, "sensor_type", None) or sensor_cfg.get("type")
                sensor_id = getattr(e, "sensor_id", None) or sensor_cfg.get("id")
                logger.warning(
                    "Skipping sensor (index=%s, type=%s, id=%s): %s",
                    idx, sensor_type, sensor_id, str(e)
                )
                continue

            except Exception as e:
                # Truly unexpected — keep the traceback
                sensor_type = sensor_cfg.get("type")
                sensor_id = sensor_cfg.get("id")
                logger.exception(
                    "Unexpected error building sensor (index=%s, type=%s, id=%s): %s",
                    idx, sensor_type, sensor_id, str(e)
                )
                continue

        return bundles
