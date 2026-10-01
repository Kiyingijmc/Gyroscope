"""Unit tests for directional risk accounting and causal provenance ancestry verification."""

from decimal import Decimal
import pytest

from gyroscope.adapters.provenance import ProvenanceBridge
from gyroscope.adapters.state import ReadOnlyStateAdapter
from gyroscope.contracts.types import (
    AuthorityDomain,
    CandidateDecision,
    DecisionSide,
    OrderType,
    RiskDecisionType,
)
from gyroscope.provenance.tracker import ProvenanceTracker
from gyroscope.risk.ledger import OpportunityRiskLedger
from gyroscope.state import SystemState


def test_directional_risk_ledger_buy_sell_accounting():
    """Verify OpportunityRiskLedger correctly computes net position for BUY (+Q) and SELL (-Q)."""
    risk_ledger = OpportunityRiskLedger(max_position_limit=Decimal("10.00000000"))
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)

    # Buy 8.0 units -> Exposure = +8.0
    cand_buy = CandidateDecision(
        decision_id="d_buy_1",
        opportunity_id="opp_1",
        symbol="BTC-USD",
        side=DecisionSide.BUY,
        order_type=OrderType.LIMIT,
        target_quantity=Decimal("8.00000000"),
        limit_price=Decimal("50000.00000000"),
        stop_price=None,
        decision_timestamp_ns=1000,
        strategy_version="1.0.0",
        provenance_node_id="node_1",
        observation_refs=("sem_1",),
    )
    auth_buy = risk_ledger.evaluate_candidate_decision(cand_buy, state_proj)
    assert auth_buy.decision_type == RiskDecisionType.ACCEPT
    assert risk_ledger.get_exposure("BTC-USD") == Decimal("8.00000000")

    # Sell 5.0 units -> Net exposure = +3.0 (NOT 13.0!)
    cand_sell = CandidateDecision(
        decision_id="d_sell_1",
        opportunity_id="opp_2",
        symbol="BTC-USD",
        side=DecisionSide.SELL,
        order_type=OrderType.LIMIT,
        target_quantity=Decimal("5.00000000"),
        limit_price=Decimal("50000.00000000"),
        stop_price=None,
        decision_timestamp_ns=1100,
        strategy_version="1.0.0",
        provenance_node_id="node_1",
        observation_refs=("sem_1",),
    )
    auth_sell = risk_ledger.evaluate_candidate_decision(cand_sell, state_proj)
    assert auth_sell.decision_type == RiskDecisionType.ACCEPT
    assert risk_ledger.get_exposure("BTC-USD") == Decimal("3.00000000")


def test_provenance_bridge_causal_ancestry_verification():
    """Verify ProvenanceBridge verifies complete causal ancestry across authority domains."""
    tracker = ProvenanceTracker(
        git_commit_sha="commit_sha",
        config_hash="cfg_hash",
        model_version="1.0.0",
    )
    bridge = ProvenanceBridge(tracker)

    obs_id = bridge.record_node(AuthorityDomain.OBSERVATION, {"price": "50000.00"}, (), timestamp_ns=1000)
    strat_id = bridge.record_node(AuthorityDomain.STRATEGY_DECISION, {"action": "BUY"}, (obs_id,), timestamp_ns=1100)
    risk_id = bridge.record_node(AuthorityDomain.RISK_AUTHORITY, {"approved": True}, (strat_id,), timestamp_ns=1200)

    # Verify ancestry from risk_id back to OBSERVATION and STRATEGY_DECISION
    assert bridge.verify_causal_ancestry(
        risk_id,
        [AuthorityDomain.OBSERVATION, AuthorityDomain.STRATEGY_DECISION, AuthorityDomain.RISK_AUTHORITY],
    ) is True

    # Reject node creation if required parent does not exist
    with pytest.raises(ValueError, match="Missing required parent provenance node"):
        bridge.record_node(AuthorityDomain.EXECUTION_INTENT, {"intent": 1}, ("non_existent_parent_id",), timestamp_ns=1300)
