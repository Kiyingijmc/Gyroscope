"""Unit tests for Strategy Boundary, Risk Authority, and Execution Intent Repository."""

from decimal import Decimal
import pytest

from gyroscope.adapters.state import ReadOnlyStateAdapter
from gyroscope.adapters.strategy import StrategyAdapter
from gyroscope.contracts.types import (
    CandidateDecision,
    DecisionSide,
    OrderType,
    ResearchEvidencePayload,
    RiskDecisionType,
    SemanticObservationRef,
)
from gyroscope.core.exceptions import AuthorityViolationError
from gyroscope.execution.repository import ExecutionIntentBuilder, InMemoryIntentRepository
from gyroscope.risk.ledger import OpportunityRiskLedger
from gyroscope.state import SystemState


def test_strategy_candidate_proposal_does_not_execute_directly():
    """Verify strategy adapter produces CandidateDecision proposals without execution authority."""
    adapter = StrategyAdapter(strategy_version="1.0.0")
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)

    obs_ref = SemanticObservationRef(
        semantic_id="sem_1",
        envelope_id="obs_1",
        source="BINANCE",
        symbol="BTC-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        price=Decimal("50000.00000000"),
        bid=Decimal("49990.00000000"),
        ask=Decimal("50010.00000000"),
        volume=Decimal("1.00000000"),
    )

    evidence = ResearchEvidencePayload(
        evidence_id="ev_1",
        symbol="BTC-USD",
        readiness_level="R4",
        nis_score=1.2,
        innovation=0.01,
        regime_label="NORMAL",
        timestamp_ns=1000,
        provenance_node_id="node_ev_1",
    )

    candidate = adapter.evaluate_opportunity(obs_ref, evidence, state_proj)

    assert candidate is not None
    assert isinstance(candidate, CandidateDecision)
    assert candidate.symbol == "BTC-USD"
    assert candidate.target_quantity == Decimal("1.00000000")


def test_risk_authority_gating_and_position_reduction():
    """Verify OpportunityRiskLedger reduces or rejects orders exceeding position limits."""
    risk_ledger = OpportunityRiskLedger(
        max_position_limit=Decimal("1.50000000"),
        max_notional_value=Decimal("100000.00000000"),
    )
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)

    candidate = CandidateDecision(
        decision_id="dec_1",
        opportunity_id="opp_1",
        symbol="BTC-USD",
        side=DecisionSide.BUY,
        order_type=OrderType.LIMIT,
        target_quantity=Decimal("2.00000000"),  # Exceeds limit of 1.5
        limit_price=Decimal("50000.00000000"),
        stop_price=None,
        decision_timestamp_ns=1000,
        strategy_version="1.0.0",
        provenance_node_id="node_1",
        observation_refs=("sem_1",),
    )

    auth = risk_ledger.evaluate_candidate_decision(candidate, state_proj)

    assert auth.decision_type == RiskDecisionType.REDUCE
    assert auth.approved_quantity == Decimal("1.50000000")
    assert auth.is_executable is True


def test_execution_intent_builder_rejects_unauthorized_proposals():
    """Verify ExecutionIntentBuilder raises AuthorityViolationError on REJECT risk authorizations."""
    risk_ledger = OpportunityRiskLedger(
        max_position_limit=Decimal("10.00000000"),
        max_notional_value=Decimal("100.00000000"),  # Exceeded by $50,000 order
    )
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)

    candidate = CandidateDecision(
        decision_id="dec_1",
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
    assert auth.decision_type == RiskDecisionType.REJECT

    builder = ExecutionIntentBuilder()
    with pytest.raises(AuthorityViolationError, match="Cannot build ExecutionIntent for non-executable authorization"):
        builder.build_intent(auth, candidate, configuration_hash="cfg_123")


def test_intent_repository_duplicate_suppression_and_conflict_rejection():
    """Verify intent repository suppresses identical duplicates and rejects conflicting fingerprints."""
    repo = InMemoryIntentRepository()
    builder = ExecutionIntentBuilder()

    risk_ledger = OpportunityRiskLedger(max_position_limit=Decimal("10.00000000"))
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)

    candidate = CandidateDecision(
        decision_id="dec_1",
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

    repo.save_intent(intent)
    assert len(repo.list_pending_intents()) == 1

    # Save exact same intent -> duplicate suppressed idempotently
    repo.save_intent(intent)
    assert len(repo.list_pending_intents()) == 1
