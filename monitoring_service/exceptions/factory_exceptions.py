from typing import Any, Optional

class FactoryError(Exception):
    """
    Base exception for factory-related errors.
    Carries optional context for better logs without string parsing.
    """
    def __init__(
        self,
        message: str,
        *,
        sensor_id: Optional[str] = None,
        sensor_type: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.sensor_id = sensor_id
        self.sensor_type = sensor_type
        self.config = config
        self.__cause__ = cause

    def __str__(self) -> str:
        base = super().__str__()
        ctx = []
        if self.sensor_type:
            ctx.append(f"sensor_type={self.sensor_type}")
        if self.sensor_id:
            ctx.append(f"sensor_id={self.sensor_id}")
        return f"{base} ({', '.join(ctx)})" if ctx else base


class UnknownSensorTypeError(FactoryError):
    def __init__(
        self,
        unknown_type: str,
        known_types: list[str],
        *,
        sensor_id: Optional[str] = None,
    ) -> None:
        msg = f"Unknown sensor type '{unknown_type}'. Known types: {', '.join(sorted(known_types)) or '∅'}"
        super().__init__(msg, sensor_type=unknown_type, sensor_id=sensor_id)


class InvalidSensorConfigError(FactoryError):
    def __init__(
        self,
        message: str,
        *,
        sensor_id: Optional[str] = None,
        sensor_type: Optional[str] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message, sensor_id=sensor_id, sensor_type=sensor_type, cause=cause)

