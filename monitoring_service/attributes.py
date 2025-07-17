"""
attributes.py

Defines the AttributesCollector class, which gathers machine attribute data
such as device name, IP address, and MAC address.

Classes:
    AttributesCollector

Usage:
    reporter = AttributesCollector(device_name, logger)
    attributes = reporter.as_dict()
"""

import socket
import uuid


class AttributesCollector:
    """
    Collects static machine attribute data during initialization.

    Attributes gathered include device name, IP address, and MAC address.
    Data is collected when the class is instantiated and exposed via `as_dict()`.
    """

    def __init__(self, device_name, logger):
        self.device_name = device_name
        self.logger = logger

    def _get_ip_address(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except Exception as e:
            self.logger.error(f"Error getting IP address: {e}")
            return None
        finally:
            s.close()

    def _get_mac_address(self):
        try:
            mac_address = ':'.join(
                ['{:02x}'.format((uuid.getnode() >> ele) & 0xff)
                 for ele in range(0, 8 * 6, 8)][::-1]
            )
            return mac_address
        except Exception as e:
            self.logger.error(f"Error getting MAC address: {e}")
            return None

    def as_dict(self):
        """
        Return a dictionary containing the machine attribute data.

        :return: dictionary containing the machine attribute data.
        """

        ip_address = self._get_ip_address()
        mac_address = self._get_mac_address()
        return {
            "device_name": self.device_name,
            "ip_address": ip_address,
            "mac_address": mac_address,
        }
