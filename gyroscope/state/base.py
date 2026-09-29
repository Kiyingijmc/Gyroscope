"""Deterministic state machine concepts and state wrapper."""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Dict, Optional, Set

from gyroscope.core.exceptions import (
    DeterminismViolationError,
    StateCorruptedException,
    VersionMismatchError,
)


@dataclass(frozen=True)
class Event:
    """Deterministic Event representation."""
    event_id: str
    event_type: str
    event_timestamp_ns: int
    observation_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemState:
    """Deterministic system state holder with canonical hash calculation and event tracking."""
    schema_version: str = "1.0"
    model_version: str = "1.0.0"
    feature_version: str = "1.0.0"
    symbol: str = "GENERIC"
    timeframe: str = "1m"
    sequence_number: int = 0
    last_event_id: str = "INIT"
    last_event_timestamp_ns: int = 0
    configuration_hash: str = "0000000000000000000000000000000000000000000000000000000000000000"
    custom_state: Dict[str, Any] = field(default_factory=dict)
    _processed_event_ids: Set[str] = field(default_factory=set, repr=False)

    def is_event_processed(self, event_id: str) -> bool:
        """Check if an event has already been processed (idempotency check)."""
        return event_id in self._processed_event_ids

    def compute_state_hash(self) -> str:
        """Calculate canonical SHA-256 hash of the mutable state payload."""
        payload = {
            "schema_version": self.schema_version,
            "model_version": self.model_version,
            "feature_version": self.feature_version,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "sequence_number": self.sequence_number,
            "last_event_id": self.last_event_id,
            "last_event_timestamp_ns": self.last_event_timestamp_ns,
            "configuration_hash": self.configuration_hash,
            "custom_state": self.custom_state,
            "processed_event_ids": sorted(list(self._processed_event_ids)),
        }
        canonical_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def process_event(self, event: Event) -> bool:
        """Process an event deterministically. Returns True if processed, False if duplicate skipped."""
        if self.is_event_processed(event.event_id):
            return False

        if event.event_timestamp_ns < self.last_event_timestamp_ns:
            raise DeterminismViolationError(
                f"Out-of-order event timestamp ({event.event_timestamp_ns}) is earlier than state last_event_timestamp_ns ({self.last_event_timestamp_ns})"
            )

        self.sequence_number += 1
        self.last_event_id = event.event_id
        self.last_event_timestamp_ns = event.event_timestamp_ns
        self._processed_event_ids.add(event.event_id)

        # Apply state updates from event payload
        for k, v in event.payload.items():
            self.custom_state[k] = v

        return True
