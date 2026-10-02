"""Unit tests for authoritative external fill identity and idempotent fill deduplication."""

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
from gyroscope.risk.ledger import OpportunityRiskLedger
from gyroscope.state import SystemState


def test_duplicate_external_fill_is_idempotent():
    """Verify receiving the exact same external execution ID twice returns existing fill idempotently without double-counting."""
    sim = DeterministicBrokerSimulator(simulate_unknown=True)
    builder = ExecutionIntentBuilder()
    risk_ledger = OpportunityRiskLedger(max_position_limit=Decimal("100.00000000"))
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)

    candidate = CandidateDecision(
        decision_id="dec_fill_1",
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
    record = sim.submit_intent(intent)

    # Delivery 1: external_execution_id = "exec_1001", qty = 3.0
    rec1, deal1 = sim.execute_partial_fill(
        broker_order_id=record.broker_order_id,
        fill_quantity=Decimal("3.00000000"),
        fill_price=Decimal("50000.00000000"),
        executed_at_ns=1100,
        external_execution_id="exec_1001",
    )
    assert rec1.filled_quantity == Decimal("3.00000000")

    # Delivery 2: EXACT SAME external_execution_id = "exec_1001", qty = 3.0
    rec2, deal2 = sim.execute_partial_fill(
        broker_order_id=record.broker_order_id,
        fill_quantity=Decimal("3.00000000"),
        fill_price=Decimal("50000.00000000"),
        executed_at_ns=1100,
        external_execution_id="exec_1001",
    )

    # Filled quantity MUST remain 3.0 (NOT double-counted to 6.0!)
    assert rec2.filled_quantity == Decimal("3.00000000")
    assert deal1 == deal2


def test_conflicting_external_fill_identity_is_rejected():
    """Verify receiving the same external execution ID with conflicting economic fields raises ValueError."""
    sim = DeterministicBrokerSimulator(simulate_unknown=True)
    builder = ExecutionIntentBuilder()
    risk_ledger = OpportunityRiskLedger(max_position_limit=Decimal("100.00000000"))
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)

    candidate = CandidateDecision(
        decision_id="dec_fill_2",
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
    record = sim.submit_intent(intent)

    sim.execute_partial_fill(
        broker_order_id=record.broker_order_id,
        fill_quantity=Decimal("3.00000000"),
        fill_price=Decimal("50000.00000000"),
        executed_at_ns=1100,
        external_execution_id="exec_1002",
    )

    # Conflicting quantity under same external execution ID -> ValueError
    with pytest.raises(ValueError, match="Conflicting external fill received"):
        sim.execute_partial_fill(
            broker_order_id=record.broker_order_id,
            fill_quantity=Decimal("4.00000000"),  # Conflict!
            fill_price=Decimal("50000.00000000"),
            executed_at_ns=1100,
            external_execution_id="exec_1002",
        )
