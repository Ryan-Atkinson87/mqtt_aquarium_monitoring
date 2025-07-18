import pytest
from unittest.mock import patch,mock_open
from monitoring_service.telemetry import TelemetryCollector


@pytest.fixture
def collector():
    return TelemetryCollector(mount_path="/")

