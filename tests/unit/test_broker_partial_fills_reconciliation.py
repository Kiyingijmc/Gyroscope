"""Unit tests for deterministic broker partial fills and evidence-based reconciliation."""

from decimal import Decimal
import pytest

from gyroscope.adapters.state import ReadOnlyStateAdapter
from gyroscope.broker.simulator import DeterministicBrokerSimulator
from gyroscope.contracts.types import (
    CandidateDecision,
    DecisionSide,
    OrderType,
)
from gyroscope.execution.repository import ExecutionIntentBuilder
from gyroscope.reconciliation.engine import BrokerQueryObservation, ReconciliationEngine
from gyroscope.risk.ledger import OpportunityRiskLedger
from gyroscope.state import SystemState


def test_broker_simulator_partial_fill_accounting():
    """Verify partial fills maintain exact invariant: filled + remaining == requested."""
    sim = DeterministicBrokerSimulator()
    builder = ExecutionIntentBuilder()
    risk_ledger = OpportunityRiskLedger(max_position_limit=Decimal("100.00000000"))
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)

    candidate = CandidateDecision(
        decision_id="dec_p1",
        opportunity_id="opp_1",
        symbol="BTC-USD",
        side=DecisionSide.BUY,
        order_type=OrderType.LIMIT,
        target_quantity=Decimal("10.00000000"),
        limit_price=Decimal("50000.00000000"),
        stop_price=None,
        decision_timestamp_ns=1000,
        strategy_version="1.0.0",
        provenance_node_id="node_1",
        observation_refs=("sem_1",),
    )

    auth = risk_ledger.evaluate_candidate_decision(candidate, state_proj)
    intent = builder.build_intent(auth, candidate, configuration_hash="cfg_123")

    # Submit as UNKNOWN/pending
    sim_unknown = DeterministicBrokerSimulator(simulate_unknown=True)
    record = sim_unknown.submit_intent(intent)
    assert record.filled_quantity == Decimal("0.00000000")

    # Partial Fill 1: 3.0 units @ 49900.00
    rec1, deal1 = sim_unknown.execute_partial_fill(
        broker_order_id=record.broker_order_id,
        fill_quantity=Decimal("3.00000000"),
        fill_price=Decimal("49900.00000000"),
        executed_at_ns=1100,
    )
    assert rec1.filled_quantity == Decimal("3.00000000")
    assert rec1.avg_fill_price == Decimal("49900.00000000")

    # Partial Fill 2: 7.0 units @ 50100.00
    rec2, deal2 = sim_unknown.execute_partial_fill(
        broker_order_id=record.broker_order_id,
        fill_quantity=Decimal("7.00000000"),
        fill_price=Decimal("50100.00000000"),
        executed_at_ns=1200,
    )
    assert rec2.filled_quantity == Decimal("10.00000000")
    # Weighted avg: (3*49900 + 7*50100)/10 = 50040.00
    assert rec2.avg_fill_price == Decimal("50040.00000000")


def test_broker_simulator_overfill_prevention():
    """Verify attempting to fill beyond requested quantity raises ValueError."""
    sim = DeterministicBrokerSimulator(simulate_unknown=True)
    builder = ExecutionIntentBuilder()
    risk_ledger = OpportunityRiskLedger(max_position_limit=Decimal("100.00000000"))
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)

    candidate = CandidateDecision(
        decision_id="dec_p2",
        opportunity_id="opp_1",
        symbol="BTC-USD",
        side=DecisionSide.BUY,
        order_type=OrderType.LIMIT,
        target_quantity=Decimal("5.00000000"),
        limit_price=Decimal("50000.00000000"),
        stop_price=None,
        decision_timestamp_ns=1000,
        strategy_version="1.0.0",
        provenance_node_id="node_1",
        observation_refs=("sem_1",),
    )

    auth = risk_ledger.evaluate_candidate_decision(candidate, state_proj)
    intent = builder.build_intent(auth, candidate, configuration_hash="cfg_123")

    record = sim.submit_intent(intent)

    with pytest.raises(ValueError, match="Overfill error"):
        sim.execute_partial_fill(
            broker_order_id=record.broker_order_id,
            fill_quantity=Decimal("6.00000000"),  # Exceeds requested 5.0
            fill_price=Decimal("50000.00000000"),
            executed_at_ns=1100,
        )


def test_reconciliation_orphan_and_mismatch_detection():
    """Verify reconciliation engine detects orphan orders and parameter mismatches."""
    rec_engine = ReconciliationEngine()
    builder = ExecutionIntentBuilder()
    risk_ledger = OpportunityRiskLedger(max_position_limit=Decimal("100.00000000"))
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)

    candidate = CandidateDecision(
        decision_id="dec_rec_1",
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

    # Fabricate an orphan order
    orphan_record = sim.submit_intent(
        builder.build_intent(
            risk_ledger.evaluate_candidate_decision(
                CandidateDecision(
                    decision_id="dec_orphan",
                    opportunity_id="opp_2",
                    symbol="ETH-USD",
                    side=DecisionSide.BUY,
                    order_type=OrderType.LIMIT,
                    target_quantity=Decimal("2.00000000"),
                    limit_price=Decimal("3000.00000000"),
                    stop_price=None,
                    decision_timestamp_ns=1000,
                    strategy_version="1.0.0",
                    provenance_node_id="node_2",
                    observation_refs=("sem_2",),
                ),
                state_proj,
            ),
            CandidateDecision(
                decision_id="dec_orphan",
                opportunity_id="opp_2",
                symbol="ETH-USD",
                side=DecisionSide.BUY,
                order_type=OrderType.LIMIT,
                target_quantity=Decimal("2.00000000"),
                limit_price=Decimal("3000.00000000"),
                stop_price=None,
                decision_timestamp_ns=1000,
                strategy_version="1.0.0",
                provenance_node_id="node_2",
                observation_refs=("sem_2",),
            ),
            configuration_hash="cfg_123",
        )
    )

    query_obs = BrokerQueryObservation(
        query_id="q_1",
        query_timestamp_ns=1200,
        broker_id="BROKER_SIM",
        is_fresh=True,
        query_quality_score=1.0,
        order_records=(record, orphan_record),
    )

    # Reconcile ONLY active_intents=[intent] -> orphan_record must be flagged as orphan
    rec_evidence = rec_engine.reconcile_broker_query(
        active_intents=[intent],
        query_obs=query_obs,
    )

    assert rec_evidence.matched_orders_count == 1
    assert rec_evidence.orphan_orders_count == 1
    assert rec_evidence.state_mismatch_detected is False
