"""
factory.py

Provides the SensorFactory and SensorBundle abstractions. The factory constructs
sensor drivers from configuration data, validates associated metadata, and
returns SensorBundle objects that can be consumed by the telemetry collector
without knowledge of driver internals.
"""


from typing import Optional
from monitoring_service.inputs.sensors import dht22, water_flow
from monitoring_service.inputs.sensors import ds18b20
from dataclasses import dataclass, field
from monitoring_service.inputs.sensors.base import BaseSensor
from monitoring_service.exceptions import (InvalidSensorConfigError, UnknownSensorTypeError, FactoryError)

# Set up logging
from monitoring_service import PACKAGE_LOGGER_NAME
import logging
logger = logging.getLogger(f"{PACKAGE_LOGGER_NAME}.{__name__.split('.')[-1]}")

@dataclass
class SensorBundle:
    """
    Container object holding a sensor driver and its associated metadata.

    A SensorBundle combines the constructed driver instance with configuration
    used during telemetry processing, such as key mapping, calibration, smoothing,
    range limits, and read interval.
    """
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
    """
    Construct sensor drivers from configuration and return SensorBundle objects.

    The factory maintains a registry mapping sensor type strings to driver
    classes, validates configuration data, and instantiates drivers with only
    the parameters they accept.
    """
    def __init__(self, registry: dict[str, type[BaseSensor]] | None = None):
        if registry is None:
            self._registry = {
                "ds18b20": ds18b20.DS18B20Sensor,
                "dht22": dht22.DHT22Sensor,
                "water_flow": water_flow.WaterFlowSensor,
            }
        else:
            self._registry = registry

    def register(self, sensor_type: str, driver_class: type[BaseSensor]):
        """
        Register or override a sensor driver class for a given sensor type.

        Args:
            sensor_type (str): Sensor type identifier used in configuration.
            driver_class (type[BaseSensor]): Driver class implementing the sensor.
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
        Build a single SensorBundle from a sensor configuration dictionary.

        The configuration is validated, the appropriate driver class is resolved
        from the registry, and the driver is instantiated with accepted and
        coerced parameters. Metadata such as key mapping, calibration, smoothing,
        ranges, and interval are validated and attached to the resulting bundle.

        Returns:
            SensorBundle: A fully constructed sensor bundle.
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
            if not isinstance(key, str) or not key.strip():
                raise InvalidSensorConfigError(f"'{key}' in calibration_map must be a string.")
            if key not in canonical:
                raise InvalidSensorConfigError(f"metadata references unknown canonical key '{key}' in calibration_map")
            if not isinstance(cal, dict):
                raise InvalidSensorConfigError(f"Calibration for '{key}' must be a dict with 'offset' and 'slope'")
            if "offset" not in cal or "slope" not in cal:
                raise InvalidSensorConfigError(f"Calibration for '{key}' must include 'offset' and 'slope'")
            if not isinstance(cal["offset"], (int, float)) or not isinstance(cal["slope"], (int, float)):
                raise InvalidSensorConfigError(f"Calibration values for '{key}' must be numeric")

        ranges_map = sensor_config.get("ranges") or {}
        for key, limits in ranges_map.items():
            if not isinstance(key, str) or not key.strip():
                raise InvalidSensorConfigError(f"'{key}' in ranges_map must be a string.")
            if key not in canonical:
                raise InvalidSensorConfigError(f"metadata references unknown canonical key '{key}' in ranges_map")
            if not isinstance(limits, dict):
                raise InvalidSensorConfigError(f"Range for '{key}' must be a dict with 'min' and 'max'")
            if "min" not in limits or "max" not in limits:
                raise InvalidSensorConfigError(f"Range for '{key}' must include 'min' and 'max'")

            low = limits["min"]
            high = limits["max"]

            if not all(isinstance(x, (int, float)) for x in (low, high)):
                raise InvalidSensorConfigError(f"Range values for '{key}' must be numeric")
            if low >= high:
                raise InvalidSensorConfigError(f"Invalid range for '{key}': min ({low}) must be less than max ({high})")

        smoothing_map = sensor_config.get("smoothing") or {}
        for key, value in smoothing_map.items():
            if not isinstance(key, str) or not key.strip():
                raise InvalidSensorConfigError(f"'{key}' in smoothing_map must be a string.")
            if key not in canonical:
                raise InvalidSensorConfigError(f"metadata references unknown canonical key '{key}' in smoothing_map")
            if not isinstance(value, int):
                raise InvalidSensorConfigError(f"Smoothing for '{key}' must be an integer ≥ 1: {value}")
            if value < 1:
                raise InvalidSensorConfigError(f"Smoothing for '{key}' must be an integer ≥ 1: {value}")

        interval = sensor_config.get("interval")
        if interval is not None and (not isinstance(interval, int) or interval < 1):
            raise InvalidSensorConfigError("'interval' must be an integer ≥ 1 if provided")

        driver_class = self._registry.get(sensor_type)
        if driver_class is None:
            raise UnknownSensorTypeError(
                unknown_type=sensor_type,
                known_types=list(self._registry.keys()),
                sensor_id=sensor_config.get("id")
            )

        driver_config = sensor_config

        required_kwargs = getattr(driver_class, "REQUIRED_KWARGS", None)
        required_any_of = getattr(driver_class, "REQUIRED_ANY_OF", None) if required_kwargs is None else None
        accepted_kwargs = getattr(driver_class, "ACCEPTED_KWARGS", set())
        coercers = getattr(driver_class, "COERCERS", {})

        filtered_kwargs: dict[str, object] = {}
        for key, value in driver_config.items():
            if key in accepted_kwargs:
                filtered_kwargs[key] = value

        for field_name, cast in coercers.items():
            if field_name in filtered_kwargs:
                try:
                    filtered_kwargs[field_name] = cast(filtered_kwargs[field_name])
                except Exception as e:
                    raise InvalidSensorConfigError(
                        f"Invalid type for '{field_name}' in {driver_class.__name__}: expected {getattr(cast, '__name__', str(cast))}"
                    ) from e

        if required_kwargs:
            missing: set[str] = set()
            for required_key in required_kwargs:
                if required_key not in filtered_kwargs or filtered_kwargs[required_key] in (None, "", []):
                    missing.add(required_key)

            not_accepted = set(required_kwargs) - set(accepted_kwargs)
            if not_accepted:
                raise InvalidSensorConfigError(
                    f"Driver {driver_class.__name__} misconfigured: REQUIRED_KWARGS {sorted(required_kwargs)} "
                    f"must be included in ACCEPTED_KWARGS (missing: {sorted(not_accepted)})"
                )

            if missing:
                raise InvalidSensorConfigError(
                    f"{driver_class.__name__} requires fields: {sorted(required_kwargs)} — missing: {sorted(missing)}"
                )
        elif required_any_of:
            has_valid_group = False
            for group in required_any_of:
                if all(key in filtered_kwargs and filtered_kwargs[key] not in (None, "", []) for key in group):
                    has_valid_group = True
                    break
            if not has_valid_group:
                raise InvalidSensorConfigError(
                    f"{driver_class.__name__} requires at least one of the following sets of fields: {required_any_of}"
                )

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
        Build sensor bundles from a list of sensor configurations or a dictionary
        containing a 'sensors' list.

        Each sensor configuration is processed independently. Sensors that fail
        validation or construction are logged and skipped.

        Returns:
            list[SensorBundle]: Successfully built sensor bundles.
        """
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

        bundles: list[SensorBundle] = []

        for idx, sensor_cfg in enumerate(sensors_cfgs):
            try:
                bundle = self.build(sensor_cfg)
                bundles.append(bundle)

            except FactoryError as e:
                sensor_type = getattr(e, "sensor_type", None) or sensor_cfg.get("type")
                sensor_id = getattr(e, "sensor_id", None) or sensor_cfg.get("id")
                logger.warning(
                    "Skipping sensor (index=%s, type=%s, id=%s): %s",
                    idx, sensor_type, sensor_id, str(e)
                )
                continue

            except Exception as e:
                sensor_type = sensor_cfg.get("type")
                sensor_id = sensor_cfg.get("id")
                logger.exception(
                    "Unexpected error building sensor (index=%s, type=%s, id=%s): %s",
                    idx, sensor_type, sensor_id, str(e)
                )
                continue

        return bundles
