"""Unit tests for strict ordered causal provenance authority precedence and invalid DAG rejection."""

import pytest

from gyroscope.adapters.provenance import ProvenanceBridge
from gyroscope.contracts.types import AuthorityDomain
from gyroscope.provenance.tracker import ProvenanceTracker


def test_provenance_rejects_backward_authority_transition():
    """Verify ProvenanceBridge rejects backward authority transitions (e.g. EXECUTION_INTENT -> OBSERVATION)."""
    tracker = ProvenanceTracker(git_commit_sha="sha", config_hash="cfg", model_version="1.0.0")
    bridge = ProvenanceBridge(tracker)

    obs_id = bridge.record_node(AuthorityDomain.OBSERVATION, {"price": "50000.00"}, (), timestamp_ns=1000)
    strat_id = bridge.record_node(AuthorityDomain.STRATEGY_DECISION, {"action": "BUY"}, (obs_id,), timestamp_ns=1100)
    intent_id = bridge.record_node(AuthorityDomain.EXECUTION_INTENT, {"qty": "1.0"}, (strat_id,), timestamp_ns=1200)

    # Attempt illegal backward transition: creating an OBSERVATION node with EXECUTION_INTENT as parent
    with pytest.raises(ValueError, match="Backward authority transition rejected"):
        bridge.record_node(AuthorityDomain.OBSERVATION, {"price": "50010.00"}, (intent_id,), timestamp_ns=1300)


def test_provenance_accepts_valid_monotonic_authority_order():
    """Verify a complete monotonic authority pipeline from OBSERVATION -> RECONCILIATION is accepted."""
    tracker = ProvenanceTracker(git_commit_sha="sha", config_hash="cfg", model_version="1.0.0")
    bridge = ProvenanceBridge(tracker)

    obs = bridge.record_node(AuthorityDomain.OBSERVATION, {"data": 1}, (), 1000)
    state = bridge.record_node(AuthorityDomain.STATE, {"seq": 1}, (obs,), 1005)
    ev = bridge.record_node(AuthorityDomain.EVIDENCE, {"nis": 1.0}, (state,), 1010)
    strat = bridge.record_node(AuthorityDomain.STRATEGY_DECISION, {"buy": 1}, (ev,), 1015)
    risk = bridge.record_node(AuthorityDomain.RISK_AUTHORITY, {"app": True}, (strat,), 1020)
    intent = bridge.record_node(AuthorityDomain.EXECUTION_INTENT, {"intent": 1}, (risk,), 1025)
    broker = bridge.record_node(AuthorityDomain.BROKER_BOUNDARY, {"ord": 1}, (intent,), 1030)
    rec = bridge.record_node(AuthorityDomain.RECONCILIATION, {"rec": 1}, (broker,), 1035)

    assert bridge.verify_causal_ancestry(
        rec,
        [
            AuthorityDomain.OBSERVATION,
            AuthorityDomain.STRATEGY_DECISION,
            AuthorityDomain.RISK_AUTHORITY,
            AuthorityDomain.EXECUTION_INTENT,
            AuthorityDomain.BROKER_BOUNDARY,
            AuthorityDomain.RECONCILIATION,
        ],
    ) is True
