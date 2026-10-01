"""True crash/restart reconstruction integration tests."""

from decimal import Decimal
from pathlib import Path
import json
import pytest

from gyroscope.adapters.observation import ObservationAdapter
from gyroscope.adapters.provenance import ProvenanceBridge
from gyroscope.adapters.state import ReadOnlyStateAdapter
from gyroscope.adapters.strategy import StrategyAdapter
from gyroscope.broker.repository import SQLiteFillRepository
from gyroscope.broker.simulator import DeterministicBrokerSimulator
from gyroscope.contracts.types import AuthorityDomain, ResearchEvidencePayload
from gyroscope.execution.repository import ExecutionIntentBuilder, SQLiteIntentRepository
from gyroscope.observation.models import Observation
from gyroscope.persistence.journal import DurableEventJournal
from gyroscope.provenance.tracker import ProvenanceTracker
from gyroscope.reconciliation.engine import BrokerQueryObservation, ReconciliationEngine, RecoveryEngine
from gyroscope.risk.ledger import OpportunityRiskLedger
from gyroscope.state import Event, SystemState


def test_true_crash_recovery_reconstruction(tmp_path: Path):
    """Process A executes pipeline, writes WAL, intents DB, and fills DB, then terminates. Process B recovers exclusively from durable artifacts without re-running pipeline."""
    wal_file = tmp_path / "durable_events.wal"
    intents_db = tmp_path / "intents.db"
    fills_db = tmp_path / "fills.db"

    # --- PROCESS A: Live Execution ---
    j_a = DurableEventJournal(wal_file)
    intent_repo_a = SQLiteIntentRepository(intents_db)
    fill_repo_a = SQLiteFillRepository(fills_db)
    sim_a = DeterministicBrokerSimulator(fill_repository=fill_repo_a)
    state_a = SystemState(symbol="BTC-USD")
    state_proj_a = ReadOnlyStateAdapter(state_a)
    tracker_a = ProvenanceTracker(git_commit_sha="commit_sha", config_hash="cfg_hash", model_version="1.0.0")
    bridge_a = ProvenanceBridge(tracker_a)
    obs_adapter = ObservationAdapter()
    strategy_adapter = StrategyAdapter(strategy_version="1.0.0")
    risk_ledger_a = OpportunityRiskLedger(max_position_limit=Decimal("10.00000000"))
    intent_builder = ExecutionIntentBuilder()

    # Ingest Observation & Event
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
    evt = Event(event_id="e1", event_type="OBSERVATION", event_timestamp_ns=1000, payload={"price": 50000.0})
    state_a.process_event(evt)

    # Strategy -> Risk
    sem_ref = obs_adapter.extract_semantic_ref(obs)
    obs_node_id = bridge_a.record_node(AuthorityDomain.OBSERVATION, {"symbol": "BTC-USD"}, (), timestamp_ns=1000)
    ev_node_id = bridge_a.record_node(AuthorityDomain.EVIDENCE, {"nis": 1.0}, (obs_node_id,), timestamp_ns=1005)
    evidence = ResearchEvidencePayload(
        evidence_id="ev_1",
        symbol="BTC-USD",
        readiness_level="R4",
        nis_score=1.0,
        innovation=0.01,
        regime_label="NORMAL",
        timestamp_ns=1000,
        provenance_node_id=ev_node_id,
    )

    candidate = strategy_adapter.evaluate_opportunity(sem_ref, evidence, state_proj_a)
    strat_node_id = bridge_a.record_node(AuthorityDomain.STRATEGY_DECISION, {"act": "BUY"}, (ev_node_id,), timestamp_ns=1010)

    auth = risk_ledger_a.evaluate_candidate_decision(candidate, state_proj_a)
    risk_node_id = bridge_a.record_node(AuthorityDomain.RISK_AUTHORITY, {"app": True}, (strat_node_id,), timestamp_ns=1015)

    # Persist risk event to WAL
    j_a.append_atomic(
        {
            "event_type": "RISK_AUTHORIZATION_GRANTED",
            "symbol": "BTC-USD",
            "side": candidate.side.value,
            "approved_quantity": f"{auth.approved_quantity:.8f}",
        }
    )

    # Intent Persistence & Execution
    intent = intent_builder.build_intent(auth, candidate, configuration_hash="cfg_hash")
    intent_repo_a.save_intent(intent)
    order_record = sim_a.submit_intent(intent)

    # Record Process A canonical metrics
    state_hash_a = state_proj_a.get_state_hash()
    risk_hash_a = risk_ledger_a.compute_ledger_state_hash()
    fill_hash_a = fill_repo_a.compute_ledger_hash()

    # SIMULATE PROCESS TERMINATION (CRASH)
    j_a.close()

    # --- PROCESS B: Crash Recovery & State Reconstruction (Without running business pipeline!) ---
    j_b = DurableEventJournal(wal_file)
    intent_repo_b = SQLiteIntentRepository(intents_db)
    fill_repo_b = SQLiteFillRepository(fills_db)
    risk_ledger_b = OpportunityRiskLedger(max_position_limit=Decimal("10.00000000"))

    # Reconstruct risk exposure from WAL committed events
    risk_ledger_b.reconstruct_from_events(j_b.get_committed_events())

    # Recover intents and fills
    recovered_intents = intent_repo_b.list_pending_intents()
    recovered_deals = fill_repo_b.get_deals_for_intent(intent.intent_id)

    # Compare Process A vs Process B recovered state
    assert len(recovered_intents) == 1
    assert recovered_intents[0].intent_id == intent.intent_id
    assert risk_ledger_b.compute_ledger_state_hash() == risk_hash_a
    assert fill_repo_b.compute_ledger_hash() == fill_hash_a
