"""
attributes.py

Provides the AttributesCollector class, responsible for gathering basic device
attributes such as device name, IP address, and MAC address.

Classes:
    AttributesCollector

Usage:
    collector = AttributesCollector(device_name, logger)
    attrs = collector.as_dict()
"""

import socket
import uuid


class AttributesCollector:
    """
    Collect basic device attributes and expose them as a dictionary.

    The collector gathers device name, IP address, and MAC address. Attribute
    values are retrieved on demand when calling as_dict().
    """

    def __init__(self, device_name, logger):
        self.device_name = device_name
        self.logger = logger

    def _get_ip_address(self):
        """
        Retrieve the device's primary IPv4 address.

        Returns:
            str or None: The detected IP address, or None if it cannot be
            determined.
        """
        this_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            this_socket.connect(("8.8.8.8", 80))
            return this_socket.getsockname()[0]
        except Exception as e:
            self.logger.error(f"Error getting IP address: {e}")
            return None
        finally:
            this_socket.close()

    def _get_mac_address(self):
        """
        Retrieve the device's MAC address.

        Returns:
            str or None: The MAC address in standard colon format, or None if it
            cannot be determined.
        """
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
        Build and return a dictionary of collected device attributes.

        Returns:
            dict: Attribute values including device_name, ip_address,
            and mac_address.
        """

        ip_address = self._get_ip_address()
        mac_address = self._get_mac_address()
        return {
            "device_name": self.device_name,
            "ip_address": ip_address,
            "mac_address": mac_address,
        }
