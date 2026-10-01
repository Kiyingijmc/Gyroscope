"""Unit tests for State Adapter and Provenance Bridge."""

from gyroscope.adapters.provenance import ProvenanceBridge
from gyroscope.adapters.state import ReadOnlyStateAdapter
from gyroscope.contracts.types import AuthorityDomain
from gyroscope.provenance.tracker import ProvenanceTracker
from gyroscope.state import Event, SystemState


def test_read_only_state_adapter_isolation():
    """Verify state adapter projects system state without modifying underlying state authority."""
    state = SystemState(symbol="BTC-USD")
    adapter = ReadOnlyStateAdapter(state)

    assert adapter.symbol == "BTC-USD"
    assert adapter.get_latest_sequence_number() == 0

    # Event processing occurs via SystemState
    evt = Event(event_id="e1", event_type="TICK", event_timestamp_ns=1000, payload={"price": 50000.0})
    state.process_event(evt)

    assert adapter.get_latest_sequence_number() == 1
    assert adapter.get_state_payload_hash() == state.compute_state_payload_hash()


def test_provenance_bridge_ancestry_chain():
    """Verify that strategy proposals and decisions maintain a valid single ancestry chain."""
    tracker = ProvenanceTracker(
        git_commit_sha="235ae06857cdfd84168f996fb6792aafd8e0c630",
        config_hash="cfg_hash_1",
        model_version="1.0.0",
    )
    bridge = ProvenanceBridge(tracker)

    # 1. Observation node
    obs_node_id = bridge.record_node(
        authority=AuthorityDomain.OBSERVATION,
        payload={"symbol": "BTC-USD", "price": "50000.00"},
        parent_node_ids=(),
        timestamp_ns=1000,
    )

    # 2. Strategy decision node
    strat_node_id = bridge.record_node(
        authority=AuthorityDomain.STRATEGY_DECISION,
        payload={"action": "BUY", "quantity": "1.0"},
        parent_node_ids=(obs_node_id,),
        timestamp_ns=1100,
    )

    # 3. Risk node
    risk_node_id = bridge.record_node(
        authority=AuthorityDomain.RISK_AUTHORITY,
        payload={"approved": True, "risk_score": 0.1},
        parent_node_ids=(strat_node_id,),
        timestamp_ns=1200,
    )

    ancestry = bridge.get_ancestry(risk_node_id)
    ancestry_ids = [n.node_id for n in ancestry]

    assert risk_node_id in ancestry_ids
    assert strat_node_id in ancestry_ids
    assert obs_node_id in ancestry_ids
