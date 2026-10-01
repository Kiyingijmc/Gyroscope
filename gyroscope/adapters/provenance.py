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
    """Bridge adapter mapping domain events and decisions into Gyroscope's single authoritative provenance DAG with strict causal ancestry validation."""

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
        """Record a domain event node into the single authoritative provenance graph and enforce causal parent link existence."""
        # Enforce that non-OBSERVATION nodes MUST carry parent node references
        if authority != AuthorityDomain.OBSERVATION and not parent_node_ids:
            raise ValueError(f"Non-observation authority domain {authority.value} must carry parent node references")

        # Enforce parent node existence in the tracker
        for parent_id in parent_node_ids:
            if not self._tracker.get_node(parent_id):
                raise ValueError(f"Missing required parent provenance node in DAG: '{parent_id}'")

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
        """Verify that a node's causal ancestry contains nodes from all required authority domains."""
        ancestry = self.get_ancestry(node_id)
        found_authorities = {node.artifact_type for node in ancestry}
        return all(req.value in found_authorities for req in required_authorities)
