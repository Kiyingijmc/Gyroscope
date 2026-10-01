"""Provenance bridge mapping strategy and execution lineage fields into Gyroscope's single authoritative ProvenanceTracker/Store."""

from typing import Any, Dict, List, Optional, Sequence, Tuple

from gyroscope.contracts.ports import ProvenancePort
from gyroscope.contracts.types import AuthorityDomain
from gyroscope.provenance.tracker import ProvenanceNode, ProvenanceTracker


AUTHORITY_PRECEDENCE = {
    AuthorityDomain.OBSERVATION: 0,
    AuthorityDomain.STATE: 1,
    AuthorityDomain.RESEARCH_ESTIMATION: 2,
    AuthorityDomain.EVIDENCE: 3,
    AuthorityDomain.STRATEGY_DECISION: 4,
    AuthorityDomain.RISK_AUTHORITY: 5,
    AuthorityDomain.EXECUTION_INTENT: 6,
    AuthorityDomain.BROKER_BOUNDARY: 7,
    AuthorityDomain.RECONCILIATION: 8,
    AuthorityDomain.DURABLE_STATE: 9,
}


class ProvenanceBridge(ProvenancePort):
    """Bridge adapter mapping domain events and decisions into Gyroscope's single authoritative provenance DAG with strict causal ancestry and precedence validation."""

    def __init__(self, tracker: ProvenanceTracker) -> None:
        self._tracker = tracker

    @property
    def tracker(self) -> ProvenanceTracker:
        return self._tracker

    def record_node(
        self,
        authority: AuthorityDomain,
        payload: Dict[str, Any],
        parent_node_ids: Tuple[str, ...],
        timestamp_ns: int = 1000,
    ) -> str:
        """Record a domain event node into the single authoritative provenance graph, enforcing monotonic authority ordering and parent existence."""
        child_level = AUTHORITY_PRECEDENCE[authority]

        if authority != AuthorityDomain.OBSERVATION and not parent_node_ids:
            raise ValueError(f"Non-observation authority domain {authority.value} must carry parent node references")

        for parent_id in parent_node_ids:
            parent_node = self._tracker.get_node(parent_id)
            if not parent_node:
                raise ValueError(f"Missing required parent provenance node in DAG: '{parent_id}'")

            try:
                parent_auth = AuthorityDomain(parent_node.artifact_type)
                parent_level = AUTHORITY_PRECEDENCE[parent_auth]
            except ValueError:
                parent_auth = None

            if parent_auth is not None and parent_level > child_level:
                raise ValueError(
                    f"Backward authority transition rejected: parent {parent_auth.value} (level {parent_level}) "
                    f"cannot precede child {authority.value} (level {child_level})"
                )

        node = self._tracker.record(
            artifact_type=authority.value,
            timestamp_ns=timestamp_ns,
            payload=payload,
            parent_node_ids=parent_node_ids,
        )
        return node.node_id

    def get_ancestry(self, node_id: str) -> Sequence[ProvenanceNode]:
        """Retrieve full causal lineage tree for any decision artifact."""
        return self._tracker.trace_ancestry(node_id)

    def verify_causal_ancestry(
        self,
        node_id: str,
        required_authorities: Sequence[AuthorityDomain],
    ) -> bool:
        """Verify that a node's causal ancestry contains nodes from all required authority domains in monotonic causal order."""
        ancestry = self.get_ancestry(node_id)
        found_authorities = {node.artifact_type for node in ancestry}
        if not all(req.value in found_authorities for req in required_authorities):
            return False

        # Verify ordering along every parent-child edge in ancestry
        for node in ancestry:
            try:
                node_auth = AuthorityDomain(node.artifact_type)
                node_level = AUTHORITY_PRECEDENCE[node_auth]
                for p_id in node.parent_node_ids:
                    p_node = self._tracker.get_node(p_id)
                    if p_node:
                        p_auth = AuthorityDomain(p_node.artifact_type)
                        p_level = AUTHORITY_PRECEDENCE[p_auth]
                        if p_level > node_level:
                            return False
            except ValueError:
                pass

        return True
