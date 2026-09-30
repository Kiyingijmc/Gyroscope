"""Abstract and in-memory provenance store abstractions."""

from abc import ABC, abstractmethod
from typing import List, Optional

from gyroscope.provenance.tracker import ProvenanceNode


class ProvenanceStore(ABC):
    """Abstract interface for immutable decision provenance persistence."""

    @abstractmethod
    def record(self, node: ProvenanceNode) -> None:
        """Record an immutable provenance node."""
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[ProvenanceNode]:
        """Retrieve a provenance node by unique identity."""
        pass

    @abstractmethod
    def trace_ancestry(self, node_id: str) -> List[ProvenanceNode]:
        """Trace causal parent lineage for a given node."""
        pass


class InMemoryProvenanceStore(ProvenanceStore):
    """In-memory implementation of ProvenanceStore with immutability guarantees."""

    def __init__(self):
        self._nodes = {}

    def record(self, node: ProvenanceNode) -> None:
        if node.node_id in self._nodes:
            existing = self._nodes[node.node_id]
            if existing != node:
                raise ValueError(
                    f"Attempted to mutate historical provenance node {node.node_id} with conflicting payload."
                )
            return
        self._nodes[node.node_id] = node

    def get_node(self, node_id: str) -> Optional[ProvenanceNode]:
        return self._nodes.get(node_id)

    def trace_ancestry(self, node_id: str) -> List[ProvenanceNode]:
        ancestry = []
        visited = set()
        queue = [node_id]

        while queue:
            curr_id = queue.pop(0)
            if curr_id in visited:
                continue
            visited.add(curr_id)
            node = self._nodes.get(curr_id)
            if node:
                ancestry.append(node)
                queue.extend(node.parent_node_ids)

        return ancestry
