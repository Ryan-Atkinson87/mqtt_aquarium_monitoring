"""
main.py

Runs the monitoring service by setting up configuration, logging, telemetry collection,
and ThingsBoard connectivity. Loads `.env` and `config.json`, establishes the MQTT connection,
and starts the MonitoringAgent loop.

This script is the main entry point for the monitoring application.
"""
import logging
from monitoring_service.config_loader import ConfigLoader
from monitoring_service.telemetry import TelemetryCollector
from monitoring_service.attributes import AttributesCollector
from monitoring_service.TBClientWrapper import TBClientWrapper
from monitoring_service.agent import MonitoringAgent
from monitoring_service.logging_setup import setup_logging
from monitoring_service.sensors.ds18B20 import DS18B20Sensor

def main():
    bootstrap_logger = logging.getLogger("bootstrap")
    bootstrap_logger.setLevel(logging.INFO)
    bootstrap_logger.addHandler(logging.StreamHandler())

    config_loader = ConfigLoader(logger=bootstrap_logger)
    config = config_loader.as_dict() 

    logger = setup_logging(
        log_dir="log",
        log_file_name="monitoring_service.log",
        log_level=config["log_level"]
    )

    server = config["server"]
    token = config["token"]
    poll_period = config["poll_period"]
    mount_path = config["mount_path"]
    device_name = config["device_name"]

    # TODO: Add to config
    sensor_id = "28-0e2461862fc0"

    temperature_sensor = DS18B20Sensor(sensor_id)

    telemetry_collector = TelemetryCollector(logger, temperature_sensor, mount_path)
    attributes_collector = AttributesCollector(device_name,
                                               logger)

    client = TBClientWrapper(server,
                             token,
                             logger)

    agent = MonitoringAgent(server,
                            token,
                            logger,
                            telemetry_collector,
                            attributes_collector,
                            client,
                            poll_period)

    client.connect()
    agent.start()
    client.disconnect()


if __name__ == "__main__":
    main()
