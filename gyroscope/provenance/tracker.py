"""Provenance node tracking, causal lineage primitives, and deterministic node identity with deep immutability and cryptographic content-binding."""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union


class FrozenDict(Mapping):
    """Deeply immutable mapping wrapper."""

    def __init__(self, data: Optional[Union[Mapping, Dict[str, Any]]] = None):
        self._data: Dict[str, Any] = {}
        if data:
            for k, v in data.items():
                self._data[k] = _deep_freeze(v)

    def __getitem__(self, key: Any) -> Any:
        return self._data[key]

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __repr__(self) -> str:
        return f"FrozenDict({self._data!r})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, FrozenDict):
            return self._data == other._data
        if isinstance(other, Mapping):
            return self._data == dict(other)
        return False

    def __hash__(self) -> int:
        canonical_str = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        h_bytes = hashlib.sha256(canonical_str.encode("utf-8")).digest()
        return int.from_bytes(h_bytes[:8], byteorder="big", signed=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert back to a standard Python dictionary recursively."""
        res = {}
        for k, v in self._data.items():
            if isinstance(v, FrozenDict):
                res[k] = v.to_dict()
            elif isinstance(v, tuple):
                res[k] = [_to_mutable(item) for item in v]
            else:
                res[k] = v
        return res


def _deep_freeze(val: Any) -> Any:
    """Recursively freeze lists to tuples and dicts to FrozenDict."""
    if isinstance(val, (dict, Mapping)):
        return FrozenDict(val)
    if isinstance(val, (list, set, tuple)):
        return tuple(_deep_freeze(item) for item in val)
    return val


def _to_mutable(val: Any) -> Any:
    if isinstance(val, FrozenDict):
        return val.to_dict()
    if isinstance(val, tuple):
        return [_to_mutable(item) for item in val]
    return val


def compute_deterministic_provenance_id(
    artifact_type: str,
    timestamp_ns: int,
    git_commit_sha: str,
    config_hash: str,
    model_version: str,
    parent_node_ids: Sequence[str],
    payload: Mapping[str, Any],
) -> str:
    """Derive a canonical, deterministic SHA-256 provenance node identifier."""
    mutable_payload = _to_mutable(payload) if isinstance(payload, FrozenDict) else payload
    canonical_dict = {
        "artifact_type": artifact_type,
        "config_hash": config_hash,
        "git_commit_sha": git_commit_sha,
        "model_version": model_version,
        "parent_node_ids": sorted(list(parent_node_ids)),
        "payload": mutable_payload,
        "timestamp_ns": timestamp_ns,
    }
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    h = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return f"prov_{h[:32]}"


@dataclass(frozen=True)
class ProvenanceNode:
    """Deeply immutable lineage record for decision artifacts with cryptographic identity binding."""
    node_id: str
    parent_node_ids: Tuple[str, ...]
    timestamp_ns: int
    git_commit_sha: str
    config_hash: str
    model_version: str
    artifact_type: str
    payload: FrozenDict
    payload_hash: str = field(init=False)

    def __init__(
        self,
        node_id: str,
        parent_node_ids: Sequence[str],
        timestamp_ns: int,
        git_commit_sha: str,
        config_hash: str,
        model_version: str,
        artifact_type: str,
        payload: Union[Mapping[str, Any], Dict[str, Any]],
    ):
        frozen_parents = tuple(sorted(list(parent_node_ids)))
        frozen_pld = payload if isinstance(payload, FrozenDict) else FrozenDict(payload)

        computed_id = compute_deterministic_provenance_id(
            artifact_type=artifact_type,
            timestamp_ns=timestamp_ns,
            git_commit_sha=git_commit_sha,
            config_hash=config_hash,
            model_version=model_version,
            parent_node_ids=frozen_parents,
            payload=frozen_pld,
        )

        if node_id != computed_id:
            raise ValueError(
                f"Cryptographic provenance identity mismatch: provided node_id '{node_id}' "
                f"does not match computed canonical node_id '{computed_id}'"
            )

        canonical_str = json.dumps(frozen_pld.to_dict(), sort_keys=True, separators=(",", ":"))
        pld_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "parent_node_ids", frozen_parents)
        object.__setattr__(self, "timestamp_ns", timestamp_ns)
        object.__setattr__(self, "git_commit_sha", git_commit_sha)
        object.__setattr__(self, "config_hash", config_hash)
        object.__setattr__(self, "model_version", model_version)
        object.__setattr__(self, "artifact_type", artifact_type)
        object.__setattr__(self, "payload", frozen_pld)
        object.__setattr__(self, "payload_hash", pld_hash)


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
        parent_node_ids: Optional[Sequence[str]] = None,
        node_id: Optional[str] = None,
    ) -> ProvenanceNode:
        """Record a new decision artifact in the provenance lineage."""
        parents = tuple(parent_node_ids or ())
        computed_nid = compute_deterministic_provenance_id(
            artifact_type=artifact_type,
            timestamp_ns=timestamp_ns,
            git_commit_sha=self.git_commit_sha,
            config_hash=self.config_hash,
            model_version=self.model_version,
            parent_node_ids=parents,
            payload=payload,
        )

        nid = node_id or computed_nid

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
