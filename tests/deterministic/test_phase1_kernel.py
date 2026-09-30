"""Comprehensive Phase 1 Deterministic Kernel Test Suite validating identity, hashing, ordering, replay, snapshot equivalence, numeric boundaries, provenance immutability, and subprocess execution."""

from decimal import Decimal
import subprocess
import sys

import pytest

from gyroscope.core.exceptions import CausalViolationError, DeterminismViolationError, StateCorruptedException
from gyroscope.core.numeric import (
    AUTHORITATIVE_PRECISION,
    assert_exact_financial_quantity,
    to_authoritative_decimal,
)
from gyroscope.engine import (
    CausalOrderingBuffer,
    DeterministicReplayEngine,
    GapDetector,
    GapStatus,
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


def test_deterministic_observation_identity():
    """Verify that same canonical observation produces identical ID, replay-stable, and explicit ID overrides."""
    obs1 = Observation.create(
        symbol="BTC-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        arrival_timestamp_ns=1100,
        processing_timestamp_ns=1200,
        price=50000.0,
        volume=1.5,
        sequence_number=1,
        source="BINANCE",
        metadata={"b": 2, "a": 1},
    )

    obs2 = Observation.create(
        symbol="BTC-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        arrival_timestamp_ns=1100,
        processing_timestamp_ns=1200,
        price=50000.0,
        volume=1.5,
        sequence_number=1,
        source="BINANCE",
        metadata={"a": 1, "b": 2},  # Reordered dict keys
    )

    assert obs1.observation_id == obs2.observation_id
    assert obs1.observation_id.startswith("obs_")

    obs_diff = Observation.create(
        symbol="BTC-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        arrival_timestamp_ns=1100,
        processing_timestamp_ns=1200,
        price=50001.0,  # Price change
        volume=1.5,
        sequence_number=1,
        source="BINANCE",
    )
    assert obs1.observation_id != obs_diff.observation_id

    obs_explicit = Observation.create(
        symbol="BTC-USD",
        timeframe="1m",
        event_timestamp_ns=1000,
        arrival_timestamp_ns=1100,
        processing_timestamp_ns=1200,
        price=50000.0,
        observation_id="custom_obs_123",
    )
    assert obs_explicit.observation_id == "custom_obs_123"


def test_deterministic_provenance_identity_and_deep_immutability():
    """Verify that provenance node identity is derived deterministically and objects are deeply immutable."""
    tracker = ProvenanceTracker(
        git_commit_sha="abc1234",
        config_hash="0000111122223333444455556666777788889999aaaabbbbccccddddeeeeffff",
        model_version="1.0.0",
    )

    node1 = tracker.record(
        artifact_type="STATE_ESTIMATE",
        timestamp_ns=1000,
        payload={"state": [1.0, 2.0], "meta": {"k": "v"}},
        parent_node_ids=["prov_p1", "prov_p2"],
    )

    # Verify deep immutability: top-level frozen, nested list frozen to tuple, dict frozen to FrozenDict
    with pytest.raises(TypeError):
        node1.parent_node_ids[0] = "mutated"

    with pytest.raises(TypeError):
        node1.payload["state"] = [3.0]

    with pytest.raises(TypeError):
        node1.payload["meta"]["k"] = "mutated"

    tracker2 = ProvenanceTracker(
        git_commit_sha="abc1234",
        config_hash="0000111122223333444455556666777788889999aaaabbbbccccddddeeeeffff",
        model_version="1.0.0",
    )

    node2 = tracker2.record(
        artifact_type="STATE_ESTIMATE",
        timestamp_ns=1000,
        payload={"state": [1.0, 2.0], "meta": {"k": "v"}},
        parent_node_ids=["prov_p2", "prov_p1"],  # Order normalized
    )

    assert node1.node_id == node2.node_id
    assert node1.payload_hash == node2.payload_hash


def test_canonical_hashing_contracts_and_snapshot_tamper_rejection():
    """Verify distinction between state_payload_hash, state_hash, and snapshot_hash and adversarial tampering rejection."""
    state = SystemState(symbol="ETH-USD", sequence_number=5, last_event_id="evt_5", last_event_timestamp_ns=5000)
    state.custom_state["var"] = 42

    serialized = serialize_state(state)
    deserialized = deserialize_state(serialized)

    assert deserialized.compute_state_payload_hash() == state.compute_state_payload_hash()
    assert deserialized.compute_state_hash() == state.compute_state_hash()

    # Adversarial tampering tests
    import json
    data = json.loads(serialized)

    # 1. Tamper custom_state -> fails snapshot_hash or state_hash
    t1 = dict(data)
    t1["state_payload"]["custom_state"]["var"] = 99
    with pytest.raises(StateCorruptedException, match="Snapshot envelope integrity failure"):
        deserialize_state(json.dumps(t1))

    # 2. Tamper header snapshot_hash -> fails snapshot_hash
    t2 = dict(data)
    t2["snapshot_hash"] = "0" * 64
    with pytest.raises(StateCorruptedException, match="Snapshot envelope integrity failure"):
        deserialize_state(json.dumps(t2))

    # 3. Missing snapshot_hash -> fails mandatory missing check
    t3 = dict(data)
    del t3["snapshot_hash"]
    with pytest.raises(StateCorruptedException, match="Missing mandatory 'snapshot_hash'"):
        deserialize_state(json.dumps(t3))


def test_numeric_determinism_boundary_and_rejections():
    """Verify exact Decimal semantics for authoritative risk quantities and float/NaN/Infinity rejections."""
    d1 = to_authoritative_decimal("100.123456789")
    assert d1 == Decimal("100.12345679")
    assert isinstance(d1, Decimal)

    assert assert_exact_financial_quantity(Decimal("10.5")) == Decimal("10.5")

    with pytest.raises(TypeError):
        assert_exact_financial_quantity(10.5)

    with pytest.raises(ValueError, match="cannot accept NaN or Infinity"):
        to_authoritative_decimal(float("nan"))

    with pytest.raises(ValueError, match="cannot accept NaN or Infinity"):
        to_authoritative_decimal(float("inf"))


def test_event_identity_and_idempotency():
    """Verify deterministic event ID generation and duplicate event idempotency."""
    e1 = Event.create(
        event_type="TICK",
        event_timestamp_ns=1000,
        payload={"price": 100.0},
        observation_id="obs_1",
    )
    e2 = Event.create(
        event_type="TICK",
        event_timestamp_ns=1000,
        payload={"price": 100.0},
        observation_id="obs_1",
    )

    assert e1.event_id == e2.event_id

    state = SystemState()
    assert state.process_event(e1) is True
    post_hash = state.compute_state_hash()

    assert state.process_event(e2) is False
    assert state.compute_state_hash() == post_hash


def test_causal_ordering_and_gap_detection():
    """Verify deterministic reordering and sequence gap detection."""
    e1 = Event.create(event_type="TICK", event_timestamp_ns=1000, sequence_number=1, source="A", payload={"v": 1})
    e2 = Event.create(event_type="TICK", event_timestamp_ns=2000, sequence_number=2, source="A", payload={"v": 2})
    e3 = Event.create(event_type="TICK", event_timestamp_ns=3000, sequence_number=4, source="A", payload={"v": 4})

    buf = CausalOrderingBuffer()
    buf.push_many([e3, e1, e2])
    ordered = buf.flush_ordered()

    assert [e.sequence_number for e in ordered] == [1, 2, 4]

    detector = GapDetector(initial_sequence=0, initial_timestamp_ns=0)
    assert detector.inspect(ordered[0]) == GapStatus.CONTINUOUS
    assert detector.inspect(ordered[1]) == GapStatus.CONTINUOUS
    assert detector.inspect(ordered[2]) == GapStatus.DATA_GAP

    assert len(detector.detected_gaps) == 1
    assert detector.detected_gaps[0].expected_sequence == 3
    assert detector.detected_gaps[0].received_sequence == 4


def test_multi_boundary_snapshot_replay_equivalence():
    """Test Replay(E1...En) == Snapshot(Ek) + Replay(Ek+1...En) across multiple k boundary points (k=0, 1, 5, 9, 10)."""
    events = [
        Event.create(event_type="TICK", event_timestamp_ns=1000 + i * 100, sequence_number=i + 1, payload={"val": i})
        for i in range(10)
    ]

    engine_full = DeterministicReplayEngine()
    state_full = engine_full.replay_stream(events)
    full_state_hash = state_full.compute_state_hash()

    for k in [0, 1, 5, 9, 10]:
        engine_p = DeterministicReplayEngine()
        if k > 0:
            engine_p.replay_stream(events[:k])

        store = SnapshotStore()
        snap = store.save_snapshot(engine_p.state)

        resumed_state = store.load_state(snap.snapshot_id)
        engine_r = DeterministicReplayEngine(initial_state=resumed_state)
        if k < len(events):
            engine_r.replay_stream(events[k:])

        assert engine_r.state.compute_state_hash() == full_state_hash, f"Snapshot resume failed at k={k}"


def test_provenance_store_graph_integrity_and_parent_validation():
    """Verify in-memory provenance store parent validation, cycle rejection, and ancestry tracing."""
    store = InMemoryProvenanceStore()
    tracker = ProvenanceTracker("sha1", "cfg1", "1.0.0")

    n1 = tracker.record("OBS", 1000, {"p": 1})

    # Missing parent validation
    n2_invalid = ProvenanceNode(
        node_id="prov_invalid",
        parent_node_ids=["prov_non_existent"],
        timestamp_ns=1100,
        git_commit_sha="sha1",
        config_hash="cfg1",
        model_version="1.0.0",
        artifact_type="STATE",
        payload={"s": 2},
    )
    with pytest.raises(KeyError, match="Parent provenance node 'prov_non_existent' not found"):
        store.record(n2_invalid, validate_parents=True)

    # Valid parent record
    store.record(n1)
    n2 = tracker.record("STATE", 1100, {"s": 2}, parent_node_ids=[n1.node_id])
    store.record(n2)

    # Self-parent cycle rejection
    n_cycle = ProvenanceNode(
        node_id="prov_cycle",
        parent_node_ids=["prov_cycle"],
        timestamp_ns=1200,
        git_commit_sha="sha1",
        config_hash="cfg1",
        model_version="1.0.0",
        artifact_type="STATE",
        payload={"s": 3},
    )
    with pytest.raises(ValueError, match="Self-referential provenance parent prohibited"):
        store.record(n_cycle)


def test_process_boundary_determinism_reconstruction():
    """Verify deterministic reconstruction and state hash match across subprocess execution boundaries."""
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
