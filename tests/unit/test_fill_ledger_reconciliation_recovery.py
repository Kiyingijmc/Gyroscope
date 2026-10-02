"""Unit tests for complete fill-ledger reconciliation and recovery engine gating."""

from decimal import Decimal
import pytest

from gyroscope.adapters.state import ReadOnlyStateAdapter
from gyroscope.broker.repository import SQLiteFillRepository
from gyroscope.broker.simulator import DeterministicBrokerSimulator
from gyroscope.contracts.types import (
    BrokerDeal,
    CandidateDecision,
    DecisionSide,
    OrderType,
    RecoveryState,
)
from gyroscope.execution.repository import ExecutionIntentBuilder
from gyroscope.reconciliation.engine import BrokerQueryObservation, ReconciliationEngine, RecoveryEngine
from gyroscope.risk.ledger import OpportunityRiskLedger
from gyroscope.state import SystemState


def test_reconciliation_detects_fill_quantity_mismatch_and_gates_recovery():
    """Verify that a discrepancy between fill repository deals and intent requested quantity is flagged as state mismatch and blocks RECOVERY_COMPLETE."""
    rec_engine = ReconciliationEngine()
    recov_engine = RecoveryEngine()
    builder = ExecutionIntentBuilder()
    risk_ledger = OpportunityRiskLedger(max_position_limit=Decimal("100.00000000"))
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)

    candidate = CandidateDecision(
        decision_id="dec_rec_deal_1",
        opportunity_id="opp_1",
        symbol="BTC-USD",
        side=DecisionSide.BUY,
        order_type=OrderType.LIMIT,
        target_quantity=Decimal("1.00000000"),
        limit_price=Decimal("50000.00000000"),
        stop_price=None,
        decision_timestamp_ns=1000,
        strategy_version="1.0.0",
        provenance_node_id="node_1",
        observation_refs=("sem_1",),
    )

    auth = risk_ledger.evaluate_candidate_decision(candidate, state_proj)
    intent = builder.build_intent(auth, candidate, configuration_hash="cfg_123")

    sim = DeterministicBrokerSimulator()
    record = sim.submit_intent(intent)

    # Fabricate an overfill deal in the query observation
    overfill_deal = BrokerDeal(
        deal_id="ext_overfill_1",
        order_id=record.broker_order_id,
        intent_id=intent.intent_id,
        symbol="BTC-USD",
        side=DecisionSide.BUY,
        fill_quantity=Decimal("2.00000000"),  # 2.0 exceeds intent requested 1.0!
        fill_price=Decimal("50000.00000000"),
        fee_amount=Decimal("0.00000000"),
        fee_currency="USD",
        executed_at_ns=1100,
    )

    query_obs = BrokerQueryObservation(
        query_id="query_fill_check",
        query_timestamp_ns=1200,
        broker_id="BROKER_SIM",
        is_fresh=True,
        query_quality_score=1.0,
        order_records=(record,),
        deal_records=(overfill_deal,),
    )

    rec_ev = rec_engine.reconcile_broker_query([intent], query_obs)
    assert rec_ev.state_mismatch_detected is True

    recov_ev = recov_engine.evaluate_recovery_status(rec_ev)
    assert recov_ev.is_valid_evidence is False
    assert recov_ev.recovery_state == RecoveryState.RECONCILING
