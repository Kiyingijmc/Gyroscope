"""Canonical market data observations and causal validation."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import uuid

from gyroscope.core.exceptions import CausalViolationError


@dataclass(frozen=True)
class Observation:
    """Canonical observation data model with four-timestamp causal contract.

    Invariants:
      1. event_timestamp_ns <= arrival_timestamp_ns
      2. event_timestamp_ns <= processing_timestamp_ns
      3. decision_timestamp_ns >= processing_timestamp_ns if provided
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
        observation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Observation":
        """Factory method to build a validated canonical observation."""
        obs_id = observation_id or f"obs_{uuid.uuid4().hex}"
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
            metadata=metadata or {},
        )
