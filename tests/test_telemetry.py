import pytest
from unittest.mock import patch,mock_open
from monitoring_service.telemetry import TelemetryCollector


@pytest.fixture
def collector():
    return TelemetryCollector(mount_path="/")


def test_get_cpu_usage_returns_float(collector):
    with patch("monitoring_service.telemetry.psutil.cpu_percent", return_value=25.5):
        result = collector._get_cpu_usage()
        assert isinstance(result, float)
        assert result == 25.5


def test_get_cpu_temp_returns_float(collector):
    with patch("builtins.open", new_callable=mock_open, read_data="50000"):
        result = collector._get_cpu_temp()
        assert isinstance(result, float)
        assert result == 50.0


def test_get_gpu_temp_returns_float(collector):
    with patch("monitoring_service.telemetry.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "temp=55.0'C\n"
        result = collector._get_gpu_temp()
        assert isinstance(result, float)
        assert result == 55.0


def test_get_mem_usage_returns_float(collector):
    with patch("monitoring_service.telemetry.psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.percent = 60.0
        result = collector._get_mem_usage()
        assert isinstance(result, float)
        assert result == 60.0


def test_get_disk_usage_returns_float(collector):
    with patch("monitoring_service.telemetry.psutil.disk_usage") as mock_du:
        mock_du.return_value.percent = 75.0
        result = collector._get_disk_usage()
        assert isinstance(result, float)
        assert result == 75.0


def test_get_telemetry_returns_data_and_no_errors(collector):
    # Patch all methods inside TelemetryCollector
    with patch.object(collector, "_get_cpu_usage", return_value=10.0), \
         patch.object(collector, "_get_cpu_temp", return_value=40.0), \
         patch.object(collector, "_get_gpu_temp", return_value=45.0), \
         patch.object(collector, "_get_mem_usage", return_value=55.0), \
         patch.object(collector, "_get_disk_usage", return_value=65.0):

        telemetry, errors = collector.get_telemetry()
        assert telemetry == {
            "cpu_usage": 10.0,
            "cpu_temp": 40.0,
            "gpu_temp": 45.0,
            "ram_usage": 55.0,
            "disk_usage": 65.0,
        }
        assert errors == []
