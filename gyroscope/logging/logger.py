"""Structured telemetry logger enforcing category discipline."""

from dataclasses import asdict
import json
import logging
from typing import Any, Dict, Optional

from gyroscope.core.types import LogCategory


class StructuredLogger:
    """Structured telemetry logger converting system events into canonical JSON logs."""

    def __init__(self, name: str = "gyroscope", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log_event(
        self,
        category: LogCategory,
        event_name: str,
        timestamp_ns: int,
        payload: Optional[Dict[str, Any]] = None,
        level: int = logging.INFO,
    ) -> Dict[str, Any]:
        """Emit structured JSON telemetry log."""
        log_data = {
            "category": category.value,
            "event_name": event_name,
            "timestamp_ns": timestamp_ns,
            "payload": payload or {},
        }
        msg = json.dumps(log_data, sort_keys=True)
        self.logger.log(level, msg)
        return log_data
