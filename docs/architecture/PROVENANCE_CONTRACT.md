# PROVENANCE & LINEAGE CONTRACT v1.0

**Contract Version:** 1.0.0
**Status:** IMPLEMENTED AND FORENSICALLY VERIFIED
**Last Updated:** 2026-09-29

---

## 1. PURPOSE & ARCHITECTURAL SCOPE

This document specifies the immutable decision provenance model (`ProvenanceNode`), provenance tracker (`ProvenanceTracker`), and provenance store (`InMemoryProvenanceStore`).

---

## 2. PROVENANCE INVARIANTS

1. **Cryptographic Content Binding:** `ProvenanceNode.__init__()` validates that any provided `node_id` strictly equals `compute_deterministic_provenance_id(...)`. Rejects mismatching explicit IDs.
2. **Deep Immutability:** `ProvenanceNode.payload` is frozen as a `FrozenDict` and lists/tuples are recursively frozen. Caller mutations to original payloads after construction leave the node unchanged.
3. **Graph Integrity & DAG Cycle Prevention:** `InMemoryProvenanceStore.record()` performs parent presence verification and DFS traversal to detect and reject self-parents ($A \to A$) and arbitrary multi-node cycles ($A \to B \to C \to A$) before insertion.
4. **Immutability Protection:** Re-recording a node with identical content is idempotent; re-recording a node ID with conflicting content raises `ValueError`.
