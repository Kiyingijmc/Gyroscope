"""Abstract and in-memory provenance store abstractions with graph integrity and cycle detection."""

from abc import ABC, abstractmethod
from typing import List, Optional, Sequence

from gyroscope.provenance.tracker import ProvenanceNode


class ProvenanceStore(ABC):
    """Abstract interface for immutable decision provenance persistence."""

    @abstractmethod
    def record(self, node: ProvenanceNode, validate_parents: bool = True) -> None:
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
    """In-memory implementation of ProvenanceStore with immutability guarantees and arbitrary DAG cycle prevention."""

    def __init__(self):
        self._nodes = {}

    def _would_create_cycle(self, node_id: str, parent_node_ids: Sequence[str]) -> bool:
        """Check if adding node_id with parent_node_ids would introduce a cycle in the provenance graph using iterative BFS/DFS traversal."""
        visited = set()
        stack = list(parent_node_ids)

        while stack:
            curr_id = stack.pop()
            if curr_id == node_id:
                return True
            if curr_id in visited:
                continue
            visited.add(curr_id)
            curr_node = self._nodes.get(curr_id)
            if curr_node:
                stack.extend(curr_node.parent_node_ids)

        return False

    def record(self, node: ProvenanceNode, validate_parents: bool = True) -> None:
        """Record an immutable provenance node, validating parent presence and arbitrary DAG cycle prevention."""
        if node.node_id in node.parent_node_ids:
            raise ValueError(f"Self-referential provenance parent prohibited for node {node.node_id}")

        if validate_parents and node.parent_node_ids:
            for parent_id in node.parent_node_ids:
                if parent_id not in self._nodes:
                    raise KeyError(f"Parent provenance node '{parent_id}' not found in store for node '{node.node_id}'")

        if self._would_create_cycle(node.node_id, node.parent_node_ids):
            raise ValueError(f"Arbitrary cycle detected in provenance graph when inserting node '{node.node_id}'")

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
        """Backtrack through parent lineage using cycle-safe traversal."""
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
