"""Provenance node tracking, causal lineage primitives, and deterministic node identity."""

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Dict, List, Optional


def compute_deterministic_provenance_id(
    artifact_type: str,
    timestamp_ns: int,
    git_commit_sha: str,
    config_hash: str,
    model_version: str,
    parent_node_ids: List[str],
    payload: Dict[str, Any],
) -> str:
    """Derive a canonical, deterministic SHA-256 provenance node identifier."""
    canonical_dict = {
        "artifact_type": artifact_type,
        "config_hash": config_hash,
        "git_commit_sha": git_commit_sha,
        "model_version": model_version,
        "parent_node_ids": sorted(parent_node_ids),
        "payload": payload,
        "timestamp_ns": timestamp_ns,
    }
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    h = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return f"prov_{h[:32]}"


@dataclass(frozen=True)
class ProvenanceNode:
    """Immutable lineage record for decision artifacts with deterministic identity derivation."""
    node_id: str
    parent_node_ids: List[str]
    timestamp_ns: int
    git_commit_sha: str
    config_hash: str
    model_version: str
    artifact_type: str
    payload: Dict[str, Any]
    payload_hash: str = field(init=False)

    def __post_init__(self) -> None:
        canonical_str = json.dumps(self.payload, sort_keys=True, separators=(",", ":"))
        h = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
        object.__setattr__(self, "payload_hash", h)


class ProvenanceTracker:
    """In-memory or persistent provenance chain collector."""

    def __init__(self, git_commit_sha: str, config_hash: str, model_version: str):
        self.git_commit_sha = git_commit_sha
        self.config_hash = config_hash
        self.model_version = model_version
        self._nodes: Dict[str, ProvenanceNode] = {}

    def record(
        self,
        artifact_type: str,
        timestamp_ns: int,
        payload: Dict[str, Any],
        parent_node_ids: Optional[List[str]] = None,
        node_id: Optional[str] = None,
    ) -> ProvenanceNode:
        """Record a new decision artifact in the provenance lineage."""
        parents = parent_node_ids or []
        nid = node_id or compute_deterministic_provenance_id(
            artifact_type=artifact_type,
            timestamp_ns=timestamp_ns,
            git_commit_sha=self.git_commit_sha,
            config_hash=self.config_hash,
            model_version=self.model_version,
            parent_node_ids=parents,
            payload=payload,
        )
        node = ProvenanceNode(
            node_id=nid,
            parent_node_ids=parents,
            timestamp_ns=timestamp_ns,
            git_commit_sha=self.git_commit_sha,
            config_hash=self.config_hash,
            model_version=self.model_version,
            artifact_type=artifact_type,
            payload=payload,
        )
        self._nodes[nid] = node
        return node

    def get_node(self, node_id: str) -> Optional[ProvenanceNode]:
        return self._nodes.get(node_id)

    def trace_ancestry(self, node_id: str) -> List[ProvenanceNode]:
        """Backtrack through parent lineage to retrieve complete causal ancestry."""
        ancestry: List[ProvenanceNode] = []
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
