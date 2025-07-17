"""
telemetry.py

Provides the TelemetryCollector class, which gathers system metrics from a
Raspberry Pi or other Linux-based device. These metrics include CPU usage,
CPU temperature, GPU temperature, RAM usage, and disk usage.

All metrics are returned as a dictionary of telemetry data, along with a list
of any errors encountered during collection. This data is intended for use
with IoT platforms such as ThingsBoard.

Classes:
    TelemetryCollector

Usage:
    collector = TelemetryCollector()
    telemetry, errors = collector.get_telemetry()
"""

import psutil
import subprocess


class TelemetryCollector:
    """
    Manages the collection of telemetry from the Raspberry Pi.
    Uses get_telemetry to collect telemetry from the Raspberry Pi in the form of a
    dictionary of telemetry data.
    """
    def __init__(self, mount_path="/"):
        self.mount_path = mount_path

    @staticmethod
    def _get_cpu_usage():
        cpu_usage = psutil.cpu_percent(interval=1)
        return cpu_usage

    @staticmethod
    def _get_cpu_temp():
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_str = f.readline()
            return float(temp_str) / 1000.0

    @staticmethod
    def _get_gpu_temp():
        vcgencmd_path = "/usr/bin/vcgencmd"
        result = subprocess.run([vcgencmd_path, 'measure_temp'], capture_output=True, text=True)
        if result.returncode == 0:
            temp_str = result.stdout.strip()
            temp_value = temp_str.split('=')[1].replace("'C", "")
            return float(temp_value)
        else:
            return None

    @staticmethod
    def _get_mem_usage():
        mem_usage = psutil.virtual_memory().percent
        return mem_usage

    def _get_disk_usage(self):
        # TODO: support configurable mount point
        disk_usage = psutil.disk_usage(self.mount_path).percent
        return disk_usage

    def get_telemetry(self):
        # TODO: move error logging into this function, remove from agent.py
        """
        Collects system metrics from a Raspberry Pi.
        :return: dictionary of telemetry data, list of errors encountered
        """
        data = {}
        errors = []

        try:
            data['cpu_usage'] = self._get_cpu_usage()
        except Exception as e:
            errors.append(f"Error getting cpu usage: {e}")
            data['cpu_usage'] = None

        try:
            data['cpu_temp'] = self._get_cpu_temp()
        except Exception as e:
            errors.append(f"Error getting cpu temp: {e}")
            data['cpu_temp'] = None

        try:
            data['gpu_temp'] = self._get_gpu_temp()
        except Exception as e:
            errors.append(f"Error getting gpu temp: {e}")
            data['gpu_temp'] = None

        try:
            data['ram_usage'] = self._get_mem_usage()
        except Exception as e:
            errors.append(f"Error getting memory usage: {e}")
            data['ram_usage'] = None

        try:
            data['disk_usage'] = self._get_disk_usage()
        except Exception as e:
            errors.append(f"Error getting disk usage: {e}")
            data['disk_usage'] = None

        return data, errors
