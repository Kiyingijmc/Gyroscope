"""Comprehensive Phase 1 Deterministic Kernel Test Suite validating identity, hashing, ordering, replay, snapshot equivalence, numeric boundaries, and provenance."""

from decimal import Decimal
import pytest

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

    # Invariant I1: Same canonical observation -> same identity
    assert obs1.observation_id == obs2.observation_id
    assert obs1.observation_id.startswith("obs_")

    # Different payload -> different identity
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

    # Explicit observation_id overrides derived identity
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


def test_deterministic_provenance_identity():
    """Verify that provenance node identity is derived deterministically from canonical attributes."""
    tracker = ProvenanceTracker(
        git_commit_sha="abc1234",
        config_hash="0000111122223333444455556666777788889999aaaabbbbccccddddeeeeffff",
        model_version="1.0.0",
    )

    node1 = tracker.record(
        artifact_type="STATE_ESTIMATE",
        timestamp_ns=1000,
        payload={"state": [1.0, 2.0]},
        parent_node_ids=["prov_p1", "prov_p2"],
    )

    tracker2 = ProvenanceTracker(
        git_commit_sha="abc1234",
        config_hash="0000111122223333444455556666777788889999aaaabbbbccccddddeeeeffff",
        model_version="1.0.0",
    )

    node2 = tracker2.record(
        artifact_type="STATE_ESTIMATE",
        timestamp_ns=1000,
        payload={"state": [1.0, 2.0]},
        parent_node_ids=["prov_p2", "prov_p1"],  # Order of parents normalized
    )

    # Invariant I3: Same canonical provenance -> same identity
    assert node1.node_id == node2.node_id
    assert node1.payload_hash == node2.payload_hash


def test_canonical_hashing_contracts():
    """Verify distinction between state_payload_hash, state_hash, and snapshot_hash."""
    state = SystemState(symbol="ETH-USD", sequence_number=5, last_event_id="evt_5", last_event_timestamp_ns=5000)
    state.custom_state["var"] = 42

    payload_hash = state.compute_state_payload_hash()
    state_hash = state.compute_state_hash()

    assert payload_hash != state_hash

    serialized = serialize_state(state)
    deserialized = deserialize_state(serialized)

    assert deserialized.compute_state_payload_hash() == payload_hash
    assert deserialized.compute_state_hash() == state_hash


def test_numeric_determinism_boundary():
    """Verify exact Decimal semantics for authoritative risk quantities and float assertions."""
    # Authoritative financial quantity conversion
    d1 = to_authoritative_decimal("100.123456789")
    assert d1 == Decimal("100.12345679")  # Quantized to 8 decimal places
    assert isinstance(d1, Decimal)

    # Exact Decimal check passes for Decimal, fails for float
    assert assert_exact_financial_quantity(Decimal("10.5")) == Decimal("10.5")
    with pytest.raises(TypeError):
        assert_exact_financial_quantity(10.5)


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

    # Invariant I2: Same canonical event -> same identity
    assert e1.event_id == e2.event_id

    state = SystemState()
    assert state.process_event(e1) is True
    post_hash = state.compute_state_hash()

    # Invariant I6: Duplicate event processing is idempotent
    assert state.process_event(e2) is False
    assert state.compute_state_hash() == post_hash


def test_causal_ordering_and_gap_detection():
    """Verify deterministic reordering and sequence gap detection."""
    e1 = Event.create(event_type="TICK", event_timestamp_ns=1000, sequence_number=1, source="A", payload={"v": 1})
    e2 = Event.create(event_type="TICK", event_timestamp_ns=2000, sequence_number=2, source="A", payload={"v": 2})
    e3 = Event.create(event_type="TICK", event_timestamp_ns=3000, sequence_number=4, source="A", payload={"v": 4})  # Gap at 3

    buf = CausalOrderingBuffer()
    buf.push_many([e3, e1, e2])  # Submitted out of order
    ordered = buf.flush_ordered()

    assert [e.sequence_number for e in ordered] == [1, 2, 4]

    detector = GapDetector(initial_sequence=0, initial_timestamp_ns=0)
    assert detector.inspect(ordered[0]) == GapStatus.CONTINUOUS
    assert detector.inspect(ordered[1]) == GapStatus.CONTINUOUS
    assert detector.inspect(ordered[2]) == GapStatus.DATA_GAP

    # Invariant I9: Sequence gaps are explicitly recorded
    assert len(detector.detected_gaps) == 1
    assert detector.detected_gaps[0].expected_sequence == 3
    assert detector.detected_gaps[0].received_sequence == 4


def test_full_replay_vs_snapshot_resume_equivalence():
    """Major Invariant Test I8: Full Replay(E1...En) == Snapshot(Ek) + Replay(Ek+1...En)."""
    events = [
        Event.create(event_type="TICK", event_timestamp_ns=1000 + i * 100, sequence_number=i + 1, payload={"val": i})
        for i in range(10)
    ]

    # Path 1: Full Replay from scratch
    engine_full = DeterministicReplayEngine()
    state_full = engine_full.replay_stream(events)
    full_state_hash = state_full.compute_state_hash()

    # Path 2: Partial replay to k=5, snapshot, resume with Ek+1...En
    k = 5
    engine_partial = DeterministicReplayEngine()
    engine_partial.replay_stream(events[:k])

    store = SnapshotStore()
    snap = store.save_snapshot(engine_partial.state)

    # Resume from snapshot
    resumed_state = store.load_state(snap.snapshot_id)
    engine_resume = DeterministicReplayEngine(initial_state=resumed_state)
    state_resumed = engine_resume.replay_stream(events[k:])
    resumed_state_hash = state_resumed.compute_state_hash()

    # Invariant I8 verification
    assert full_state_hash == resumed_state_hash
    assert state_full.custom_state == state_resumed.custom_state
    assert state_full.sequence_number == state_resumed.sequence_number == 10


def test_provenance_store_ancestry_and_immutability():
    """Verify in-memory provenance store ancestry tracing and immutability protection."""
    store = InMemoryProvenanceStore()
    tracker = ProvenanceTracker("sha1", "cfg1", "1.0.0")

    n1 = tracker.record("OBS", 1000, {"p": 1})
    n2 = tracker.record("STATE", 1100, {"s": 2}, parent_node_ids=[n1.node_id])

    store.record(n1)
    store.record(n2)

    ancestry = store.trace_ancestry(n2.node_id)
    assert len(ancestry) == 2
    assert ancestry[0].node_id == n2.node_id
    assert ancestry[1].node_id == n1.node_id

    # Duplicate re-record with identical content is idempotent
    store.record(n1)

    # Conflicting node ID mutation raises ValueError
    conflicting_node = ProvenanceNode(
        node_id=n1.node_id,
        parent_node_ids=[],
        timestamp_ns=1000,
        git_commit_sha="sha1",
        config_hash="cfg1",
        model_version="1.0.0",
        artifact_type="OBS",
        payload={"p": 999},  # Conflicting payload
    )
    with pytest.raises(ValueError, match="Attempted to mutate historical provenance node"):
        store.record(conflicting_node)
