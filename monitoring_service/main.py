"""
main.py

Bootstrap entry point for the monitoring service. Loads configuration, sets up
logging, constructs sensors, collectors, and displays, initializes the
ThingsBoard client, and starts the monitoring agent.
"""

import logging
from monitoring_service.config_loader import ConfigLoader
from monitoring_service.logging_setup import setup_logging
from monitoring_service.inputs.sensors import SensorFactory
from monitoring_service.telemetry import TelemetryCollector
from monitoring_service.attributes import AttributesCollector
from monitoring_service.TBClientWrapper import TBClientWrapper
from monitoring_service.agent import MonitoringAgent
from monitoring_service.outputs.display.factory import build_displays


def main():
    """
    Initialize and start the monitoring service.

    This function loads configuration, configures logging, builds sensors via the
    SensorFactory, initializes displays, wires collectors and the ThingsBoard
    client, and starts the MonitoringAgent.
    """
    bootstrap_logger = logging.getLogger("bootstrap")
    bootstrap_logger.setLevel(logging.INFO)
    bootstrap_logger.addHandler(logging.StreamHandler())

    config = ConfigLoader(logger=bootstrap_logger).as_dict()

    logger = setup_logging(
        log_dir="log",
        log_file_name="monitoring_service.log",
        log_level=config["log_level"],
    )

    displays_config = config.get("displays", [])

    displays = build_displays(
        displays_config=displays_config,
        logger=logger,
    )

    server = config["server"]
    token = config["token"]
    poll_period = config["poll_period"]
    device_name = config["device_name"]

    factory = SensorFactory()

    sensors_config = config.get("sensors", [])
    if not isinstance(sensors_config, list) or not sensors_config:
        raise RuntimeError("Config missing a non-empty 'sensors' list")

    bundles = factory.build_all(sensors_config)

    if not bundles:
        logger.warning("No sensors configured/built. Telemetry will be empty.")

    telemetry_collector = TelemetryCollector(bundles=bundles)
    attributes_collector = AttributesCollector(device_name, logger)
    client = TBClientWrapper(server, token, logger)

    agent = MonitoringAgent(
        server,
        token,
        logger,
        telemetry_collector,
        attributes_collector,
        client,
        poll_period,
        displays=displays,
    )

    client.connect()

    try:
        agent.start()
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user.")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
