"""Canonical market data observations, causal validation, and deterministic identity derivation."""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Dict, Optional

from gyroscope.core.exceptions import CausalViolationError


def compute_deterministic_observation_id(
    source: str,
    symbol: str,
    timeframe: str,
    event_timestamp_ns: int,
    arrival_timestamp_ns: int,
    sequence_number: int,
    price: float,
    volume: float = 0.0,
    source_version: str = "1.0.0",
    metadata: Optional[Dict[str, Any]] = None,
    parent_observation_id: Optional[str] = None,
) -> str:
    """Derive a canonical, deterministic, SHA-256 observation identifier."""
    meta_payload = metadata or {}
    canonical_dict = {
        "arrival_timestamp_ns": arrival_timestamp_ns,
        "event_timestamp_ns": event_timestamp_ns,
        "metadata": meta_payload,
        "parent_observation_id": parent_observation_id or "",
        "price": f"{price:.8f}",
        "sequence_number": sequence_number,
        "source": source,
        "source_version": source_version,
        "symbol": symbol,
        "timeframe": timeframe,
        "volume": f"{volume:.8f}",
    }
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    h = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return f"obs_{h[:32]}"


@dataclass(frozen=True)
class Observation:
    """Canonical observation data model with four-timestamp causal contract and deterministic identity.

    Invariants:
      1. event_timestamp_ns <= arrival_timestamp_ns
      2. event_timestamp_ns <= processing_timestamp_ns
      3. decision_timestamp_ns >= processing_timestamp_ns if provided
      4. observation_id is canonically derived when not explicitly provided
    """
    observation_id: str
    symbol: str
    timeframe: str
    event_timestamp_ns: int
    arrival_timestamp_ns: int
    processing_timestamp_ns: int
    decision_timestamp_ns: Optional[int] = None
    sequence_number: int = 0
    price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    spread: float = 0.0
    volume: float = 0.0
    data_quality: float = 1.0
    source: str = "DEFAULT"
    source_version: str = "1.0.0"
    session_state: str = "REGULAR"
    news_state: str = "NONE"
    parent_observation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate causal timestamp order and numeric constraints."""
        if self.event_timestamp_ns <= 0:
            raise CausalViolationError(f"Invalid event_timestamp_ns: {self.event_timestamp_ns}")
        if self.arrival_timestamp_ns < self.event_timestamp_ns:
            raise CausalViolationError(
                f"Arrival time ({self.arrival_timestamp_ns}) cannot precede event time ({self.event_timestamp_ns})"
            )
        if self.processing_timestamp_ns < self.event_timestamp_ns:
            raise CausalViolationError(
                f"Processing time ({self.processing_timestamp_ns}) cannot precede event time ({self.event_timestamp_ns})"
            )
        if self.decision_timestamp_ns is not None and self.decision_timestamp_ns < self.processing_timestamp_ns:
            raise CausalViolationError(
                f"Decision time ({self.decision_timestamp_ns}) cannot precede processing time ({self.processing_timestamp_ns})"
            )

    @classmethod
    def create(
        cls,
        symbol: str,
        timeframe: str,
        event_timestamp_ns: int,
        arrival_timestamp_ns: int,
        processing_timestamp_ns: int,
        price: float,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        volume: float = 0.0,
        sequence_number: int = 0,
        source: str = "DIRECT",
        source_version: str = "1.0.0",
        observation_id: Optional[str] = None,
        parent_observation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Observation":
        """Factory method to build a validated canonical observation with deterministic identity derivation."""
        meta = metadata or {}
        obs_id = observation_id or compute_deterministic_observation_id(
            source=source,
            symbol=symbol,
            timeframe=timeframe,
            event_timestamp_ns=event_timestamp_ns,
            arrival_timestamp_ns=arrival_timestamp_ns,
            sequence_number=sequence_number,
            price=price,
            volume=volume,
            source_version=source_version,
            metadata=meta,
            parent_observation_id=parent_observation_id,
        )
        bid_val = price if bid is None else bid
        ask_val = price if ask is None else ask
        spread_val = max(0.0, ask_val - bid_val)

        return cls(
            observation_id=obs_id,
            symbol=symbol,
            timeframe=timeframe,
            event_timestamp_ns=event_timestamp_ns,
            arrival_timestamp_ns=arrival_timestamp_ns,
            processing_timestamp_ns=processing_timestamp_ns,
            sequence_number=sequence_number,
            price=price,
            bid=bid_val,
            ask=ask_val,
            spread=spread_val,
            volume=volume,
            source=source,
            source_version=source_version,
            parent_observation_id=parent_observation_id,
            metadata=meta,
        )
