from dataclasses import dataclass
from typing import Optional
import time


@dataclass(frozen=True)
class DisplayStatus:
    device_name: str
    connected: bool
    last_publish_ok: bool
    cpu_temp_c: Optional[float]
    water_temperature: Optional[float]
    flow_present: Optional[bool]
    timestamp_utc: float

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "DisplayStatus":
        values = snapshot.get("values", {})

        return cls(
            device_name=snapshot.get("device_name", "unknown"),
            #connected=snapshot.get("connected", False),
            #last_publish_ok=snapshot.get("last_publish_ok", False),
            water_temperature=values.get("water_temperature"),
            #flow_present=values.get("flow_present"),
            timestamp_utc=snapshot.get("ts", time.time()),
        )
