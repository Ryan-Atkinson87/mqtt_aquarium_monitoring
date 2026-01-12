# MQTT Aquarium Monitoring

![MIT License](https://img.shields.io/badge/license-MIT-green)

## Overview

**MQTT Aquarium Monitoring** is a lightweight Python application designed for Raspberry Pi devices to monitor aquarium
telemetry (temperature, light levels, turbidity etc.) and send the data to a ThingsBoard instance using MQTT. This
program is intended for production environments where reliable telemetry reporting and logging are crucial. It is
structured for maintainability and extensibility, with a focus on clean code, unit testing, and systemd deployment.

## Features

- Sends aquarium telemetry to ThingsBoard
- Sends static machine attributes (device name, IP, MAC address)
- Local rotating log files for debugging and traceability
- Unit tested with Pytest
- Python 3.11+ support
- Easily configurable via `.env` and `config.json`
- Production-ready with systemd service example

## Sensor Interface Spec

Full details in docs/SENSOR_INTERFACE.md

## Project Structure

```
mqtt_aquarium_monitoring/
├── docs/
│   └── SENSOR_INTERFACE.md
├── monitoring_service/
│   ├── display/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── factory.py
│   │   ├── logging_display.py
│   │   └── ssd1306_i2c.py.py
│   ├── exceptions/
│   │   ├── __init__.py
│   │   └── factory_exceptions.py
│   ├── sensors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── constants.py
│   │   ├── dht22.py
│   │   ├── ds18b20.py
│   │   ├── factory.py
│   │   ├── gpio_sensor.py
│   │   ├── i2c_water_level.py
│   │   └── water_flow.py
│   ├── __init__.py
│   ├── agent.py
│   ├── attributes.py
│   ├── config_loader.py
│   ├── logging_setup.py
│   ├── main.py
│   ├── TBClientWrapper.py
│   └── telemetry.py
├── tests/
│   ├── hardware/
│   │   ├── __init__.py
│   │   ├── test_hardware_dht22.py
│   │   ├── test_hardware_ds18b20.py
│   │   ├── test_hardware_ssd1306_i2c.py
│   │   └── test_hardware_water_flow.py
│   ├── not_implemented/
│   │   ├── __init__.py
│   │   ├── test_i2c_water_level.py
│   │   └── test_hardware_i2c_water_level.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_attributes.py
│   │   ├── test_config_loader.py
│   │   ├── test_dht22_factory.py
│   │   ├── test_dht22_sensor.py
│   │   ├── test_factory_build.py
│   │   ├── test_logging_display.py
│   │   ├── test_ssd1306_i2c.py.py
│   │   ├── test_tbclientwrapper.py
│   │   ├── test_telemetry_collector.py
│   │   └── test_water_flow_sensor.py
│   └── __init__.py
├── .env
├── CHANGELOG.md
├── config.example.json
├── config.json
├── mqtt_aquarium_monitoring_example.service
├── README.md
└── requirements.txt
```

## Supported Telemetry

| Sensor Type     | Telemetry Key       | Unit  | Description                           |
|-----------------|---------------------|-------|---------------------------------------|
| DS18B20         | `water_temperature` | °C    | Aquarium water temperature            |
| DHT22           | `air_temperature`   | °C    | Ambient air temperature               |
| DHT22           | `air_humidity`      | %RH   | Relative air humidity                 |
| I2C Water Level | `water_level`       | mm    | Aquarium water level from top of tank |
| Water Flow      | `water_flow`        | l/min | Water flow through filter return pipe |


Each telemetry key is mapped from the raw driver output using the `keys` section in `config.json`.  
This allows additional sensors to be added easily without modifying the core codebase.

Future sensors (planned):
- `turbidity` - water clarity sensor

## Supported Displays

| Display Type     | Output Type | Description        |
|------------------|-------------|--------------------|
| SSD1306 I2C OLED | I2C         | Small OLED Display |

## Getting Started

### Prerequisites

- Raspberry Pi OS (or any Linux-based OS)
- Python 3.11+
- ThingsBoard instance
- MQTT device access token

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/Ryan-Atkinson87/mqtt_aquarium_monitoring.git mqtt_aquarium_monitoring
   cd mqtt_aquarium_monitoring
   ```
2. Set up the Python virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure your `.env` file and `config.json`:

- See `.env` and `config.json` example files.

### Running the Application

Run directly:

```bash
python main.py
```

Or deploy with systemd for production:

```bash
sudo cp mqtt_aquarium_monitoring.service /etc/systemd/system/
sudo systemctl enable mqtt_aquarium_monitoring.service
sudo systemctl start mqtt_aquarium_monitoring.service
```

### Testing

```bash
pytest tests/
```

### Wiring Diagrams

#### DS18B20 Sensor
| Pin  | Connection | Notes                                |
|------|------------|--------------------------------------|
| VCC  | 3.3V       | Power                                |
| GND  | GND        | Ground                               |
| DATA | GPIO4      | Needs 4.7kΩ pull-up resistor to 3.3V |

- Ensure 1-Wire is enabled on the Raspberry Pi.

#### DHT22 Sensor
| Pin  | Connection | Notes                                  |
|------|------------|----------------------------------------|
| VCC  | 5V         | Power                                  |
| GND  | GND        | Ground                                 |
| DATA | GPIO17     | Requires 10kΩ pull-up resistor to 3.3V |

- Ensure pin numbering in config.json matches wiring.

#### I2C Water Level Sensor
| Pin | Connection | Notes  |
|-----|------------|--------|
| VCC | 3.3V       | Power  |
| GND | GND        | Ground |
| SDA | GPIO3      | Data   |
| SCL | GPIO5      | Clock  |

#### Water Flow Sensor (Turbine Type)
| Sensor Pin | Pi Connection | Notes      |
|------------|---------------|------------|
| VCC        | 5V            | Power      |
| GND        | GND           | Ground     |
| Signal     | GPIO17        | Signal Pin |

Signal pin requires pull-up; pigpio sets internal pull-up automatically

#### I2C SSD1306 OLED Display
| Pin | Connection | Notes  |
|-----|------------|--------|
| VCC | 3.3V       | Power  |
| GND | GND        | Ground |
| SDA | GPIO3      | Data   |
| SCL | GPIO5      | Clock  |

## License

This project is licensed under the [MIT License](LICENSE).

---

## How to Contribute

Contributions are welcome — whether it's fixing a bug, improving docs, or adding new sensor support.

1. **Fork** the repository on GitHub.
2. **Create a new branch** for your feature or fix:
   ```bash
   git checkout -b feature/my-new-feature
   ```
3. **Commit your changes** with a clear message:
   ```bash
   git commit -m "Add support for XYZ sensor"
   ```
4. **Push to your fork** and open a Pull Request against the `dev` branch.

### Contribution Guidelines
- Follow the existing code style and structure.
- All new code must include appropriate **unit tests**.
- Use clear, descriptive commit messages.
- Reference any related **issues** or **milestones** in your PR.
- If adding a new feature or bugfix, label the issue appropriately (`feature`, `bug`, `v2.x.x`, etc.).
- Check the [Project Board](https://github.com/Ryan-Atkinson87/mqtt_aquarium_monitoring/projects) to see ongoing work and planned releases.

---

Built with ❤️ to provide reliable system telemetry monitoring.
