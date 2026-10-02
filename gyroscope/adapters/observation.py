"""Semantic observation identity adapter separating market content identity from ingestion envelope metadata."""

from decimal import Decimal
import hashlib
import json
from typing import Any, Dict, Optional

from gyroscope.contracts.types import SemanticObservationRef
from gyroscope.core.numeric import to_authoritative_decimal
from gyroscope.observation.models import Observation


def compute_semantic_observation_identity(
    source: str,
    symbol: str,
    timeframe: str,
    event_timestamp_ns: int,
    source_sequence: int,
    price: Decimal,
    bid: Decimal,
    ask: Decimal,
    volume: Decimal,
    source_version: str = "1.0.0",
    parent_semantic_id: Optional[str] = None,
) -> str:
    """Derive a deterministic SHA-256 semantic content identifier.

    Crucially, envelope/ingestion timestamps (arrival_timestamp_ns, processing_timestamp_ns,
    decision_timestamp_ns) ARE EXCLUDED so that two identical market events received at different
    ingestion times share the exact same semantic content identity.
    """
    canonical_dict = {
        "ask": f"{ask:.8f}",
        "bid": f"{bid:.8f}",
        "event_timestamp_ns": event_timestamp_ns,
        "parent_semantic_id": parent_semantic_id or "",
        "price": f"{price:.8f}",
        "source": source,
        "source_sequence": source_sequence,
        "source_version": source_version,
        "symbol": symbol,
        "timeframe": timeframe,
        "volume": f"{volume:.8f}",
    }
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return f"sem_{digest[:32]}"


class ObservationAdapter:
    """Adapter transforming Gyroscope Observation models into semantic content references."""

    def extract_semantic_ref(self, obs: Observation) -> SemanticObservationRef:
        """Extract a SemanticObservationRef with decoupled semantic content identity."""
        price_dec = to_authoritative_decimal(obs.price)
        bid_dec = to_authoritative_decimal(obs.bid)
        ask_dec = to_authoritative_decimal(obs.ask)
        volume_dec = to_authoritative_decimal(obs.volume)

        sem_id = compute_semantic_observation_identity(
            source=obs.source,
            symbol=obs.symbol,
            timeframe=obs.timeframe,
            event_timestamp_ns=obs.event_timestamp_ns,
            source_sequence=obs.sequence_number,
            price=price_dec,
            bid=bid_dec,
            ask=ask_dec,
            volume=volume_dec,
            source_version=obs.source_version,
            parent_semantic_id=obs.parent_observation_id,
        )

        return SemanticObservationRef(
            semantic_id=sem_id,
            envelope_id=obs.observation_id,
            source=obs.source,
            symbol=obs.symbol,
            timeframe=obs.timeframe,
            event_timestamp_ns=obs.event_timestamp_ns,
            price=price_dec,
            bid=bid_dec,
            ask=ask_dec,
            volume=volume_dec,
        )
