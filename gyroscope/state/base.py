"""Deterministic state machine concepts, event identity derivation, and canonical state contracts."""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Dict, Optional, Set

from gyroscope.core.exceptions import (
    DeterminismViolationError,
    StateCorruptedException,
    VersionMismatchError,
)


def compute_deterministic_event_id(
    event_type: str,
    event_timestamp_ns: int,
    payload: Dict[str, Any],
    observation_id: Optional[str] = None,
    source: str = "DEFAULT",
    sequence_number: int = 0,
) -> str:
    """Derive a canonical, deterministic SHA-256 event identifier."""
    canonical_dict = {
        "event_timestamp_ns": event_timestamp_ns,
        "event_type": event_type,
        "observation_id": observation_id or "",
        "payload": payload,
        "sequence_number": sequence_number,
        "source": source,
    }
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    h = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return f"evt_{h[:32]}"


@dataclass(frozen=True)
class Event:
    """Deterministic Event representation with derived canonical identity."""
    event_id: str
    event_type: str
    event_timestamp_ns: int
    observation_id: Optional[str] = None
    sequence_number: int = 0
    source: str = "DEFAULT"
    payload: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        event_type: str,
        event_timestamp_ns: int,
        payload: Optional[Dict[str, Any]] = None,
        observation_id: Optional[str] = None,
        sequence_number: int = 0,
        source: str = "DEFAULT",
        event_id: Optional[str] = None,
    ) -> "Event":
        """Factory method to build a validated canonical event with deterministic identity derivation."""
        p = payload or {}
        eid = event_id or compute_deterministic_event_id(
            event_type=event_type,
            event_timestamp_ns=event_timestamp_ns,
            payload=p,
            observation_id=observation_id,
            source=source,
            sequence_number=sequence_number,
        )
        return cls(
            event_id=eid,
            event_type=event_type,
            event_timestamp_ns=event_timestamp_ns,
            observation_id=observation_id,
            sequence_number=sequence_number,
            source=source,
            payload=p,
        )


@dataclass
class SystemState:
    """Deterministic system state holder with canonical semantic payload hashing and snapshot hashing.

    Sequence Semantics:
      - SystemState.sequence_number represents the highest authoritative event sequence number incorporated into the state.
      - For sequence-bearing events (sequence_number > 0), sequence_number updates to event.sequence_number.
      - For sequence_number == 0 events (e.g. unsequenced tick/heartbeat), sequence_number increments by 1 if event sequence is 0.
    """
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

    def compute_state_payload_hash(self) -> str:
        """Calculate canonical SHA-256 hash of the semantic state payload alone."""
        payload = {
            "custom_state": self.custom_state,
            "feature_version": self.feature_version,
            "model_version": self.model_version,
            "processed_event_ids": sorted(list(self._processed_event_ids)),
            "schema_version": self.schema_version,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
        }
        canonical_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def compute_state_hash(self) -> str:
        """Calculate canonical SHA-256 state hash including sequence and configuration header context."""
        payload = {
            "configuration_hash": self.configuration_hash,
            "custom_state": self.custom_state,
            "feature_version": self.feature_version,
            "last_event_id": self.last_event_id,
            "last_event_timestamp_ns": self.last_event_timestamp_ns,
            "model_version": self.model_version,
            "processed_event_ids": sorted(list(self._processed_event_ids)),
            "schema_version": self.schema_version,
            "sequence_number": self.sequence_number,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
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

        if event.sequence_number > 0:
            self.sequence_number = event.sequence_number
        else:
            self.sequence_number += 1

        self.last_event_id = event.event_id
        self.last_event_timestamp_ns = event.event_timestamp_ns
        self._processed_event_ids.add(event.event_id)

        # Apply state updates from event payload
        for k, v in event.payload.items():
            self.custom_state[k] = v

        return True
