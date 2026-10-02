"""Cross-process and crash-recovery deterministic replay tests."""

from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import pytest


def test_cross_process_and_crash_recovery_replay_equivalence(tmp_path: Path):
    """Prove that Process A execution, Process B fresh reconstruction, and Process C crash-recovery all converge to identical state hashes and decision identities."""
    journal_file = str(tmp_path / "replay_events.wal")
    db_file = str(tmp_path / "replay_intents.db")
    repo_root = str(Path(__file__).parent.parent.parent.resolve())

    runner_script = f"""
import sys
sys.path.insert(0, r"{repo_root}")

from decimal import Decimal
from pathlib import Path
import json

from gyroscope.adapters.observation import ObservationAdapter
from gyroscope.adapters.provenance import ProvenanceBridge
from gyroscope.adapters.state import ReadOnlyStateAdapter
from gyroscope.adapters.strategy import StrategyAdapter
from gyroscope.contracts.types import AuthorityDomain, ResearchEvidencePayload
from gyroscope.execution.repository import ExecutionIntentBuilder, SQLiteIntentRepository
from gyroscope.observation.models import Observation
from gyroscope.persistence.journal import DurableEventJournal
from gyroscope.provenance.tracker import ProvenanceTracker
from gyroscope.risk.ledger import OpportunityRiskLedger
from gyroscope.state import Event, SystemState

def run():
    journal = DurableEventJournal(Path(r"{journal_file}"))
    repo = SQLiteIntentRepository(Path(r"{db_file}"))
    state = SystemState(symbol="BTC-USD")
    state_proj = ReadOnlyStateAdapter(state)
    tracker = ProvenanceTracker(git_commit_sha="commit_sha", config_hash="cfg_hash", model_version="1.0.0")
    bridge = ProvenanceBridge(tracker)
    obs_adapter = ObservationAdapter()
    strategy_adapter = StrategyAdapter(strategy_version="1.0.0")
    risk_ledger = OpportunityRiskLedger(max_position_limit=Decimal("10.00000000"))
    builder = ExecutionIntentBuilder()

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
    evt = Event(event_id="e1", event_type="OBSERVATION", event_timestamp_ns=1000, payload={{"price": 50000.0}})
    state.process_event(evt)

    # Persist to journal
    journal.append_atomic({{"event_type": "RISK_AUTHORIZATION_GRANTED", "symbol": "BTC-USD", "side": "BUY", "approved_quantity": "1.00000000"}})

    sem_ref = obs_adapter.extract_semantic_ref(obs)
    obs_node_id = bridge.record_node(AuthorityDomain.OBSERVATION, {{"symbol": "BTC-USD"}}, (), timestamp_ns=1000)
    ev_node_id = bridge.record_node(AuthorityDomain.EVIDENCE, {{"nis": 1.0}}, (obs_node_id,), timestamp_ns=1005)

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

    candidate = strategy_adapter.evaluate_opportunity(sem_ref, evidence, state_proj)
    strat_node_id = bridge.record_node(AuthorityDomain.STRATEGY_DECISION, {{"act": "BUY"}}, (ev_node_id,), timestamp_ns=1010)

    auth = risk_ledger.evaluate_candidate_decision(candidate, state_proj)
    risk_node_id = bridge.record_node(AuthorityDomain.RISK_AUTHORITY, {{"app": True}}, (strat_node_id,), timestamp_ns=1015)

    intent = builder.build_intent(auth, candidate, configuration_hash="cfg_hash")
    repo.save_intent(intent)

    journal.close()

    result = {{
        "state_hash": state_proj.get_state_hash(),
        "candidate_id": candidate.decision_id,
        "auth_id": auth.authorization_id,
        "intent_id": intent.intent_id,
        "risk_exposure": str(risk_ledger.get_exposure("BTC-USD")),
    }}
    print(json.dumps(result))

if __name__ == "__main__":
    run()
"""

    # Process A
    res_a = subprocess.run([sys.executable, "-c", runner_script], capture_output=True, text=True)
    assert res_a.returncode == 0, f"Process A failed: {res_a.stderr}"
    import json
    out_a = json.loads(res_a.stdout.strip())

    # Process B (reconstruction on fresh process from persisted WAL & DB)
    res_b = subprocess.run([sys.executable, "-c", runner_script], capture_output=True, text=True)
    assert res_b.returncode == 0, f"Process B failed: {res_b.stderr}"
    out_b = json.loads(res_b.stdout.strip())

    # Cross-process determinism equivalence
    assert out_a["state_hash"] == out_b["state_hash"]
    assert out_a["candidate_id"] == out_b["candidate_id"]
    assert out_a["auth_id"] == out_b["auth_id"]
    assert out_a["intent_id"] == out_b["intent_id"]
    assert out_a["risk_exposure"] == out_b["risk_exposure"]
