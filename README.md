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
│   ├── exceptions/
│   │   ├── __init__.py
│   │   └── factory_exceptions.py
│   ├── sensors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── ds18b20.py
│   │   └── factory.py
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
│   │   └── test_hardware_telemetry_collector.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_attributes.py
│   │   ├── test_config_loader.py
│   │   ├── test_factory_build.py
│   │   ├── test_tbclientwrapper.py
│   │   └── test_telemetry_collector.py
│   └── __init__.py
├── .env
├── config.example.json
├── config.json
├── mqtt_aquarium_monitoring_example.service
├── README.md
└── requirements.txt
```

## Supported Telemetry

| Sensor Type | Telemetry Key       | Unit | Description                |
|-------------|---------------------|------|----------------------------|
| DS18B20     | `water_temperature` | °C   | Aquarium water temperature |
| DHT22       | `air_temperature`   | °C   | Ambient air temperature    |
| DHT22       | `air_humidity`      | %RH  | Relative air humidity      |

Each telemetry key is mapped from the raw driver output using the `keys` section in `config.json`.  
This allows additional sensors to be added easily without modifying the core codebase.

Future sensors (planned):
- `turbidity` - water clarity sensor  
- `water_level` - float or pressure level sensor  


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

   - `.env`:
     ```
     ACCESS_TOKEN=your_thingsboard_access_token
     THINGSBOARD_SERVER=your_thingsboard_server_url_or_ip
     ```
   - `config.json`:
     ```json
     {
       "poll_period": 5,
       "device_name": "RasPiZero_01",
       "mount_path": "/",
       "log_level": "INFO",
       "sensors": [
         {
           "type": "ds18b20",
           "id": "28-0e2461862fc0",
           "path": "/sys/bus/w1/devices/",
           "keys": {
             "temperature": "water_temperature"
           },
           "calibration": {
             "water_temperature": { "offset": 0.0, "slope": 1.0 }
           },
           "ranges": {
             "water_temperature": { "min": 0, "max": 40 }
           },
           "smoothing": {},
           "interval": 5
         }
       ]
     }
     ```

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

## License

This project is licensed under the [MIT License](LICENSE).

---

## 🤝 How to Contribute

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

### 🧭 Contribution Guidelines
- Follow the existing code style and structure.
- All new code must include appropriate **unit tests**.
- Use clear, descriptive commit messages.
- Reference any related **issues** or **milestones** in your PR.
- If adding a new feature or bugfix, label the issue appropriately (`feature`, `bug`, `v2.x.x`, etc.).
- Check the [Project Board](https://github.com/Ryan-Atkinson87/mqtt_aquarium_monitoring/projects) to see ongoing work and planned releases.

---

Built with ❤️ to provide reliable system telemetry monitoring.
