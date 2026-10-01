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
    processing_timestamp_ns: int,
    sequence_number: int,
    price: float,
    bid: Optional[float] = None,
    ask: Optional[float] = None,
    volume: float = 0.0,
    data_quality: float = 1.0,
    session_state: str = "REGULAR",
    news_state: str = "NONE",
    decision_timestamp_ns: Optional[int] = None,
    source_version: str = "1.0.0",
    metadata: Optional[Dict[str, Any]] = None,
    parent_observation_id: Optional[str] = None,
) -> str:
    """Derive a canonical, deterministic, SHA-256 observation identifier.

    Formal Observation Identity Field Matrix:
    - symbol: IDENTITY-BOUND (Instrument identity)
    - timeframe: IDENTITY-BOUND (Temporal aggregation context)
    - event_timestamp_ns: IDENTITY-BOUND (Source observation timestamp)
    - arrival_timestamp_ns: IDENTITY-BOUND (Ingestion boundary timestamp)
    - processing_timestamp_ns: IDENTITY-BOUND (System processing timestamp)
    - decision_timestamp_ns: IDENTITY-BOUND (Optional risk/execution decision timestamp)
    - sequence_number: IDENTITY-BOUND (Source sequence number)
    - price: IDENTITY-BOUND (Observed trade/mid price)
    - bid: IDENTITY-BOUND (Observed bid price)
    - ask: IDENTITY-BOUND (Observed ask price)
    - spread: DERIVED (ask - bid, computed automatically)
    - volume: IDENTITY-BOUND (Observed volume)
    - data_quality: IDENTITY-BOUND (Data cleanliness/feed quality score)
    - source: IDENTITY-BOUND (Venue/broker identifier)
    - source_version: IDENTITY-BOUND (Venue feed schema version)
    - session_state: IDENTITY-BOUND (Trading session classification)
    - news_state: IDENTITY-BOUND (News event window classification)
    - parent_observation_id: IDENTITY-BOUND (Causal lineage reference)
    - metadata: IDENTITY-BOUND (Additional semantic key-value pairs)
    """
    meta_payload = metadata or {}
    bid_val = price if bid is None else bid
    ask_val = price if ask is None else ask
    canonical_dict = {
        "arrival_timestamp_ns": arrival_timestamp_ns,
        "ask": f"{ask_val:.8f}",
        "bid": f"{bid_val:.8f}",
        "data_quality": f"{data_quality:.6f}",
        "decision_timestamp_ns": decision_timestamp_ns or 0,
        "event_timestamp_ns": event_timestamp_ns,
        "metadata": meta_payload,
        "news_state": news_state,
        "parent_observation_id": parent_observation_id or "",
        "price": f"{price:.8f}",
        "processing_timestamp_ns": processing_timestamp_ns,
        "sequence_number": sequence_number,
        "session_state": session_state,
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
    """Canonical observation data model with four-timestamp causal contract and cryptographic identity binding.

    Invariants:
      1. event_timestamp_ns <= arrival_timestamp_ns
      2. event_timestamp_ns <= processing_timestamp_ns
      3. decision_timestamp_ns >= processing_timestamp_ns if provided
      4. observation_id is strictly cryptographically bound to material content
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
        """Validate causal timestamp order, numeric constraints, and identity integrity."""
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

        computed_id = compute_deterministic_observation_id(
            source=self.source,
            symbol=self.symbol,
            timeframe=self.timeframe,
            event_timestamp_ns=self.event_timestamp_ns,
            arrival_timestamp_ns=self.arrival_timestamp_ns,
            processing_timestamp_ns=self.processing_timestamp_ns,
            decision_timestamp_ns=self.decision_timestamp_ns,
            sequence_number=self.sequence_number,
            price=self.price,
            bid=self.bid,
            ask=self.ask,
            volume=self.volume,
            data_quality=self.data_quality,
            session_state=self.session_state,
            news_state=self.news_state,
            source_version=self.source_version,
            metadata=self.metadata,
            parent_observation_id=self.parent_observation_id,
        )

        if self.observation_id != computed_id:
            raise ValueError(
                f"Cryptographic observation identity mismatch: provided observation_id '{self.observation_id}' "
                f"does not match computed canonical observation_id '{computed_id}'"
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
        data_quality: float = 1.0,
        session_state: str = "REGULAR",
        news_state: str = "NONE",
        decision_timestamp_ns: Optional[int] = None,
        sequence_number: int = 0,
        source: str = "DIRECT",
        source_version: str = "1.0.0",
        observation_id: Optional[str] = None,
        parent_observation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Observation":
        """Factory method to build a validated canonical observation with deterministic identity derivation."""
        meta = metadata or {}
        bid_val = price if bid is None else bid
        ask_val = price if ask is None else ask
        spread_val = max(0.0, ask_val - bid_val)

        computed_id = compute_deterministic_observation_id(
            source=source,
            symbol=symbol,
            timeframe=timeframe,
            event_timestamp_ns=event_timestamp_ns,
            arrival_timestamp_ns=arrival_timestamp_ns,
            processing_timestamp_ns=processing_timestamp_ns,
            decision_timestamp_ns=decision_timestamp_ns,
            sequence_number=sequence_number,
            price=price,
            bid=bid_val,
            ask=ask_val,
            volume=volume,
            data_quality=data_quality,
            session_state=session_state,
            news_state=news_state,
            source_version=source_version,
            metadata=meta,
            parent_observation_id=parent_observation_id,
        )

        obs_id = observation_id or computed_id

        return cls(
            observation_id=obs_id,
            symbol=symbol,
            timeframe=timeframe,
            event_timestamp_ns=event_timestamp_ns,
            arrival_timestamp_ns=arrival_timestamp_ns,
            processing_timestamp_ns=processing_timestamp_ns,
            decision_timestamp_ns=decision_timestamp_ns,
            sequence_number=sequence_number,
            price=price,
            bid=bid_val,
            ask=ask_val,
            spread=spread_val,
            volume=volume,
            data_quality=data_quality,
            source=source,
            source_version=source_version,
            session_state=session_state,
            news_state=news_state,
            parent_observation_id=parent_observation_id,
            metadata=meta,
        )
