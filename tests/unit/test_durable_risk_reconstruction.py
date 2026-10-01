"""Unit tests for OpportunityRiskLedger durable reconstruction and WAL risk authorization event stream replay."""

from decimal import Decimal
import pytest

from gyroscope.adapters.state import ReadOnlyStateAdapter
from gyroscope.contracts.types import CandidateDecision, DecisionSide, OrderType, RiskDecisionType
from gyroscope.risk.ledger import OpportunityRiskLedger
from gyroscope.state import SystemState


def test_durable_risk_ledger_event_reconstruction():
    """Verify that replaying an authoritative event stream reconstructs identical OpportunityRiskLedger exposure and state hash."""
    # Live execution run
    live_ledger = OpportunityRiskLedger(max_position_limit=Decimal("10.00000000"))
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)

    cand1 = CandidateDecision(
        decision_id="dec_r1",
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
    auth1 = live_ledger.evaluate_candidate_decision(cand1, state_proj)
    assert auth1.decision_type == RiskDecisionType.ACCEPT

    cand2 = CandidateDecision(
        decision_id="dec_r2",
        opportunity_id="opp_2",
        symbol="BTC-USD",
        side=DecisionSide.SELL,
        order_type=OrderType.LIMIT,
        target_quantity=Decimal("2.00000000"),
        limit_price=Decimal("50000.00000000"),
        stop_price=None,
        decision_timestamp_ns=1100,
        strategy_version="1.0.0",
        provenance_node_id="node_1",
        observation_refs=("sem_1",),
    )
    auth2 = live_ledger.evaluate_candidate_decision(cand2, state_proj)
    assert auth2.decision_type == RiskDecisionType.ACCEPT

    live_exposure = live_ledger.get_exposure("BTC-USD")
    live_hash = live_ledger.compute_ledger_state_hash()
    assert live_exposure == Decimal("3.00000000")

    # Event stream logged during live execution
    logged_events = [
        {
            "event_type": "RISK_AUTHORIZATION_GRANTED",
            "symbol": "BTC-USD",
            "side": "BUY",
            "approved_quantity": "5.00000000",
        },
        {
            "event_type": "RISK_AUTHORIZATION_GRANTED",
            "symbol": "BTC-USD",
            "side": "SELL",
            "approved_quantity": "2.00000000",
        },
    ]

    # Reconstructed run on fresh ledger
    reconstructed_ledger = OpportunityRiskLedger(max_position_limit=Decimal("10.00000000"))
    reconstructed_ledger.reconstruct_from_events(logged_events)

    rec_exposure = reconstructed_ledger.get_exposure("BTC-USD")
    rec_hash = reconstructed_ledger.compute_ledger_state_hash()

    assert rec_exposure == live_exposure
    assert rec_hash == live_hash
