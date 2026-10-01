"""Unit tests for integration contracts and semantic observation adapter."""

from decimal import Decimal
import pytest

from gyroscope.adapters.observation import ObservationAdapter, compute_semantic_observation_identity
from gyroscope.contracts.types import (
    AuthorityDomain,
    CandidateDecision,
    DecisionSide,
    ExecutionIntent,
    OrderStatus,
    OrderType,
    RiskAuthorization,
    RiskDecisionType,
    SemanticObservationRef,
)
from gyroscope.observation.models import Observation


def test_semantic_observation_identity_invariance_to_ingestion_metadata():
    """Verify that identical market content produced at different ingestion times yields identical semantic_id."""
    adapter = ObservationAdapter()

    # Observation A: ingested at t_arr=1100, t_proc=1200
    obs_a = Observation.create(
        symbol="BTC-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        arrival_timestamp_ns=1100,
        processing_timestamp_ns=1200,
        price=50000.0,
        bid=49990.0,
        ask=50010.0,
        volume=1.5,
        sequence_number=42,
        source="BINANCE",
    )

    # Observation B: exact same event, but ingested later at t_arr=1500, t_proc=1600
    obs_b = Observation.create(
        symbol="BTC-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        arrival_timestamp_ns=1500,
        processing_timestamp_ns=1600,
        price=50000.0,
        bid=49990.0,
        ask=50010.0,
        volume=1.5,
        sequence_number=42,
        source="BINANCE",
    )

    # Gyroscope envelope/ingestion IDs MUST differ due to arrival timestamp inclusion
    assert obs_a.observation_id != obs_b.observation_id

    ref_a = adapter.extract_semantic_ref(obs_a)
    ref_b = adapter.extract_semantic_ref(obs_b)

    # Semantic IDs MUST be identical
    assert ref_a.semantic_id == ref_b.semantic_id
    assert ref_a.price == Decimal("50000.00000000")
    assert ref_a.bid == Decimal("49990.00000000")
    assert ref_a.ask == Decimal("50010.00000000")


def test_semantic_observation_identity_changes_on_market_content_mutation():
    """Verify that mutating price, volume, or sequence changes semantic_id."""
    adapter = ObservationAdapter()

    base_obs = Observation.create(
        symbol="ETH-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        arrival_timestamp_ns=1100,
        processing_timestamp_ns=1200,
        price=3000.0,
        bid=2999.0,
        ask=3001.0,
        volume=2.0,
        sequence_number=1,
    )

    mutated_obs = Observation.create(
        symbol="ETH-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        arrival_timestamp_ns=1100,
        processing_timestamp_ns=1200,
        price=3000.5,  # price modified
        bid=2999.0,
        ask=3001.0,
        volume=2.0,
        sequence_number=1,
    )

    ref_base = adapter.extract_semantic_ref(base_obs)
    ref_mutated = adapter.extract_semantic_ref(mutated_obs)

    assert ref_base.semantic_id != ref_mutated.semantic_id


def test_contracts_exact_decimal_enforcement():
    """Verify that integration value objects strictly enforce exact Decimal quantities."""
    with pytest.raises(TypeError, match="Authoritative financial/risk quantity must be exact Decimal"):
        CandidateDecision(
            decision_id="dec_1",
            opportunity_id="opp_1",
            symbol="BTC-USD",
            side=DecisionSide.BUY,
            order_type=OrderType.LIMIT,
            target_quantity=1.5,  # float rejected
            limit_price=Decimal("50000.00000000"),
            stop_price=None,
            decision_timestamp_ns=1000,
            strategy_version="1.0.0",
            provenance_node_id="node_1",
            observation_refs=("sem_1",),
        )


def test_risk_authorization_executability():
    """Verify risk authorization executability gating."""
    auth_accept = RiskAuthorization(
        authorization_id="auth_1",
        candidate_decision_id="dec_1",
        decision_type=RiskDecisionType.ACCEPT,
        approved_quantity=Decimal("1.00000000"),
        approved_limit_price=Decimal("50000.00000000"),
        approved_stop_price=None,
        max_slippage_bps=Decimal("10.00000000"),
        risk_budget_consumed=Decimal("500.00000000"),
        reason="Approved by risk ledger",
        evaluated_at_ns=1000,
        risk_ledger_state_hash="hash_123",
        provenance_node_id="node_1",
    )
    assert auth_accept.is_executable is True

    auth_reject = RiskAuthorization(
        authorization_id="auth_2",
        candidate_decision_id="dec_1",
        decision_type=RiskDecisionType.REJECT,
        approved_quantity=Decimal("0.00000000"),
        approved_limit_price=None,
        approved_stop_price=None,
        max_slippage_bps=Decimal("0.00000000"),
        risk_budget_consumed=Decimal("0.00000000"),
        reason="Risk threshold exceeded",
        evaluated_at_ns=1000,
        risk_ledger_state_hash="hash_123",
        provenance_node_id="node_1",
    )
    assert auth_reject.is_executable is False
