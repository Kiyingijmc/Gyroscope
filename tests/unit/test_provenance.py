"""Unit tests for ProvenanceTracker and lineage graph traversal."""

from gyroscope.provenance.tracker import ProvenanceTracker


def test_provenance_recording_and_ancestry_tracing():
    tracker = ProvenanceTracker(
        git_commit_sha="3a9254445849d26544ae6aa5c03a5e767fd3586b",
        config_hash="abc123hash",
        model_version="1.0.0",
    )

    n1 = tracker.record(
        artifact_type="OBSERVATION",
        timestamp_ns=1000,
        payload={"price": 100.0},
    )

    n2 = tracker.record(
        artifact_type="FEATURE",
        timestamp_ns=1005,
        payload={"sma": 99.5},
        parent_node_ids=[n1.node_id],
    )

    n3 = tracker.record(
        artifact_type="RISK_DECISION",
        timestamp_ns=1010,
        payload={"approved": True},
        parent_node_ids=[n2.node_id],
    )

    ancestry = tracker.trace_ancestry(n3.node_id)
    node_ids = [node.node_id for node in ancestry]

    assert node_ids == [n3.node_id, n2.node_id, n1.node_id]
    assert tracker.get_node(n2.node_id).parent_node_ids == (n1.node_id,)


def test_provenance_payload_deep_immutability_and_aliasing():
    """Verify caller-owned mutable payloads with dicts, lists, nested dicts, and nested lists cannot mutate stored provenance nodes, hashes, or ancestry after creation."""
    tracker = ProvenanceTracker("sha1", "cfg1", "1.0.0")

    payload = {
        "dict": {"a": 1},
        "list": [10, 20],
        "nested_dict": {"level1": {"level2": "original"}},
        "nested_list": [[1, 2], [{"deep": "data"}]],
    }
    initial_payload_hash = tracker.record("OBS", 1000, payload).payload_hash
    node = tracker.record("OBS", 1000, payload)
    initial_node_id = node.node_id

    # Mutate caller-owned payload structures at all levels
    payload["dict"]["a"] = 999
    payload["list"].append(30)
    payload["nested_dict"]["level1"]["level2"] = "tampered"
    payload["nested_list"][0].append(3)
    payload["nested_list"][1][0]["deep"] = "hacked"

    # Stored node payload, payload_hash, and node_id must remain strictly unchanged
    assert node.node_id == initial_node_id
    assert node.payload_hash == initial_payload_hash
    assert node.payload["dict"]["a"] == 1
    assert tuple(node.payload["list"]) == (10, 20)
    assert node.payload["nested_dict"]["level1"]["level2"] == "original"
    assert node.payload["nested_list"][0] == (1, 2)
    assert node.payload["nested_list"][1][0]["deep"] == "data"
