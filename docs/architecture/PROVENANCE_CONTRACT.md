# PROVENANCE CONTRACT v1.0

**Status:** FROZEN
**Scope:** Lineage tracking, decision auditability, and causality chains across research and production.

---

## 1. PROVENANCE CHAIN CONCEPT

Every decision artifact generated within Gyroscope—whether a state transition, feature estimation, risk authorization, or broker order—must be linked to an immutable provenance record.

```
Observation (ID: obs_100)
    │
    ├─► State Transition (ID: st_101, PreHash: h0, PostHash: h1)
    │      │
    │      └─► Feature / Estimation (ID: est_102, Model: v1.0)
    │             │
    │             └─► Risk Authorization (ID: risk_103, ConfigHash: cfg_abc)
    │                    │
    │                    └─► Execution Order (ID: ord_104)
```

---

## 2. MANDATORY PROVENANCE METADATA

Every recorded provenance node must contain:

- `node_id`: Unique string identifier (e.g. ULID or UUIDv4).
- `parent_node_ids`: List of causal precursor IDs.
- `timestamp_ns`: Precise UTC nanosecond timestamp.
- `git_commit_sha`: Active repository SHA when generated.
- `config_hash`: SHA-256 hash of active runtime configuration.
- `model_version`: Exact version string of the generating model.
- `payload_hash`: SHA-256 hash of the output artifact.

---

## 3. AUDIT & REPRODUCIBILITY GUARANTEE

Given a specific provenance node (e.g., Execution Order `ord_104`), an auditor must be able to trace backwards through `parent_node_ids` to retrieve:
1. The exact raw observations that triggered the trade.
2. The model code and configuration parameters used.
3. The exact state hash at the moment of evaluation.
