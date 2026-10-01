"""Provenance bridge mapping strategy and execution lineage fields into Gyroscope's single authoritative ProvenanceTracker/Store."""

from typing import Any, Dict, Optional, Sequence, Tuple

from gyroscope.contracts.ports import ProvenancePort
from gyroscope.contracts.types import AuthorityDomain
from gyroscope.provenance.tracker import ProvenanceNode, ProvenanceTracker


class ProvenanceBridge(ProvenancePort):
    """Bridge adapter mapping domain events and decisions into Gyroscope's single authoritative provenance DAG."""

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
        """Record a domain event node into the single authoritative provenance graph and return its deterministic node_id."""
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
