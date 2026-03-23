# Sensor Reference

Each sensor driver reads from hardware and returns a flat dict. This document covers wiring, config fields, and notes
for each supported sensor type.

For the driver interface contract (how sensor classes are implemented), see [SENSOR_INTERFACE.md](SENSOR_INTERFACE.md).

---

## DS18B20 — Water Temperature

**Telemetry key:** `water_temperature` | **Unit:** °C | **Protocol:** 1-Wire

### Wiring

| Pin  | Connection | Notes                                |
|------|------------|--------------------------------------|
| VCC  | 3.3V       | Power                                |
| GND  | GND        | Ground                               |
| DATA | GPIO4      | Needs 4.7kΩ pull-up resistor to 3.3V |

> May need 100nF capacitor between VCC and GND.

Enable 1-Wire via `raspi-config` or add `dtoverlay=w1-gpio` to `/boot/firmware/config.txt`. The sensor ID appears under
`/sys/bus/w1/devices/`.

### Config example

```json
{
  "type": "ds18b20",
  "id": "28-0e2461862fc0",
  "path": "/sys/bus/w1/devices/",
  "keys": {
    "temperature": "water_temperature"
  },
  "calibration": {
    "water_temperature": {
      "offset": 0.0,
      "slope": 1.0
    }
  },
  "ranges": {
    "water_temperature": {
      "min": 0,
      "max": 40
    }
  },
  "smoothing": {},
  "interval": 5,
  "max_retries": 3,
  "retry_base_delay": 0.5
}
```

### Driver-specific fields

| Field  | Type   | Required | Description                               |
|--------|--------|----------|-------------------------------------------|
| `id`   | string | Yes      | 1-Wire device ID (e.g. `28-0e2461862fc0`) |
| `path` | string | Yes      | Path to 1-Wire devices directory          |

---

## DHT22 — Air Temperature & Humidity

**Telemetry keys:** `air_temperature` (°C), `air_humidity` (%RH) | **Protocol:** GPIO (bit-bang)

### Wiring

| Pin  | Connection | Notes                                  |
|------|------------|----------------------------------------|
| VCC  | 3.3V       | Power                                  |
| GND  | GND        | Ground                                 |
| DATA | GPIO17     | Requires 10kΩ pull-up resistor to 3.3V |

> May need 100nF capacitor between VCC and GND.

Ensure the pin number in `config.json` matches your wiring.

### Config example

```json
{
  "type": "DHT22",
  "id": "gpio17",
  "pin": 17,
  "keys": {
    "temperature": "air_temperature",
    "humidity": "air_humidity"
  },
  "calibration": {
    "air_temperature": {
      "offset": 0.0,
      "slope": 1.0
    },
    "air_humidity": {
      "offset": 0.0,
      "slope": 1.0
    }
  },
  "ranges": {
    "air_temperature": {
      "min": -40,
      "max": 80
    },
    "air_humidity": {
      "min": 0,
      "max": 100
    }
  },
  "smoothing": {},
  "interval": 15,
  "max_retries": 3,
  "retry_base_delay": 0.5
}
```

### Driver-specific fields

| Field | Type | Required | Description         |
|-------|------|----------|---------------------|
| `pin` | int  | Yes      | BCM GPIO pin number |

---

## Water Flow Sensor (Turbine Type)

**Telemetry keys:** `water_flow` (l/min, EMA-smoothed), `water_flow_instant` (l/min, instantaneous) | **Protocol:** GPIO
pulse counting via pigpio

### Wiring

| Sensor Pin | Pi Connection | Notes                                  |
|------------|---------------|----------------------------------------|
| VCC        | 5V            | Power                                  |
| GND        | GND           | Ground                                 |
| Signal     | GPIO21        | Requires 10kΩ pull-up resistor to 3.3V |

> May need 100nF capacitor between VCC and GND.

10k resistor between GPIO and 3.3V. The `pigpiod` daemon must be running.

### Config example

```json
{
  "type": "water_flow",
  "id": "gpio21",
  "pin": 21,
  "keys": {
    "flow_smoothed": "water_flow",
    "flow_instant": "water_flow_instant"
  },
  "calibration": {
    "water_flow": {
      "offset": 0.0,
      "slope": 1.0
    },
    "water_flow_instant": {
      "offset": 0.0,
      "slope": 1.0
    }
  },
  "ranges": {
    "water_flow": {
      "min": 0,
      "max": 30
    },
    "water_flow_instant": {
      "min": 0,
      "max": 30
    }
  },
  "smoothing": {},
  "precision": {
    "water_flow": 2,
    "water_flow_instant": 2
  },
  "interval": 5,
  "max_retries": 3,
  "retry_base_delay": 0.5,
  "sample_window": 5,
  "sliding_window_s": 3,
  "glitch_us": 200,
  "calibration_constant": 3.3
}
```

### Driver-specific fields

| Field                  | Type  | Required | Description                                              |
|------------------------|-------|----------|----------------------------------------------------------|
| `pin`                  | int   | Yes      | BCM GPIO pin number                                      |
| `sample_window`        | int   | No       | Number of samples for EMA smoothing                      |
| `sliding_window_s`     | float | No       | Sliding window duration (seconds) for instantaneous flow |
| `glitch_us`            | int   | No       | Pulse glitch filter in microseconds (pigpio)             |
| `calibration_constant` | float | No       | Pulses-per-litre factor for your specific flow sensor    |

---

## I2C Water Level Sensor (WIP)

**Telemetry key:** `water_level` | **Unit:** mm | **Protocol:** I2C

> **Note:** This driver is in `inputs/sensors/non_functional/` and is not production-ready.

### Wiring

| Pin | Connection | Notes  |
|-----|------------|--------|
| VCC | 3.3V       | Power  |
| GND | GND        | Ground |
| SDA | GPIO3      | Data   |
| SCL | GPIO5      | Clock  |

Enable I2C via `raspi-config`. Verify with `i2cdetect -y 1`.

### Config example

```json
{
  "type": "water_level",
  "id": "grove_water_level",
  "bus": 1,
  "low_address": 119,
  "keys": {
    "water_level": "water_level"
  },
  "calibration": {
    "water_level": {
      "offset": 0.0,
      "slope": 1.0
    }
  },
  "ranges": {
    "water_level": {
      "min": 0,
      "max": 100
    }
  },
  "smoothing": {},
  "interval": 5
}
```

### Driver-specific fields

| Field         | Type | Required | Description               |
|---------------|------|----------|---------------------------|
| `bus`         | int  | Yes      | I2C bus number            |
| `low_address` | int  | Yes      | I2C address of the sensor |

---

## Adding a new sensor

1. Implement `BaseSensor` from `inputs/sensors/base.py` (see [SENSOR_INTERFACE.md](SENSOR_INTERFACE.md))
2. Register the new type in `inputs/sensors/factory.py`
3. Add an entry to `config.json` following the schema above