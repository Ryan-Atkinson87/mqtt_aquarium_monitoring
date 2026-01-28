"""
TBClientWrapper.py

Provides the TBClientWrapper class, a thin wrapper around the ThingsBoard MQTT
client. It manages connection setup and exposes methods for sending telemetry
and attribute data.

Classes:
    TBClientWrapper
"""

from tb_device_mqtt import TBDeviceMqttClient


def _safe_log(logger, level: str, message: str) -> None:
    if logger is None:
        return
    fn = getattr(logger, level.lower(), None)
    if callable(fn):
        try:
            fn(message)
        except Exception:
            pass


class TBClientWrapper:
    """
    Wrap the ThingsBoard MQTT client and provide helper methods for connecting,
    sending telemetry and attributes, and disconnecting.
    """

    def __init__(self, tb_server, tb_token, logger, client_class=TBDeviceMqttClient):
        self.logger = logger
        self.client = client_class(tb_server, username=tb_token)

    def connect(self):
        """
        Establish a connection to the ThingsBoard server.
        """
        try:
            self.client.connect()
            _safe_log(self.logger, "info", "Connected to ThingsBoard.")
        except Exception as e:
            _safe_log(self.logger, "error", f"Could not connect to ThingsBoard server: {e}")
            raise

    def send_telemetry(self, telemetry: dict):
        """
        Send a telemetry payload to ThingsBoard.

        Empty payloads are logged and skipped.
        """
        if not telemetry:
            _safe_log(self.logger, "warning", "Telemetry data is empty. Skipping send.")
            return

        try:
            self.client.send_telemetry(telemetry)
        except Exception as e:
            _safe_log(self.logger, "error", f"Failed to send telemetry to ThingsBoard: {e}")

    def send_attributes(self, attributes: dict):
        """
        Send an attributes payload to ThingsBoard.

        Empty payloads are logged and skipped.
        """
        if not attributes:
            _safe_log(self.logger, "warning", "Attributes data is empty. Skipping send.")
            return

        try:
            self.client.send_attributes(attributes)
        except Exception as e:
            _safe_log(self.logger, "error", f"Failed to send attributes data to ThingsBoard: {e}")

    def disconnect(self):
        """
        Disconnect from the ThingsBoard server.
        """
        try:
            self.client.disconnect()
            _safe_log(self.logger, "info", "Disconnected from ThingsBoard.")
        except Exception as e:
            _safe_log(self.logger, "error", f"Failed to disconnect ThingsBoard: {e}")
            raise
