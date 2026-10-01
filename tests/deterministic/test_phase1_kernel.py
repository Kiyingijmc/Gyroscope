"""Comprehensive Phase 1 Deterministic Kernel Final Forensic Closure Test Suite.

Validates:
- Sequence monotonicity & regression/duplicate rejection
- Cryptographic content-binding for provenance node identity and observation identity
- Arbitrary DAG cycle prevention (A -> B -> C -> A) hitting public store boundary
- Mandatory state_payload_hash verification & envelope tamper detection
- Multi-boundary snapshot/replay equivalence
- Subprocess process-boundary reconstruction
"""

from decimal import Decimal
import json
import subprocess
import sys

import pytest

from gyroscope.core.exceptions import CausalViolationError, DeterminismViolationError, StateCorruptedException
from gyroscope.engine import (
    CausalOrderingBuffer,
    DeterministicReplayEngine,
    GapDetector,
    GapStatus,
    ReplayResult,
    ReplayStatus,
    SnapshotStore,
)
from gyroscope.observation import Observation, compute_deterministic_observation_id
from gyroscope.provenance import (
    InMemoryProvenanceStore,
    ProvenanceNode,
    ProvenanceTracker,
    compute_deterministic_provenance_id,
)
from gyroscope.state import Event, SystemState, compute_deterministic_event_id, serialize_state, deserialize_state


def test_sequence_monotonicity_and_regression_rejection():
    """SystemState rejects sequence regressions and duplicate sequences with DeterminismViolationError atomically."""
    state = SystemState(symbol="BTC-USD", sequence_number=5, last_event_timestamp_ns=5000, last_event_id="evt_5")
    initial_hash = state.compute_state_hash()
    initial_payload_hash = state.compute_state_payload_hash()

    # Event with sequence 3 (regression from 5)
    reordered_event = Event.create(
        event_type="TICK",
        event_timestamp_ns=6000,
        sequence_number=3,
        payload={"hacked_price": 100.0},
    )

    with pytest.raises(DeterminismViolationError, match="Sequence regression detected"):
        state.process_event(reordered_event)

    # Event with duplicate sequence 5 (new distinct event with sequence 5)
    dup_seq_event = Event.create(
        event_type="TICK",
        event_timestamp_ns=6100,
        sequence_number=5,
        payload={"hacked_price": 105.0},
    )

    with pytest.raises(DeterminismViolationError, match="Sequence regression detected"):
        state.process_event(dup_seq_event)

    # Verify state immutability across all fields after rejection
    assert state.sequence_number == 5
    assert state.last_event_timestamp_ns == 5000
    assert state.last_event_id == "evt_5"
    assert state.compute_state_hash() == initial_hash
    assert state.compute_state_payload_hash() == initial_payload_hash
    assert "hacked_price" not in state.custom_state


def test_atomic_rejection_boundary_matrix():
    """Formal atomic rejection boundary test matrix A through N proving zero observable state side-effects and distinguishing REJECTED_ATOMICALLY from ACCEPTED_IDEMPOTENTLY_WITH_NO_STATE_CHANGE."""
    # Boundary A: Sequence regression (REJECTED_ATOMICALLY)
    state = SystemState(symbol="BTC-USD", sequence_number=5, last_event_timestamp_ns=5000, last_event_id="evt_5", custom_state={"initial": True})
    hash_before = state.compute_state_hash()
    pld_hash_before = state.compute_state_payload_hash()

    reg_event = Event.create(event_type="TICK", event_timestamp_ns=6000, sequence_number=3, payload={"tampered": True})
    with pytest.raises(DeterminismViolationError, match="Sequence regression detected"):
        state.process_event(reg_event)

    assert state.sequence_number == 5
    assert state.last_event_timestamp_ns == 5000
    assert state.last_event_id == "evt_5"
    assert state.custom_state == {"initial": True}
    assert state.compute_state_hash() == hash_before
    assert state.compute_state_payload_hash() == pld_hash_before

    # Boundary B: Duplicate event (ACCEPTED_IDEMPOTENTLY_WITH_NO_STATE_CHANGE)
    # Process valid first event (sequence 6)
    first_event = Event.create(event_type="TICK", event_timestamp_ns=5050, sequence_number=6, payload={"initial": True}, event_id="evt_6")
    proc1 = state.process_event(first_event)
    assert proc1 is True
    post_first_hash = state.compute_state_hash()

    # Re-submit exact same event
    proc2 = state.process_event(first_event)
    assert proc2 is False
    assert state.sequence_number == 6
    assert state.compute_state_hash() == post_first_hash

    # Boundary C: Missing provenance parent (REJECTED_ATOMICALLY)
    store = InMemoryProvenanceStore()
    tracker = ProvenanceTracker("sha1", "cfg1", "1.0.0")

    class MissingParentNode:
        def __init__(self):
            self.node_id = "prov_node_missing_parent"
            self.parent_node_ids = ("prov_missing_parent_999",)
            self.payload = {"data": 1}

    missing_p_node = MissingParentNode()
    nodes_before_missing = dict(store._nodes)
    with pytest.raises(KeyError, match="Parent provenance node 'prov_missing_parent_999' not found"):
        store.record(missing_p_node)
    assert store._nodes == nodes_before_missing

    # Boundary D: Provenance self-cycle (REJECTED_ATOMICALLY)
    class SelfCycleNode:
        def __init__(self):
            self.node_id = "prov_self"
            self.parent_node_ids = ("prov_self",)
            self.payload = {}

    nodes_before_self = dict(store._nodes)
    with pytest.raises(ValueError, match="Self-referential provenance parent prohibited"):
        store.record(SelfCycleNode())
    assert store._nodes == nodes_before_self

    # Boundary E: Provenance direct cycle A -> B -> A (REJECTED_ATOMICALLY)
    nA = tracker.record("OBS", 1000, {"step": "A"})
    store.record(nA)
    nB = tracker.record("STATE", 1100, {"step": "B"}, parent_node_ids=[nA.node_id])
    store.record(nB)

    class DirectCycleNode:
        def __init__(self, nid: str, parents: tuple):
            self.node_id = nid
            self.parent_node_ids = parents
            self.payload = {"step": "cycle"}

    nodes_before_direct = dict(store._nodes)
    with pytest.raises(ValueError, match="Arbitrary cycle detected"):
        store.record(DirectCycleNode(nA.node_id, (nB.node_id,)))
    assert store._nodes == nodes_before_direct

    # Boundary F: Provenance transitive cycle A -> B -> C -> D -> A (REJECTED_ATOMICALLY)
    nC = tracker.record("STATE", 1200, {"step": "C"}, parent_node_ids=[nB.node_id])
    store.record(nC)
    nD = tracker.record("STATE", 1300, {"step": "D"}, parent_node_ids=[nC.node_id])
    store.record(nD)

    nodes_before_transitive = dict(store._nodes)
    with pytest.raises(ValueError, match="Arbitrary cycle detected"):
        store.record(DirectCycleNode(nA.node_id, (nD.node_id,)))
    assert store._nodes == nodes_before_transitive

    # Boundary G: Forged provenance identity (REJECTED_ATOMICALLY)
    with pytest.raises(ValueError, match="Cryptographic provenance identity mismatch"):
        ProvenanceNode(
            node_id="prov_forged_id_000000000000000000",
            parent_node_ids=(),
            timestamp_ns=1000,
            git_commit_sha="sha1",
            config_hash="cfg1",
            model_version="1.0.0",
            artifact_type="OBS",
            payload={"test": True},
        )

    # Boundary H: Conflicting historical provenance node (REJECTED_ATOMICALLY)
    nodes_before_conflict = dict(store._nodes)

    class ConflictingNode:
        def __init__(self, nid: str):
            self.node_id = nid
            self.parent_node_ids = ()
            self.payload = {"valid": False, "tampered": True}

        def __eq__(self, other):
            return False

    conflicting_node = ConflictingNode(nA.node_id)
    with pytest.raises(ValueError, match="Attempted to mutate historical provenance node"):
        store.record(conflicting_node)

    assert store._nodes == nodes_before_conflict
    assert store.get_node(nA.node_id) == nA

    # Boundary I: Missing state_payload_hash (REJECTED_ATOMICALLY)
    valid_state = SystemState(symbol="ETH-USD", sequence_number=1, custom_state={"ok": True})
    serialized_valid = serialize_state(valid_state)
    data_no_pld_hash = json.loads(serialized_valid)
    del data_no_pld_hash["state_payload_hash"]
    from gyroscope.state.serialization import compute_snapshot_hash
    data_no_pld_hash["snapshot_hash"] = compute_snapshot_hash(data_no_pld_hash)
    with pytest.raises(StateCorruptedException, match="Missing mandatory 'state_payload_hash'"):
        deserialize_state(json.dumps(data_no_pld_hash))

    # Boundary J: State payload tampering (REJECTED_ATOMICALLY)
    data_pld_tampered = json.loads(serialized_valid)
    data_pld_tampered["state_payload"]["custom_state"]["ok"] = False
    data_pld_tampered["snapshot_hash"] = compute_snapshot_hash(data_pld_tampered)
    with pytest.raises(StateCorruptedException, match="State payload hash mismatch"):
        deserialize_state(json.dumps(data_pld_tampered))

    # Boundary K: Payload hash tampering (REJECTED_ATOMICALLY)
    data_k = json.loads(serialized_valid)
    data_k["state_payload_hash"] = "hash_k_tampered"
    data_k["snapshot_hash"] = compute_snapshot_hash(data_k)
    with pytest.raises(StateCorruptedException, match="State payload hash mismatch"):
        deserialize_state(json.dumps(data_k))

    # Boundary L: State hash tampering (REJECTED_ATOMICALLY)
    data_l = json.loads(serialized_valid)
    data_l["state_hash"] = "state_hash_l_tampered"
    data_l["snapshot_hash"] = compute_snapshot_hash(data_l)
    with pytest.raises(StateCorruptedException, match="State hash integrity failure"):
        deserialize_state(json.dumps(data_l))

    # Boundary M: Snapshot hash tampering (REJECTED_ATOMICALLY)
    data_m = json.loads(serialized_valid)
    data_m["snapshot_hash"] = "snap_m_tampered"
    with pytest.raises(StateCorruptedException, match="Snapshot envelope integrity failure"):
        deserialize_state(json.dumps(data_m))

    # Boundary N: Configuration header tampering (REJECTED_ATOMICALLY)
    data_n = json.loads(serialized_valid)
    data_n["configuration_hash"] = "cfg_tampered_999"
    data_n["snapshot_hash"] = compute_snapshot_hash(data_n)
    with pytest.raises(StateCorruptedException, match="State hash integrity failure"):
        deserialize_state(json.dumps(data_n))


def test_observation_identity_complete_field_binding_and_mutations():
    """Observation identity includes all material observation fields and rejects forged/mismatched IDs."""
    obs1 = Observation.create(
        symbol="BTC-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        arrival_timestamp_ns=1050,
        processing_timestamp_ns=1100,
        price=50000.0,
        bid=49999.0,
        ask=50001.0,
        volume=1.5,
        data_quality=0.99,
        session_state="REGULAR",
        news_state="HIGH_IMPACT",
        decision_timestamp_ns=1120,
        sequence_number=1,
        source="BINANCE",
        source_version="1.1.0",
        metadata={"feed": "primary"},
        parent_observation_id="obs_parent_001",
    )

    assert obs1.observation_id.startswith("obs_")

    # Forged observation_id in constructor is rejected
    with pytest.raises(ValueError, match="Cryptographic observation identity mismatch"):
        Observation(
            observation_id="obs_forged_id_0000000000000000",
            symbol="BTC-USD",
            timeframe="1m",
            event_timestamp_ns=1000,
            arrival_timestamp_ns=1050,
            processing_timestamp_ns=1100,
            price=50000.0,
        )

    # Parameterised mutation sensitivity check: changing any field changes computed ID
    base_params = dict(
        source="BINANCE",
        symbol="BTC-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        arrival_timestamp_ns=1050,
        processing_timestamp_ns=1100,
        sequence_number=1,
        price=50000.0,
        bid=49999.0,
        ask=50001.0,
        volume=1.5,
        data_quality=0.99,
        session_state="REGULAR",
        news_state="HIGH_IMPACT",
        decision_timestamp_ns=1120,
        source_version="1.1.0",
        metadata={"feed": "primary"},
        parent_observation_id="obs_parent_001",
    )

    base_id = compute_deterministic_observation_id(**base_params)

    mutations = [
        ("bid", 49998.0),
        ("ask", 50002.0),
        ("processing_timestamp_ns", 1105),
        ("decision_timestamp_ns", 1125),
        ("data_quality", 0.95),
        ("session_state", "EXTENDED"),
        ("news_state", "NONE"),
        ("metadata", {"feed": "secondary"}),
        ("parent_observation_id", "obs_parent_002"),
        ("sequence_number", 2),
        ("source_version", "1.2.0"),
    ]

    all_identity_fields = [
        "source",
        "symbol",
        "timeframe",
        "event_timestamp_ns",
        "arrival_timestamp_ns",
        "processing_timestamp_ns",
        "sequence_number",
        "price",
        "bid",
        "ask",
        "volume",
        "data_quality",
        "session_state",
        "news_state",
        "decision_timestamp_ns",
        "source_version",
        "metadata",
        "parent_observation_id",
    ]

    all_mutations = [
        ("source", "KRAKEN"),
        ("symbol", "ETH-USD"),
        ("timeframe", "5m"),
        ("event_timestamp_ns", 1001),
        ("arrival_timestamp_ns", 1051),
        ("processing_timestamp_ns", 1105),
        ("sequence_number", 2),
        ("price", 50001.0),
        ("bid", 49998.0),
        ("ask", 50002.0),
        ("volume", 2.0),
        ("data_quality", 0.95),
        ("session_state", "EXTENDED"),
        ("news_state", "NONE"),
        ("decision_timestamp_ns", 1125),
        ("source_version", "1.2.0"),
        ("metadata", {"feed": "secondary"}),
        ("parent_observation_id", "obs_parent_002"),
    ]

    tested_fields = set()
    for field_name, new_val in all_mutations:
        tested_fields.add(field_name)
        mutated_params = base_params.copy()
        mutated_params[field_name] = new_val
        mutated_id = compute_deterministic_observation_id(**mutated_params)
        assert mutated_id != base_id, f"Mutation of field '{field_name}' did not alter observation ID."

    # Verify every identity field was explicitly mutation tested
    assert tested_fields == set(all_identity_fields), f"Missing mutation coverage for identity fields: {set(all_identity_fields) - tested_fields}"
    assert len(tested_fields) == 18, f"Expected exactly 18 tested identity fields, got {len(tested_fields)}"


def test_provenance_cryptographic_content_binding_and_rejections():
    """ProvenanceNode validates provided node_id strictly equals compute_deterministic_provenance_id()."""
    tracker = ProvenanceTracker("sha1", "cfg1", "1.0.0")

    valid_node = tracker.record("OBS", 1000, {"p": 100.0})
    assert valid_node.node_id.startswith("prov_")

    with pytest.raises(ValueError, match="Cryptographic provenance identity mismatch"):
        ProvenanceNode(
            node_id="prov_fake_forged_id",
            parent_node_ids=[],
            timestamp_ns=1000,
            git_commit_sha="sha1",
            config_hash="cfg1",
            model_version="1.0.0",
            artifact_type="OBS",
            payload={"p": 100.0},
        )


def test_provenance_arbitrary_dag_cycle_prevention_at_store_boundary():
    """InMemoryProvenanceStore.record() boundary detects and rejects arbitrary cycles (self, direct A->B->A, and transitive A->B->C->D->A) atomically."""
    store = InMemoryProvenanceStore()
    tracker = ProvenanceTracker("sha1", "cfg1", "1.0.0")

    # Establish valid acyclic DAG: A -> B -> C -> D
    nA = tracker.record("OBS", 1000, {"step": "A"})
    store.record(nA)

    nB = tracker.record("STATE", 1100, {"step": "B"}, parent_node_ids=[nA.node_id])
    store.record(nB)

    nC = tracker.record("STATE", 1200, {"step": "C"}, parent_node_ids=[nB.node_id])
    store.record(nC)

    nD = tracker.record("STATE", 1300, {"step": "D"}, parent_node_ids=[nC.node_id])
    store.record(nD)

    # Test-only adversarial node class compatible with ProvenanceStore required interface
    class TestAdversarialNode:
        def __init__(self, nid: str, parents: tuple):
            self.node_id = nid
            self.parent_node_ids = parents
            self.payload = {"step": "adversarial"}

    # 1. Self-cycle rejection: A -> A
    adv_self = TestAdversarialNode("prov_self_node", ("prov_self_node",))
    nodes_before_self = dict(store._nodes)

    with pytest.raises(ValueError, match="Self-referential provenance parent prohibited"):
        store.record(adv_self)

    assert store._nodes == nodes_before_self

    # 2. Direct cycle rejection: A -> B -> A
    adv_direct_cycle = TestAdversarialNode(nA.node_id, (nB.node_id,))
    nodes_before_direct = dict(store._nodes)

    with pytest.raises(ValueError, match="Arbitrary cycle detected in provenance graph"):
        store.record(adv_direct_cycle)

    assert store._nodes == nodes_before_direct

    # 3. Transitive cycle rejection: A -> B -> C -> D -> A
    adv_transitive_cycle = TestAdversarialNode(nA.node_id, (nD.node_id,))
    nodes_before_transitive = dict(store._nodes)

    with pytest.raises(ValueError, match="Arbitrary cycle detected in provenance graph"):
        store.record(adv_transitive_cycle)

    assert store._nodes == nodes_before_transitive
    assert len(store._nodes) == 4
    assert store.get_node(nA.node_id) == nA


def test_triple_hash_tampering_matrix():
    """Triple-hash contract validation: Cases A through J covering payload, sequence, config, state_hash, and snapshot_hash tampering."""
    state = SystemState(symbol="ETH-USD", sequence_number=1, custom_state={"alpha": 1}, configuration_hash="cfg123")
    serialized = serialize_state(state)
    data = json.loads(serialized)

    from gyroscope.state.serialization import compute_snapshot_hash

    # Case A: Delete state_payload_hash
    data_no_payload_hash = data.copy()
    del data_no_payload_hash["state_payload_hash"]
    data_no_payload_hash["snapshot_hash"] = compute_snapshot_hash(data_no_payload_hash)
    with pytest.raises(StateCorruptedException, match="Missing mandatory 'state_payload_hash'"):
        deserialize_state(json.dumps(data_no_payload_hash))

    # Case B: Modify state_payload without updating state_payload_hash (recomputing outer snapshot_hash)
    data_tampered_payload = json.loads(serialized)
    data_tampered_payload["state_payload"]["custom_state"]["alpha"] = 99
    data_tampered_payload["snapshot_hash"] = compute_snapshot_hash(data_tampered_payload)
    with pytest.raises(StateCorruptedException, match="State payload hash mismatch"):
        deserialize_state(json.dumps(data_tampered_payload))

    # Case C: Modify state_payload and recompute H1 (state_payload_hash), but leave state_hash stale
    data_c = json.loads(serialized)
    data_c["state_payload"]["custom_state"]["alpha"] = 99
    import hashlib
    canonical_payload = json.dumps(data_c["state_payload"], sort_keys=True, separators=(",", ":"))
    data_c["state_payload_hash"] = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    data_c["snapshot_hash"] = compute_snapshot_hash(data_c)
    with pytest.raises(StateCorruptedException, match="State hash integrity failure"):
        deserialize_state(json.dumps(data_c))

    # Case D: Modify sequence_number without recomputing hashes
    data_d = json.loads(serialized)
    data_d["sequence_number"] = 99
    data_d["snapshot_hash"] = compute_snapshot_hash(data_d)
    with pytest.raises(StateCorruptedException, match="State hash integrity failure"):
        deserialize_state(json.dumps(data_d))

    # Case E: Modify last_event_id without recomputing hashes
    data_e = json.loads(serialized)
    data_e["last_event_id"] = "evt_hacked"
    data_e["snapshot_hash"] = compute_snapshot_hash(data_e)
    with pytest.raises(StateCorruptedException, match="State hash integrity failure"):
        deserialize_state(json.dumps(data_e))

    # Case F: Modify configuration_hash without recomputing hashes
    data_f = json.loads(serialized)
    data_f["configuration_hash"] = "cfg_tampered"
    data_f["snapshot_hash"] = compute_snapshot_hash(data_f)
    with pytest.raises(StateCorruptedException, match="State hash integrity failure"):
        deserialize_state(json.dumps(data_f))

    # Case G: Modify only snapshot_hash
    data_g = json.loads(serialized)
    data_g["snapshot_hash"] = "snap_tampered_000000000000000000000000"
    with pytest.raises(StateCorruptedException, match="Snapshot envelope integrity failure"):
        deserialize_state(json.dumps(data_g))

    # Case H: Delete snapshot_hash
    data_h = json.loads(serialized)
    del data_h["snapshot_hash"]
    with pytest.raises(StateCorruptedException, match="Missing mandatory 'snapshot_hash'"):
        deserialize_state(json.dumps(data_h))

    # Case I: Modify state_hash only
    data_i = json.loads(serialized)
    data_i["state_hash"] = "state_tampered_0000000000000000000000"
    data_i["snapshot_hash"] = compute_snapshot_hash(data_i)
    with pytest.raises(StateCorruptedException, match="State hash integrity failure"):
        deserialize_state(json.dumps(data_i))

    # Case J: Fully recomputed internally consistent envelope for valid state deserializes cleanly
    state_valid = SystemState(symbol="ETH-USD", sequence_number=1, custom_state={"alpha": 1}, configuration_hash="cfg123")
    serialized_valid = serialize_state(state_valid)
    restored = deserialize_state(serialized_valid)
    assert restored.compute_state_hash() == state_valid.compute_state_hash()


def test_replay_authority_and_degraded_gap_semantics():
    """Verify ReplayResult.is_authoritative mapping across all ReplayStatus outcomes."""
    # COMPLETE -> is_authoritative = True
    ev_complete = [
        Event.create(event_type="TICK", event_timestamp_ns=1000, sequence_number=1),
        Event.create(event_type="TICK", event_timestamp_ns=1100, sequence_number=2),
    ]
    eng1 = DeterministicReplayEngine()
    res1 = eng1.replay_stream_with_status(ev_complete)
    assert res1.status == ReplayStatus.COMPLETE
    assert res1.is_authoritative is True

    # COMPLETE_WITH_DUPLICATES -> is_authoritative = True
    ev_dups = [
        Event.create(event_type="TICK", event_timestamp_ns=1000, sequence_number=1, event_id="evt_same"),
        Event.create(event_type="TICK", event_timestamp_ns=1000, sequence_number=1, event_id="evt_same"),
    ]
    eng2 = DeterministicReplayEngine()
    res2 = eng2.replay_stream_with_status(ev_dups)
    assert res2.status == ReplayStatus.COMPLETE_WITH_DUPLICATES
    assert res2.is_authoritative is True

    # GAP_DETECTED -> is_authoritative = False
    events_with_gap = [
        Event.create(event_type="TICK", event_timestamp_ns=1000, sequence_number=1),
        Event.create(event_type="TICK", event_timestamp_ns=1200, sequence_number=3),  # Gap: missing sequence 2
    ]
    eng3 = DeterministicReplayEngine()
    res3 = eng3.replay_stream_with_status(events_with_gap)
    assert res3.status == ReplayStatus.GAP_DETECTED
    assert res3.is_authoritative is False

    # Explicitly test ReplayResult.is_authoritative property across ReplayStatus values
    r_complete = ReplayResult(status=ReplayStatus.COMPLETE, final_state=SystemState(), processed_count=1, duplicate_count=0, gap_events=())
    assert r_complete.is_authoritative is True

    r_dups = ReplayResult(status=ReplayStatus.COMPLETE_WITH_DUPLICATES, final_state=SystemState(), processed_count=1, duplicate_count=1, gap_events=())
    assert r_dups.is_authoritative is True

    r_gap = ReplayResult(status=ReplayStatus.GAP_DETECTED, final_state=SystemState(), processed_count=1, duplicate_count=0, gap_events=())
    assert r_gap.is_authoritative is False

    r_ts_reg = ReplayResult(status=ReplayStatus.TIMESTAMP_REGRESSION_DETECTED, final_state=SystemState(), processed_count=1, duplicate_count=0, gap_events=())
    assert r_ts_reg.is_authoritative is False

    r_failed = ReplayResult(status=ReplayStatus.FAILED, final_state=SystemState(), processed_count=0, duplicate_count=0, gap_events=())
    assert r_failed.is_authoritative is False

    # fail_on_gap halts processing on sequence jump
    eng5 = DeterministicReplayEngine(fail_on_gap=True)
    with pytest.raises(DeterminismViolationError, match="Replay halted due to sequence gap"):
        eng5.replay_stream_with_status(events_with_gap)


def test_multi_boundary_snapshot_replay_equivalence():
    """Verify snapshot resume equivalence across k=0, 1, 2, 5, 9, 10."""
    events = [
        Event.create(event_type="TICK", event_timestamp_ns=1000 + i * 100, sequence_number=i + 1, payload={"val": i})
        for i in range(10)
    ]

    engine_full = DeterministicReplayEngine()
    state_full = engine_full.replay_stream(events)
    full_state_hash = state_full.compute_state_hash()

    for k in [0, 1, 2, 5, 9, 10]:
        engine_p = DeterministicReplayEngine()
        if k > 0:
            engine_p.replay_stream(events[:k])

        store = SnapshotStore()
        snap = store.save_snapshot(engine_p.state)

        resumed_state = store.load_state(snap.snapshot_id)
        engine_r = DeterministicReplayEngine(initial_state=resumed_state)
        if k < len(events):
            engine_r.replay_stream(events[k:])

        assert engine_r.state.compute_state_hash() == full_state_hash, f"Equivalence failed at split k={k}"


def test_process_boundary_determinism_reconstruction():
    """Verify deterministic state hash match across process execution boundaries."""
    cmd = [
        sys.executable,
        "-c",
        (
            "from gyroscope.state import Event, SystemState; "
            "e = Event.create('TICK', 1000, {'v': 42}, sequence_number=1); "
            "s = SystemState(); "
            "s.process_event(e); "
            "print(s.compute_state_hash())"
        ),
    ]

    res1 = subprocess.check_output(cmd, text=True).strip()
    res2 = subprocess.check_output(cmd, text=True).strip()

    assert len(res1) == 64
    assert res1 == res2
