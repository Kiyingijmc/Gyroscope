"""Reconciliation authority and recovery engine gating production execution."""

from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
from typing import Dict, List, Optional, Tuple

from gyroscope.contracts.ports import ReconciliationPort, RecoveryPort
from gyroscope.contracts.types import (
    BrokerDeal,
    BrokerOrderRecord,
    ExecutionIntent,
    OrderStatus,
    ReconciliationEvidence,
    RecoveryEvidence,
    RecoveryState,
)


@dataclass(frozen=True)
class BrokerQueryObservation:
    """Explicit broker observation input for reconciliation."""
    query_id: str
    query_timestamp_ns: int
    broker_id: str
    is_fresh: bool
    query_quality_score: float
    order_records: Tuple[BrokerOrderRecord, ...]
    deal_records: Tuple[BrokerDeal, ...] = ()


class ReconciliationEngine(ReconciliationPort):
    """Reconciliation authority verifying broker order and deal state against active execution intents."""

    def reconcile_broker_query(
        self,
        active_intents: List[ExecutionIntent],
        query_obs: BrokerQueryObservation,
    ) -> ReconciliationEvidence:
        """Process explicit broker query observation and produce ReconciliationEvidence covering orders and fill-level deals."""
        matched_count = 0
        open_count = 0
        orphan_count = 0
        mismatch_detected = False

        known_intents = {intent.intent_id: intent for intent in active_intents}
        reconciled_ids = []

        # 1. Order-level reconciliation
        for record in query_obs.order_records:
            if record.intent_id in known_intents:
                matched_count += 1
                reconciled_ids.append(record.intent_id)
                intent = known_intents[record.intent_id]

                # Check attribute mismatches
                if record.symbol != intent.symbol or record.side != intent.side or record.requested_quantity != intent.quantity:
                    mismatch_detected = True

                if record.status in (OrderStatus.SUBMITTED, OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED):
                    open_count += 1
                elif record.status == OrderStatus.UNKNOWN:
                    mismatch_detected = True
            else:
                orphan_count += 1

        # 2. Deal-level fill-ledger reconciliation
        if query_obs.deal_records:
            deals_by_intent: Dict[str, List[BrokerDeal]] = {}
            for deal in query_obs.deal_records:
                if deal.intent_id not in known_intents:
                    orphan_count += 1
                else:
                    deals_by_intent.setdefault(deal.intent_id, []).append(deal)

            for intent_id, deals in deals_by_intent.items():
                intent = known_intents[intent_id]
                total_fill_qty = sum((d.fill_quantity for d in deals), Decimal("0.00000000"))
                if total_fill_qty > intent.quantity:
                    mismatch_detected = True  # Overfill detected!

        rec_bytes = f"{query_obs.query_id}:{matched_count}:{open_count}:{orphan_count}:{mismatch_detected}:{query_obs.is_fresh}".encode("utf-8")
        rec_id = f"rec_{hashlib.sha256(rec_bytes).hexdigest()[:16]}"
        node_id = f"prov_rec_{hashlib.sha256(rec_id.encode()).hexdigest()[:16]}"

        return ReconciliationEvidence(
            reconciliation_id=rec_id,
            broker_query_timestamp_ns=query_obs.query_timestamp_ns,
            is_fresh=query_obs.is_fresh,
            query_quality_score=query_obs.query_quality_score,
            matched_orders_count=matched_count,
            open_orders_count=open_count,
            orphan_orders_count=orphan_count,
            state_mismatch_detected=mismatch_detected,
            provenance_node_id=node_id,
            reconciled_intent_ids=tuple(reconciled_ids),
        )

    def reconcile_broker_state(
        self,
        active_intents: List[ExecutionIntent],
        fresh_broker_orders: List[BrokerOrderRecord],
    ) -> ReconciliationEvidence:
        """Compatibility wrapper for simple broker order lists."""
        query_obs = BrokerQueryObservation(
            query_id="query_compat_1",
            query_timestamp_ns=1000,
            broker_id="BROKER_SIM",
            is_fresh=True,
            query_quality_score=1.0,
            order_records=tuple(fresh_broker_orders),
        )
        return self.reconcile_broker_query(active_intents, query_obs)


class RecoveryEngine(RecoveryPort):
    """Recovery engine governing system state transition and gating production authorization."""

    def evaluate_recovery_status(
        self,
        reconciliation_evidence: ReconciliationEvidence,
    ) -> RecoveryEvidence:
        """Evaluate recovery status from reconciliation evidence."""
        if (
            reconciliation_evidence.is_fresh
            and reconciliation_evidence.query_quality_score >= 0.95
            and not reconciliation_evidence.state_mismatch_detected
            and reconciliation_evidence.orphan_orders_count == 0
        ):
            rec_state = RecoveryState.RECOVERY_COMPLETE
            is_valid = True
        else:
            rec_state = RecoveryState.RECONCILING
            is_valid = False

        recov_id = f"recov_{hashlib.sha256(reconciliation_evidence.reconciliation_id.encode()).hexdigest()[:16]}"
        prov_id = f"prov_recov_{hashlib.sha256(recov_id.encode()).hexdigest()[:16]}"

        return RecoveryEvidence(
            recovery_id=recov_id,
            producer_identity="AUTHORITATIVE_RECOVERY_ENGINE",
            recovery_state=rec_state,
            completed_at_ns=reconciliation_evidence.broker_query_timestamp_ns,
            reconciliation_evidence_id=reconciliation_evidence.reconciliation_id,
            provenance_node_id=prov_id,
            is_valid_evidence=is_valid,
        )
