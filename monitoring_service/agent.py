"""
agent.py

Defines the MonitoringAgent class, which manages telemetry and attribute
reporting to ThingsBoard. This class owns the lifecycle of the monitoring
process, including connecting to the MQTT broker, scheduling telemetry updates,
and handling incoming server-side RPC or attribute updates.

Classes:
    MonitoringAgent

Usage:
    Instantiate MonitoringAgent and call .start() to begin the monitoring loop.
"""
import time


class MonitoringAgent:
    """
    Manages telemetry sending to ThingsBoard. Uses poll_period to determine when to send data to ThingsBoard.
    Logs the collected telemetry before sending to ThingsBoard.

    Args:
        tb_host (str): ThingsBoard host to connect to.
        access_token (str): Access token to connect with.
        logger (Logger): Logger to use.
        telemetry_collector (TelemetryCollector): Telemetry collector instance.
        tb_client (ThingsBoardClient): ThingsBoard client instance.
        poll_period (int): Time in seconds between telemetry updates.
    """
    def __init__(self,
                 tb_host,
                 access_token,
                 logger,
                 telemetry_collector,
                 attributes_collector,
                 tb_client,
                 poll_period=60
                 ):
        self.tb_host = tb_host
        self.access_token = access_token
        self.logger = logger
        self.telemetry_collector = telemetry_collector
        self.attributes_collector = attributes_collector
        self.poll_period = poll_period
        self.tb_client = tb_client

    def start(self):
        """
        Starts the monitoring loop that periodically collects and sends telemetry and attribute data.

        This method runs indefinitely, sleeping for `poll_period` seconds between each
        telemetry/attributes collection cycle. It logs each tick and handles timing delays.

        Attributes data sent on every cycle in case of change. ThingsBoard will only log on change.

        Raises:
            Any unexpected exceptions from telemetry collection or transmission will propagate.
        """

        self.logger.info("MonitoringAgent started.")
        # Main loop
        while True:
            start_time = time.time()
            self._read_and_send_telemetry()
            self._read_and_send_attributes()
            end_time = time.time()
            elapsed = end_time - start_time
            delay = max(0, int(self.poll_period - elapsed))
            time.sleep(delay)

    def _read_and_send_telemetry(self):
        # TODO: move error logging into telemetry.py, remove from this function
        self.logger.info("Reading telemetry...")
        telemetry = self.telemetry_collector.as_dict()
        self.logger.info(f"Collected telemetry: {telemetry}")

        self.logger.info("Sending telemetry...")
        self.tb_client.send_telemetry(telemetry)
        self.logger.info("Telemetry sent.")

    def _read_and_send_attributes(self):
        self.logger.info("Reading attributes...")
        attributes = self.attributes_collector.as_dict()
        self.logger.info(f"Collected attributes: {attributes}")

        self.logger.info("Sending attributes...")
        self.tb_client.send_attributes(attributes)
        self.logger.info("Attributes sent.")
