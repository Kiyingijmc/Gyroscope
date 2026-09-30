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
