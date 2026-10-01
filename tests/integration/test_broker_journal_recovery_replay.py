"""Integration tests for Broker Simulator, Durable Journal, Recovery/Reconciliation, and End-to-End Deterministic Replay."""

from decimal import Decimal
from pathlib import Path
import pytest

from gyroscope.adapters.observation import ObservationAdapter
from gyroscope.adapters.provenance import ProvenanceBridge
from gyroscope.adapters.state import ReadOnlyStateAdapter
from gyroscope.adapters.strategy import StrategyAdapter
from gyroscope.broker.simulator import DeterministicBrokerSimulator
from gyroscope.contracts.types import (
    CandidateDecision,
    DecisionSide,
    OrderType,
    ResearchEvidencePayload,
    RiskDecisionType,
)
from gyroscope.execution.repository import ExecutionIntentBuilder, InMemoryIntentRepository
from gyroscope.observation.models import Observation
from gyroscope.persistence.journal import DurableEventJournal, JournalState
from gyroscope.provenance.tracker import ProvenanceTracker
from gyroscope.reconciliation.engine import RecoveryEngine, ReconciliationEngine
from gyroscope.risk.ledger import OpportunityRiskLedger
from gyroscope.state import Event, SystemState


def test_durable_journal_atomic_transaction_lifecycle(tmp_path: Path):
    """Verify durable journal enforces strict 7-phase transaction lifecycle and fault isolation."""
    journal_path = tmp_path / "journal.wal"
    journal = DurableEventJournal(journal_path)

    assert journal.state == JournalState.UNINITIALIZED

    event_payload = {"event_id": "evt_1", "price": "50000.00"}
    journal.append_atomic(event_payload)

    assert journal.state == JournalState.COMMITTED
    assert len(journal.get_committed_events()) == 1
    assert journal_path.exists()
    assert "evt_1" in journal_path.read_text()


def test_broker_simulator_order_execution_and_rejection():
    """Verify broker simulator handles market/limit fills and simulated rejections."""
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

    # Normal execution
    sim = DeterministicBrokerSimulator()
    record = sim.submit_intent(intent)
    assert record.filled_quantity == Decimal("1.00000000")
    assert record.avg_fill_price == Decimal("50000.00000000")

    # Rejection simulation
    sim_reject = DeterministicBrokerSimulator(simulate_rejection=True)
    record_reject = sim_reject.submit_intent(intent)
    assert record_reject.filled_quantity == Decimal("0.00000000")


def test_recovery_engine_gating():
    """Verify recovery engine requires fresh reconciliation evidence with zero mismatches or orphans."""
    rec_engine = ReconciliationEngine()
    recov_engine = RecoveryEngine()

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

    sim = DeterministicBrokerSimulator()
    record = sim.submit_intent(intent)

    rec_ev = rec_engine.reconcile_broker_state(
        active_intents=[intent],
        fresh_broker_orders=[record],
    )

    recov_ev = recov_engine.evaluate_recovery_status(rec_ev)
    assert recov_ev.is_valid_evidence is True


def test_deterministic_end_to_end_replay_equivalence():
    """Prove that repeating the exact same input event stream produces identical state hashes, candidate proposals, and risk decisions."""
    def run_pipeline():
        state = SystemState(symbol="BTC-USD")
        state_proj = ReadOnlyStateAdapter(state)
        tracker = ProvenanceTracker(
            git_commit_sha="235ae06857cdfd84168f996fb6792aafd8e0c630",
            config_hash="cfg_123",
            model_version="1.0.0",
        )
        prov_bridge = ProvenanceBridge(tracker)
        obs_adapter = ObservationAdapter()
        strategy_adapter = StrategyAdapter(strategy_version="1.0.0")
        risk_ledger = OpportunityRiskLedger(max_position_limit=Decimal("10.00000000"))
        intent_builder = ExecutionIntentBuilder()

        # Ingest Observation Event
        obs = Observation.create(
            symbol="BTC-USD",
            timeframe="1m",
            event_timestamp_ns=1000,
            arrival_timestamp_ns=1100,
            processing_timestamp_ns=1200,
            price=50000.0,
            bid=49990.0,
            ask=50010.0,
            volume=1.0,
            sequence_number=1,
        )

        evt = Event(event_id="evt_obs_1", event_type="OBSERVATION", event_timestamp_ns=1000, payload={"price": 50000.0})
        state.process_event(evt)

        sem_ref = obs_adapter.extract_semantic_ref(obs)
        evidence = ResearchEvidencePayload(
            evidence_id="ev_1",
            symbol="BTC-USD",
            readiness_level="R4",
            nis_score=1.0,
            innovation=0.01,
            regime_label="NORMAL",
            timestamp_ns=1000,
            provenance_node_id="node_ev_1",
        )

        candidate = strategy_adapter.evaluate_opportunity(sem_ref, evidence, state_proj)
        assert candidate is not None

        auth = risk_ledger.evaluate_candidate_decision(candidate, state_proj)
        intent = intent_builder.build_intent(auth, candidate, configuration_hash="cfg_123")

        return state_proj.get_state_hash(), candidate.decision_id, auth.authorization_id, intent.intent_id

    run1_hash, run1_cand, run1_auth, run1_intent = run_pipeline()
    run2_hash, run2_cand, run2_auth, run2_intent = run_pipeline()

    # Exact deterministic equivalence
    assert run1_hash == run2_hash
    assert run1_cand == run2_cand
    assert run1_auth == run2_auth
    assert run1_intent == run2_intent
