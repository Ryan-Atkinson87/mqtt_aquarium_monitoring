"""
output_manager.py
"""
import logging
from typing import Iterable, Mapping, Any, List


class OutputManager:
    """
    Manages output devices such as displays.

    Responsible for fanning out telemetry snapshots to outputs while
    isolating failures so outputs can never crash the agent.
    """

    def __init__(
        self,
        outputs: Iterable[Any],
        logger: logging.Logger,
    ) -> None:
        self._outputs: List[Any] = list(outputs)
        self._logger = logger

    def render(self, snapshot: Mapping[str, Any]) -> None:
        """
        Render a telemetry snapshot to all configured outputs.

        Args:
            snapshot: Telemetry snapshot containing ts, device_name, and values.
        """
        for output in self._outputs:
            try:
                output.render(snapshot)
            except Exception:
                self._logger.warning(
                    "Output render failed, disabling output",
                    exc_info=True,
                )
                try:
                    self._outputs.remove(output)
                except ValueError:
                    pass
