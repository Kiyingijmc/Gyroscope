"""Strategy decision adapter generating candidate proposals (proposals ONLY; no live broker execution authority)."""

from decimal import Decimal
import hashlib
import json
from typing import Optional, Tuple

from gyroscope.contracts.ports import StatePort, StrategyDecisionPort
from gyroscope.contracts.types import (
    AuthorityDomain,
    CandidateDecision,
    DecisionSide,
    OrderType,
    ResearchEvidencePayload,
    SemanticObservationRef,
)
from gyroscope.core.numeric import to_authoritative_decimal


class StrategyAdapter(StrategyDecisionPort):
    """Strategy proposal adapter generating candidate trade decisions."""

    def __init__(self, strategy_version: str = "1.0.0") -> None:
        self.strategy_version = strategy_version

    def evaluate_opportunity(
        self,
        observation_ref: SemanticObservationRef,
        evidence: Optional[ResearchEvidencePayload],
        state_projection: StatePort,
    ) -> Optional[CandidateDecision]:
        """Evaluate market observation and produce a candidate proposal if an opportunity exists."""
        # Baseline deterministic logic: if evidence is present and NIS score is healthy
        if evidence and evidence.nis_score < 3.0:
            target_qty = to_authoritative_decimal("1.00000000")
            limit_price = observation_ref.price

            desc_bytes = f"{observation_ref.semantic_id}:{evidence.evidence_id}:{self.strategy_version}".encode("utf-8")
            dec_id = f"cand_{hashlib.sha256(desc_bytes).hexdigest()[:16]}"
            opp_id = f"opp_{hashlib.sha256(f'{observation_ref.symbol}:{evidence.timestamp_ns}'.encode()).hexdigest()[:16]}"

            return CandidateDecision(
                decision_id=dec_id,
                opportunity_id=opp_id,
                symbol=observation_ref.symbol,
                side=DecisionSide.BUY,
                order_type=OrderType.LIMIT,
                target_quantity=target_qty,
                limit_price=limit_price,
                stop_price=None,
                decision_timestamp_ns=observation_ref.event_timestamp_ns,
                strategy_version=self.strategy_version,
                provenance_node_id=evidence.provenance_node_id,
                observation_refs=(observation_ref.semantic_id,),
            )
        return None
