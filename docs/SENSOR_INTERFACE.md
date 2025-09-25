# Sensor Interface Specification

## Overview

The sensor interface is a contract each sensor class must follow.

It defines **exactly one** public read method and some attributes' data.

It is not interested in MQTT, ThingsBoard or the collector.

It returns **domain data**, not transport payloads.

## Contract

```name:``` short, stable identifier (e.g., water_temperature). 

```kind:``` category (e.g., temperature, humidity, flow).

```units:``` string (e.g., C, %, L/h) — for dashboards and sanity checks.
```read():``` returns either:
- a single value (float/int/bool), or
- a dict of values (for multi-metric sensors like DHT22: {"air_temperature": 
23.4, "air_humidity": 51.2}).

```health() (optional):``` quick self-check, returns a simple status dict (or raises).

```close() (optional):``` tidy up resources if needed.

## Single vs. Multi-metric

All sensors should expose a single **read()** method that returns a **single dict**
regardless of the number of values being returned.

## Failure Handling

- Sensors handle hardware/parsing errors internally and raise clear exceptions. 
- The collector catches these, logs once, and omits the failed keys from telemetry. 
- Failed keys must never appear with a stale value.

## Config Fields

Each sensor instance in `config.json` must declare the following fields:

- ```type```: the sensor driver identifier (e.g., `ds18b20`, `dht22`, `flow_pulse`).
- ```id/pins/path```: the identifier required to locate the sensor hardware  
  - DS18B20 → `sensor_id` (from `/sys/bus/w1/devices/`)  
  - GPIO-based → `pin` numbers  
  - File/bus-based → `path`
- ```keys```: mapping of driver outputs to canonical telemetry keys.  
  - For single-metric sensors, a one-to-one mapping (still a dict).  
  - For multi-metric sensors (e.g., DHT22), map multiple outputs.
- ```calibration```: per key, define `{offset, slope}`.  
- ```ranges```: per key, define `{min, max}` for sanity checks.  
- ```smoothing```: per key, optional `{window}` for moving average/median.  
- ```interval```: optional, read frequency in seconds. Defaults to global interval.

All fields are validated on startup (via config schema).

Unused optional fields may be omitted in config.

## Collector Responsibilities

- Build a registry of sensors from config.
- Iterate sensors, calling `read()`
- Apply `calibration`, `ranges`, `smoothing`.
- Merge into one telemetry dict.
- Do not handle transport or persistence, only prepare domain telemetry.

## Payload Schema Rules

- Keys must be; flat, underscored and lower case. 
- Values must be standard Python native types (int, float, bool, str). 
- No Nested Dicts.