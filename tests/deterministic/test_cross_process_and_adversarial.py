"""Cross-process determinism and adversarial security test suite for Gyroscope Phase-1 Kernel."""

import json
import os
import sys
import subprocess
import pytest

from gyroscope.core.exceptions import CausalViolationError, DeterminismViolationError, StateCorruptedException
from gyroscope.observation import Observation, compute_deterministic_observation_id
from gyroscope.provenance.store import InMemoryProvenanceStore
from gyroscope.provenance.tracker import FrozenDict, ProvenanceNode, compute_deterministic_provenance_id
from gyroscope.state import Event, SystemState, deserialize_state, serialize_state
from gyroscope.engine import DeterministicReplayEngine, SnapshotStore


def test_cross_process_observation_identity_determinism():
    """Verify that observation identity derivation produces identical results across separate Python processes."""
    code = """
import json
from gyroscope.observation import compute_deterministic_observation_id

obs_id = compute_deterministic_observation_id(
    source="BINANCE",
    symbol="BTC-USD",
    timeframe="1m",
    event_timestamp_ns=1000000000,
    arrival_timestamp_ns=1000000100,
    processing_timestamp_ns=1000000200,
    decision_timestamp_ns=1000000300,
    sequence_number=42,
    price=50000.0,
    bid=49995.0,
    ask=50005.0,
    volume=1.5,
    data_quality=1.0,
    session_state="REGULAR",
    news_state="NONE",
    source_version="1.0.0",
    metadata={"feed": "primary"},
    parent_observation_id="obs_parent_123",
)
print(json.dumps({"obs_id": obs_id}))
"""
    cmd = [sys.executable, "-c", code]
    out1 = subprocess.check_output(cmd, text=True).strip()
    out2 = subprocess.check_output(cmd, text=True).strip()

    res1 = json.loads(out1)["obs_id"]
    res2 = json.loads(out2)["obs_id"]

    assert res1 == res2, "Cross-process observation identity mismatch"

    # Direct in-process verification
    expected_id = compute_deterministic_observation_id(
        source="BINANCE",
        symbol="BTC-USD",
        timeframe="1m",
        event_timestamp_ns=1000000000,
        arrival_timestamp_ns=1000000100,
        processing_timestamp_ns=1000000200,
        decision_timestamp_ns=1000000300,
        sequence_number=42,
        price=50000.0,
        bid=49995.0,
        ask=50005.0,
        volume=1.5,
        data_quality=1.0,
        session_state="REGULAR",
        news_state="NONE",
        source_version="1.0.0",
        metadata={"feed": "primary"},
        parent_observation_id="obs_parent_123",
    )
    assert res1 == expected_id


def test_cross_process_provenance_identity_determinism():
    """Verify that provenance node identity derivation produces identical results across separate Python processes."""
    code = """
import json
from gyroscope.provenance.tracker import compute_deterministic_provenance_id

node_id = compute_deterministic_provenance_id(
    artifact_type="model_checkpoint",
    timestamp_ns=1700000000000000000,
    git_commit_sha="a0d475a51de8a504346ded5cc84d31ed89e251b3",
    config_hash="cfg_hash_999",
    model_version="1.0.0",
    parent_node_ids=("parent_node_1", "parent_node_2"),
    payload={"weights_hash": "abc123456"},
)
print(json.dumps({"node_id": node_id}))
"""
    cmd = [sys.executable, "-c", code]
    out1 = subprocess.check_output(cmd, text=True).strip()
    out2 = subprocess.check_output(cmd, text=True).strip()

    res1 = json.loads(out1)["node_id"]
    res2 = json.loads(out2)["node_id"]

    assert res1 == res2, "Cross-process provenance node identity mismatch"

    expected_id = compute_deterministic_provenance_id(
        artifact_type="model_checkpoint",
        timestamp_ns=1700000000000000000,
        git_commit_sha="a0d475a51de8a504346ded5cc84d31ed89e251b3",
        config_hash="cfg_hash_999",
        model_version="1.0.0",
        parent_node_ids=("parent_node_1", "parent_node_2"),
        payload={"weights_hash": "abc123456"},
    )
    assert res1 == expected_id


def test_cross_process_replay_engine_determinism():
    """Verify that DeterministicReplayEngine produces identical final state across separate Python processes."""
    code = """
import json
from gyroscope.state import Event, SystemState
from gyroscope.engine import DeterministicReplayEngine

events = [
    Event("e1", "TICK", 1000, sequence_number=1, payload={"price": 100.0}),
    Event("e2", "TICK", 2000, sequence_number=2, payload={"price": 105.0}),
    Event("e3", "TICK", 3000, sequence_number=3, payload={"price": 102.0}),
]

initial_state = SystemState(symbol="BTC-USD")
engine = DeterministicReplayEngine(initial_state=initial_state)
result = engine.replay_stream_with_status(events)

print(json.dumps({
    "final_state_hash": result.final_state.compute_state_hash(),
    "processed_count": result.processed_count,
    "is_authoritative": result.is_authoritative,
}))
"""
    cmd = [sys.executable, "-c", code]
    out1 = subprocess.check_output(cmd, text=True).strip()
    out2 = subprocess.check_output(cmd, text=True).strip()

    res1 = json.loads(out1)
    res2 = json.loads(out2)

    assert res1 == res2, "Cross-process replay state mismatch"
    assert res1["processed_count"] == 3
    assert res1["is_authoritative"] is True


def test_adversarial_observation_forged_id_and_tampering():
    """Verify that forged observation IDs or tampered content are rejected."""
    valid_id = compute_deterministic_observation_id(
        source="BINANCE",
        symbol="BTC-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        arrival_timestamp_ns=2000,
        processing_timestamp_ns=3000,
        sequence_number=1,
        price=100.0,
    )

    # Forged ID attempt
    with pytest.raises(ValueError, match="Cryptographic observation identity mismatch"):
        Observation(
            observation_id="obs_forged_123456789",
            symbol="BTC-USD",
            timeframe="1m",
            event_timestamp_ns=1000,
            arrival_timestamp_ns=2000,
            processing_timestamp_ns=3000,
            sequence_number=1,
            price=100.0,
        )

    # Valid construction via factory
    obs = Observation.create(
        symbol="BTC-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        arrival_timestamp_ns=2000,
        processing_timestamp_ns=3000,
        price=100.0,
        sequence_number=1,
        source="BINANCE",
    )
    assert obs.observation_id == valid_id


def test_adversarial_provenance_id_tampering_and_deep_immutability():
    """Verify that forged provenance node IDs are rejected and deep immutability is strictly enforced."""
    payload = {"nested": {"key": "val"}, "items": [1, 2, 3]}
    node_id = compute_deterministic_provenance_id(
        artifact_type="dataset",
        timestamp_ns=1000,
        git_commit_sha="abc",
        config_hash="cfg",
        model_version="1.0",
        parent_node_ids=(),
        payload=payload,
    )

    # 1. Forged node_id rejection
    with pytest.raises(ValueError, match="Cryptographic provenance identity mismatch"):
        ProvenanceNode(
            node_id="pnode_forged_id",
            parent_node_ids=(),
            timestamp_ns=1000,
            git_commit_sha="abc",
            config_hash="cfg",
            model_version="1.0",
            artifact_type="dataset",
            payload=payload,
        )

    # 2. Construction of valid node
    node = ProvenanceNode(
        node_id=node_id,
        parent_node_ids=(),
        timestamp_ns=1000,
        git_commit_sha="abc",
        config_hash="cfg",
        model_version="1.0",
        artifact_type="dataset",
        payload=payload,
    )

    # 3. Deep immutability assertions
    with pytest.raises((TypeError, AttributeError)):
        node.payload["new_key"] = "forbidden"

    with pytest.raises((TypeError, AttributeError)):
        node.payload["nested"]["key"] = "mutated"

    with pytest.raises((TypeError, AttributeError)):
        node.payload["items"].append(4)

    with pytest.raises((TypeError, AttributeError)):
        node.parent_node_ids.append("parent_3")


def test_adversarial_provenance_store_dag_cycles_and_atomicity():
    """Verify that InMemoryProvenanceStore rejects missing parents, self-cycles, multi-step cycles, and maintains atomicity."""
    store = InMemoryProvenanceStore()

    # Helper to construct valid node
    def make_node(artifact_type, timestamp_ns, git_commit_sha="c", config_hash="cfg", model_version="1.0", parent_node_ids=(), payload=None):
        pld = payload or {}
        nid = compute_deterministic_provenance_id(
            artifact_type=artifact_type,
            timestamp_ns=timestamp_ns,
            git_commit_sha=git_commit_sha,
            config_hash=config_hash,
            model_version=model_version,
            parent_node_ids=parent_node_ids,
            payload=pld,
        )
        return ProvenanceNode(
            node_id=nid,
            parent_node_ids=parent_node_ids,
            timestamp_ns=timestamp_ns,
            git_commit_sha=git_commit_sha,
            config_hash=config_hash,
            model_version=model_version,
            artifact_type=artifact_type,
            payload=pld,
        )

    # 1. Missing parent rejection
    n_child_bad = make_node("model", 1000, parent_node_ids=("non_existent_parent",))
    with pytest.raises(KeyError, match="not found in store"):
        store.record(n_child_bad)

    # 2. Self-cycle rejection
    class MockSelfCycleNode:
        def __init__(self, nid: str):
            self.node_id = nid
            self.parent_node_ids = (nid,)
            self.payload = {}

    self_node = MockSelfCycleNode("prov_self_test")
    with pytest.raises(ValueError, match="Self-referential provenance parent prohibited"):
        store.record(self_node, validate_parents=False)

    # 3. Multi-step cycle rejection (A -> B -> C -> A) and store atomicity
    nodeA = make_node("stepA", 1000)
    store.record(nodeA)

    nodeB = make_node("stepB", 1001, parent_node_ids=(nodeA.node_id,))
    store.record(nodeB)

    nodeC = make_node("stepC", 1002, parent_node_ids=(nodeB.node_id,))
    store.record(nodeC)

    # Conflict attempt: conflicting content on nodeA ID
    class MockConflictingNode:
        def __init__(self, nid: str, parents: tuple):
            self.node_id = nid
            self.parent_node_ids = parents
            self.payload = {"tampered": True}

        def __eq__(self, other):
            return False

    # Case A: Cycle creation attempt
    conflict_cycle = MockConflictingNode(nodeA.node_id, (nodeC.node_id,))
    with pytest.raises(ValueError, match="Arbitrary cycle detected in provenance graph"):
        store.record(conflict_cycle)

    # Case B: Conflicting node with no cycle
    conflict_content = MockConflictingNode(nodeA.node_id, ())
    with pytest.raises(ValueError, match="Attempted to mutate historical provenance node"):
        store.record(conflict_content)

    assert len(store._nodes) == 3, "Store must remain byte-for-byte atomic and unchanged on rejection"


def test_adversarial_sequence_monotonicity_and_replay_attacks():
    """Verify state rejection for sequence regressions, duplicate sequence numbers, and snapshot tampering."""
    state = SystemState(symbol="BTC-USD")

    e1 = Event("e1", "TICK", 1000, sequence_number=1, payload={"price": 100.0})
    e2 = Event("e2", "TICK", 2000, sequence_number=2, payload={"price": 102.0})

    state.process_event(e1)
    state.process_event(e2)

    # 1. Sequence regression attempt
    e_regress = Event("e_regress", "TICK", 3000, sequence_number=1, payload={"price": 101.0})
    with pytest.raises(DeterminismViolationError, match="Sequence regression detected"):
        state.process_event(e_regress)

    # 2. Duplicate sequence attempt
    e_dup = Event("e_dup", "TICK", 3000, sequence_number=2, payload={"price": 102.0})
    with pytest.raises(DeterminismViolationError, match="Sequence regression detected"):
        state.process_event(e_dup)

    # 3. Snapshot tampering attacks
    json_str = serialize_state(state)
    data = json.loads(json_str)

    # Tamper snapshot_hash
    data_bad_snap = dict(data)
    data_bad_snap["snapshot_hash"] = "0" * 64
    with pytest.raises(StateCorruptedException, match="Snapshot envelope integrity failure"):
        deserialize_state(json.dumps(data_bad_snap))

    # Tamper state_payload_hash
    data_bad_payload = dict(data)
    data_bad_payload["state_payload_hash"] = "0" * 64
    # Recompute snapshot_hash for envelope
    from gyroscope.state.serialization import compute_snapshot_hash
    data_bad_payload["snapshot_hash"] = compute_snapshot_hash(data_bad_payload)
    with pytest.raises(StateCorruptedException, match="State payload hash mismatch"):
        deserialize_state(json.dumps(data_bad_payload))

    # Tamper state_hash
    data_bad_state_hash = dict(data)
    data_bad_state_hash["state_hash"] = "0" * 64
    data_bad_state_hash["snapshot_hash"] = compute_snapshot_hash(data_bad_state_hash)
    with pytest.raises(StateCorruptedException, match="State hash integrity failure"):
        deserialize_state(json.dumps(data_bad_state_hash))
