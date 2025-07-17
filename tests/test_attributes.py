import pytest
from unittest.mock import patch
from monitoring_service.attributes import AttributesCollector


@pytest.fixture
def collector():
    return AttributesCollector(device_name="TestDevice", logger=DummyLogger())


class DummyLogger:
    def error(self, msg):
        print(f"LOG: {msg}")


def test_as_dict_returns_expected_keys(collector):
    with patch.object(collector, "_get_ip_address", return_value="192.168.0.100"), \
         patch.object(collector, "_get_mac_address", return_value="00:11:22:33:44:55"):
        result = collector.as_dict()

    assert result["device_name"] == "TestDevice"
    assert result["ip_address"] == "192.168.0.100"
    assert result["mac_address"] == "00:11:22:33:44:55"


def test_get_ip_address_returns_ip_string(collector):
    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.getsockname.return_value = ("192.168.0.101", 0)
        ip_address = collector._get_ip_address()
        assert ip_address == "192.168.0.101"


def test_get_mac_address_returns_mac_string(collector):
    with patch("monitoring_service.attributes.uuid.getnode", return_value=0x001122334455):
        mac = collector._get_mac_address()
        assert mac == "00:11:22:33:44:55"
