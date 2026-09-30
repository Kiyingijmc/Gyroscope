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
        node_id="p1",
    )

    n2 = tracker.record(
        artifact_type="FEATURE",
        timestamp_ns=1005,
        payload={"sma": 99.5},
        parent_node_ids=["p1"],
        node_id="p2",
    )

    n3 = tracker.record(
        artifact_type="RISK_DECISION",
        timestamp_ns=1010,
        payload={"approved": True},
        parent_node_ids=["p2"],
        node_id="p3",
    )

    ancestry = tracker.trace_ancestry("p3")
    node_ids = [node.node_id for node in ancestry]

    assert node_ids == ["p3", "p2", "p1"]
    assert tracker.get_node("p2").parent_node_ids == ["p1"]
