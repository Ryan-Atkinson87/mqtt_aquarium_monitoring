"""
TBClientWrapper.py

Defines the TBClientWrapper class, which manages the connection to the ThingsBoard.
This class connects to ThingsBoard and sends a dictionary containing telemetry data.

Classes:
    TBClientWrapper

Usage:
    Instantiate TBClientWrapper and call .connect() to begin the monitoring loop.
    call .send_telemetry to send telemetry data.
    call .send_attributes to send attributes data.
"""

from tb_device_mqtt import TBDeviceMqttClient


class TBClientWrapper:
    """
    Handles the connection to the ThingsBoard and sends a dictionary containing telemetry data.

    Uses tb_device_mqtt to connect, send telemetry and disconnect from ThingsBoard.

    Raises:
        Exception: If cannot connect to ThingsBoard.
        Exception: If cannot disconnect from ThingsBoard.
    """

    def __init__(self, tb_server, tb_token, logger, client_class=TBDeviceMqttClient):
        self.client = client_class(tb_server, username=tb_token)
        self.logger = logger

    def connect(self):
        """
        Initialises the connection to ThingsBoard.
        """
        try:
            self.client.connect()
        except Exception as e:
            self.logger.error(f"Could not connect to ThingsBoard server {e}")
            raise

    def send_telemetry(self, telemetry: dict):
        """
        Sends a telemetry dictionary to ThingsBoard.

        :param telemetry: dictionary containing the telemetry data
        """
        if not telemetry:
            self.logger.warning("Telemetry data is empty. Skipping send.")
            return

        try:
            self.client.send_telemetry(telemetry)
        except Exception as e:
            self.logger.error(f"Failed to send telemetry to ThingsBoard {e}")

    def send_attributes(self, attributes: dict):
        """
        Sends attributes dictionary to ThingsBoard.

        :param attributes: dictionary containing the attributes data
        """
        if not attributes:
            self.logger.warning("Attributes data is empty. Skipping send.")
            return
        try:
            self.client.send_attributes(attributes)
        except Exception as e:
            self.logger.error(f"Failed to send attributes data to ThingsBoard {e}")

    def disconnect(self):
        """
        Disconnects from ThingsBoard.
        """
        try:
            self.client.disconnect()
        except Exception as e:
            self.logger.error(f"Failed to disconnect ThingsBoard {e}")
            raise
