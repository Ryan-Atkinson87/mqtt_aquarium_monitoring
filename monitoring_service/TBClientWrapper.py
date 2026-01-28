"""
TBClientWrapper.py

Provides the TBClientWrapper class, a thin wrapper around the ThingsBoard MQTT
client. It manages connection setup and exposes methods for sending telemetry
and attribute data.

Classes:
    TBClientWrapper
"""

from tb_device_mqtt import TBDeviceMqttClient
from threading import Lock


class TBClientWrapper:
    """
    Wrap the ThingsBoard MQTT client and provide helper methods for connecting,
    sending telemetry and attributes, and disconnecting.
    """

    def __init__(self, tb_server, tb_token, logger, client_class=TBDeviceMqttClient):
        self.client = client_class(tb_server, username=tb_token)
        self.logger = logger
        self._connected = False
        self._loop_started = False
        self._lock = Lock()

    def connect(self):
        """
        Establish a connection to the ThingsBoard server and start the MQTT
        network loop if it is not already running.
        """
        with self._lock:
            if self._connected:
                return

            try:
                self.client.connect()

                if not self._loop_started:
                    self.client.loop_start()
                    self._loop_started = True

                self._connected = True
                self.logger.info("Connected to ThingsBoard server.")

            except Exception as e:
                self.logger.error(f"Could not connect to ThingsBoard server: {e}")
                raise

    def send_telemetry(self, telemetry: dict):
        """
        Send a telemetry payload to ThingsBoard.

        Empty payloads are logged and skipped. Telemetry is only sent if a
        connection is currently established.
        """
        if not telemetry:
            self.logger.warning("Telemetry data is empty. Skipping send.")
            return

        if not self._connected:
            self.logger.warning(
                "Telemetry send requested while not connected to ThingsBoard."
            )
            return

        try:
            self.client.send_telemetry(telemetry)
            self.logger.info("Telemetry sent.")
        except Exception as e:
            self.logger.error(f"Failed to send telemetry to ThingsBoard: {e}")

    def send_attributes(self, attributes: dict):
        """
        Send an attributes payload to ThingsBoard.

        Empty payloads are logged and skipped. Attributes are only sent if a
        connection is currently established.
        """
        if not attributes:
            self.logger.warning("Attributes data is empty. Skipping send.")
            return

        if not self._connected:
            self.logger.warning(
                "Attributes send requested while not connected to ThingsBoard."
            )
            return

        try:
            self.client.send_attributes(attributes)
            self.logger.info("Attributes sent.")
        except Exception as e:
            self.logger.error(f"Failed to send attributes data to ThingsBoard: {e}")

    def disconnect(self):
        """
        Disconnect from the ThingsBoard server and stop the MQTT network loop.
        """
        with self._lock:
            if not self._connected:
                return

            try:
                self.client.disconnect()

                if self._loop_started:
                    self.client.loop_stop()
                    self._loop_started = False

                self._connected = False
                self.logger.info("Disconnected from ThingsBoard server.")

            except Exception as e:
                self.logger.error(f"Failed to disconnect ThingsBoard: {e}")
                raise
