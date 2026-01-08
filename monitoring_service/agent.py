"""
agent.py

Defines the MonitoringAgent class, responsible for running the main monitoring
loop. The agent periodically collects telemetry and device attributes and sends
them through the configured ThingsBoard client.

Classes:
    MonitoringAgent

Usage:
    agent = MonitoringAgent(...)
    agent.start()  # starts the blocking monitoring loop
"""

import time


class MonitoringAgent:
    """
    MonitoringAgent runs the main monitoring loop. It periodically collects telemetry
    and device attributes and forwards both to the ThingsBoard client.

    Args:
        tb_host (str): ThingsBoard host, stored for reference.
        access_token (str): Access token, stored for reference.
        logger (Logger): Logger instance.
        telemetry_collector (TelemetryCollector): Collects and returns telemetry data.
        attributes_collector (AttributesCollector): Collects static and dynamic attributes.
        tb_client (ThingsBoardClient): Client used to send telemetry and attributes.
        poll_period (int): Seconds between each loop iteration.
    """

    def __init__(self,
                 tb_host,
                 access_token,
                 logger,
                 telemetry_collector,
                 attributes_collector,
                 tb_client,
                 poll_period=60,
                 displays=None
                 ):
        self.tb_host = tb_host
        self.access_token = access_token
        self.logger = logger
        self.telemetry_collector = telemetry_collector
        self.attributes_collector = attributes_collector
        self.poll_period = poll_period
        self.tb_client = tb_client
        self.displays = displays or []

    def start(self):
        """
        Start and run the blocking monitoring loop.

        On each iteration the agent:
          1) collects telemetry from telemetry_collector,
          2) collects attributes from attributes_collector,
          3) forwards both to the ThingsBoard client,
          4) sleeps for `poll_period` seconds minus the cycle runtime.

        This method blocks indefinitely and logs progress. Exceptions raised by
        the collectors or tb_client will propagate to the caller.
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
        """
        Collect telemetry and send it to the ThingsBoard client.

        Calls telemetry_collector.as_dict() to obtain the payload, logs the
        collected data, and invokes tb_client.send_telemetry(telemetry).
        """
        self.logger.info("Reading telemetry...")
        telemetry = self.telemetry_collector.as_dict()
        self.logger.info(f"Collected telemetry: {telemetry}")

        self.logger.info("Sending telemetry...")
        self.tb_client.send_telemetry(telemetry)
        self.logger.info("Telemetry sent.")

        for display in self.displays:
            try:
                display.render(telemetry)
            except Exception:
                self.logger.warning(
                    "Display render failed",
                    exc_info=True,
                )

    def _read_and_send_attributes(self):
        """
        Collect device attributes and send them to the ThingsBoard client.

        Calls attributes_collector.as_dict() to obtain the attributes, logs the
        collected attributes, and invokes tb_client.send_attributes(attributes).
        """
        self.logger.info("Reading attributes...")
        attributes = self.attributes_collector.as_dict()
        self.logger.info(f"Collected attributes: {attributes}")

        self.logger.info("Sending attributes...")
        self.tb_client.send_attributes(attributes)
        self.logger.info("Attributes sent.")
