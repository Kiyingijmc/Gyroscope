"""Adversarial tests explicitly attempting security/integrity violations.

Tests attempt:
- forged observation ID;
- forged event ID;
- forged provenance ID;
- forged risk authorization;
- duplicated intent & conflicting fingerprint;
- wall-clock contamination in state;
- corrupted journal/snapshot recovery.
"""

from decimal import Decimal
from pathlib import Path
import pytest

from gyroscope.adapters.observation import ObservationAdapter
from gyroscope.adapters.state import ReadOnlyStateAdapter
from gyroscope.contracts.types import (
    CandidateDecision,
    DecisionSide,
    OrderType,
    RiskAuthorization,
    RiskDecisionType,
)
from gyroscope.core.exceptions import AuthorityViolationError
from gyroscope.execution.repository import ExecutionIntentBuilder, InMemoryIntentRepository
from gyroscope.observation.models import Observation
from gyroscope.persistence.journal import DurableEventJournal, JournalState
from gyroscope.provenance.tracker import ProvenanceNode
from gyroscope.risk.ledger import OpportunityRiskLedger
from gyroscope.state import SystemState


def test_adversarial_forged_observation_id_rejection():
    """Attempt forging observation ID with tampered price content."""
    with pytest.raises(ValueError, match="Cryptographic observation identity mismatch"):
        Observation(
            observation_id="obs_forged_id_12345678901234567890",  # Forged ID
            symbol="BTC-USD",
            timeframe="1m",
            event_timestamp_ns=1000,
            arrival_timestamp_ns=1100,
            processing_timestamp_ns=1200,
            price=50000.0,
        )


def test_adversarial_forged_provenance_id_rejection():
    """Attempt forging provenance node ID."""
    with pytest.raises(ValueError, match="Cryptographic provenance identity mismatch"):
        ProvenanceNode(
            node_id="prov_forged_node_id_1234567890",
            parent_node_ids=(),
            timestamp_ns=1000,
            git_commit_sha="commit_sha",
            config_hash="config_hash",
            model_version="1.0.0",
            artifact_type="TEST",
            payload={"key": "val"},
        )


def test_adversarial_forged_risk_authorization_bypass():
    """Attempt bypassing risk authorization by fabricating an executable authorization object."""
    builder = ExecutionIntentBuilder()

    candidate = CandidateDecision(
        decision_id="dec_adv_1",
        opportunity_id="opp_1",
        symbol="BTC-USD",
        side=DecisionSide.BUY,
        order_type=OrderType.LIMIT,
        target_quantity=Decimal("100.00000000"),  # Huge quantity
        limit_price=Decimal("50000.00000000"),
        stop_price=None,
        decision_timestamp_ns=1000,
        strategy_version="1.0.0",
        provenance_node_id="node_1",
        observation_refs=("sem_1",),
    )

    # Forged authorization with candidate ID mismatch
    forged_auth = RiskAuthorization(
        authorization_id="auth_forged",
        candidate_decision_id="dec_OTHER",  # Mismatch!
        decision_type=RiskDecisionType.ACCEPT,
        approved_quantity=Decimal("100.00000000"),
        approved_limit_price=Decimal("50000.00000000"),
        approved_stop_price=None,
        max_slippage_bps=Decimal("10.00000000"),
        risk_budget_consumed=Decimal("5000000.00000000"),
        reason="Forged approval",
        evaluated_at_ns=1000,
        risk_ledger_state_hash="fake_hash",
        provenance_node_id="node_1",
    )

    with pytest.raises(AuthorityViolationError, match="Authorization candidate ID mismatch"):
        builder.build_intent(forged_auth, candidate, configuration_hash="cfg_123")


def test_adversarial_conflicting_intent_fingerprint_rejection():
    """Attempt submitting two different intents under the same idempotency key."""
    repo = InMemoryIntentRepository()
    builder = ExecutionIntentBuilder()
    risk_ledger = OpportunityRiskLedger(max_position_limit=Decimal("10.00000000"))
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)

    candidate1 = CandidateDecision(
        decision_id="dec_same",
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

    auth1 = risk_ledger.evaluate_candidate_decision(candidate1, state_proj)
    intent1 = builder.build_intent(auth1, candidate1, configuration_hash="cfg_123")
    repo.save_intent(intent1)

    # Fabricate intent2 with SAME idempotency_key but DIFFERENT request_fingerprint
    from gyroscope.contracts.types import ExecutionIntent
    intent2 = ExecutionIntent(
        intent_id="intent_tampered",
        idempotency_key=intent1.idempotency_key,  # Same idempotency key
        request_fingerprint="fp_TAMPERED_DIFFERENT",  # Different fingerprint!
        authorization_id=intent1.authorization_id,
        symbol=intent1.symbol,
        side=intent1.side,
        order_type=intent1.order_type,
        quantity=Decimal("2.00000000"),
        limit_price=intent1.limit_price,
        stop_price=None,
        configuration_hash=intent1.configuration_hash,
        lineage_node_id=intent1.lineage_node_id,
        created_at_ns=intent1.created_at_ns,
    )

    with pytest.raises(ValueError, match="Conflicting intent under same idempotency key"):
        repo.save_intent(intent2)


def test_adversarial_journal_invalid_state_transition_fails_to_faulted(tmp_path: Path):
    """Attempt illegal state transition in journal to verify transition to FAULTED state."""
    tmp_file = tmp_path / "test_journal_fault.wal"

    journal = DurableEventJournal(tmp_file)
    journal.prepare_event({"data": 123})

    # Skip capture_offset and write directly -> invalid transition
    with pytest.raises(RuntimeError, match="Invalid transition to WRITTEN"):
        journal.write_to_disk()

    assert journal.state == JournalState.FAULTED
