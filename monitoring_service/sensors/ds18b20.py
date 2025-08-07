import glob

class DS18B20Sensor:
    def __init__(self, sensor_id=None):
        base_dir = '/sys/bus/w1/devices/'
        if sensor_id:
            self.device_file = f"{base_dir}{sensor_id}/w1_slave"
        else:
            device_folders = glob.glob(base_dir + '28-*')
            if not device_folders:
                raise RuntimeError("No DS18B20 sensor found.")
            self.device_file = f"{device_folders[0]}/w1_slave"

    def read_temp(self):
        with open(self.device_file, 'r') as f:
            lines = f.readlines()
        if lines[0].strip()[-3:] != 'YES':
            raise RuntimeError("Sensor CRC check failed")
        equals_pos = lines[1].find('t=')
        if equals_pos == -1:
            raise RuntimeError("Temperature reading not found")
        return float(lines[1][equals_pos + 2:]) / 1000.0
