# Changelog
All notable changes to this project will be documented in this file.
Format: Keep a Changelog. Versioning: SemVer (MAJOR.MINOR.PATCH).

## [Unreleased]
### Added
- (Planned) Additional sensors & telemetry fields.
- (Planned) Pi maintenance commands section in docs.

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

