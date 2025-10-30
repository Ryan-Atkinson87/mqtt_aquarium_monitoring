# Changelog
All notable changes to this project will be documented in this file.
Format: Keep a Changelog. Versioning: SemVer (MAJOR.MINOR.PATCH).

## [Unreleased]
### Added
- (Planned) Internal version tracking.
- (Planned) SQLite que for offline storage and retries.
- (Planned) HTTP implementation for sending data to places other than ThingsBoard.


## [v2.1.0] - 2025-10-30
### Added
- DHT22 sensor support for temperature and humidity.
- Unit tests for DHT22 driver and factory integration.
- Hardware test files for DHT22.
- README updates for wiring, config example, and expected telemetry keys.

### Changed
- SensorFactory now supports drivers that declare `REQUIRED_KWARGS`.
- Improved coercion and validation for GPIO-based sensors.

### Documentation
- Updated README.

## [v2.0.0] – 2025-10-21
### Added
- Modular SensorFactory for dynamic sensor creation.
- DS18B20 driver with calibration and validation.
- ThingsBoard MQTT client wrapper for telemetry.
- Attributes module for device metadata.

### Changed
- Refactored TelemetryCollector to use factory output.
- Improved ConfigLoader and logging setup.

### Fixed
- Stability and environment variable handling.

### Documentation
- Updated README and added systemd service example.

## [2.0.0-rc2] - 2025-10-20
### Fixed
- Resolved critical bug in DS18B20Sensor where the driver ignored provided path and mis-treated the file path as a base directory.
- Now correctly distinguishes between path (full w1_slave file) and base_dir (directory).
- Fully supports both configuration styles:
   - {"id": "28-xxxx", "path": "/sys/bus/w1/devices/"}
   - {"path": "/sys/bus/w1/devices/28-xxxx/w1_slave"}
- _get_device_file() no longer returns None and properly raises DS18B20ReadError on missing sensors.

### Improved
- Added explicit device_file attribute to DS18B20Sensor for clarity and logging.
- Enhanced TelemetryCollector ID resolution (id, sensor_id, path, or device_file) for more readable logs.

### Version
- Marked as release candidate 2 for v2.0.0.
- This RC focuses on verifying stable hardware operation before final release.

## [2.0.0-rc1] - 2025-10-18
### Added
- **SensorFactory** to build sensors from config (extensible, validated).
- **DS18B20Sensor** driver wired through the factory.
- **TelemetryCollector** integration with factory output (per-sensor intervals supported).
- **31 unit tests** now passing; hardware test markers for Pi-only runs.
- Local **deployment notes** and tag-based release flow (RCs).

### Changed
- Telemetry pipeline refactored to use factory-built sensor bundles.
- Config schema tightened and validated on build.
- Logging and module layout tidied for readability and deployment.

### Fixed
- More robust error handling around sensor reads (DS18B20 edge cases).

### Removed
- Direct, ad-hoc sensor instantiation in collector (replaced by factory).

### Breaking
- v1.x configs/expectations **won’t work** without updating to factory-driven config and key names.

## [1.0.0] - 2025-0X-XX
### Added
- First stable, working end-to-end version.
- Basic telemetry collection and ThingsBoard publish.
- Systemd service skeleton and minimal docs.

