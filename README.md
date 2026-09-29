# GYROSCOPE FOUNDATION v1.0

Deterministic Quantitative Research & Trading Foundation.

## Overview

Gyroscope is an independent, deterministic quantitative state-estimation and execution system. It provides an autonomous, research-safe environment anchored in strict authority separation, causal temporal boundaries ($F(t-)$), bit-for-bit replayability, and immutable provenance lineage.

> **Note:** Gyroscope Foundation v1.0 is a research and architectural foundation, not yet a fully implemented production trading engine.

---

## Constitutional Invariant Hierarchy

$$
\text{Survival} > \text{Correctness} > \text{Auditability / Provenance} > \text{Determinism} > \text{Stealth} > \text{Speed} > \text{PnL}
$$

---

## Implementation Status

### Currently Implemented (Runtime Code & Verified Tests)
- **Deterministic Core & Exceptions:** Custom domain exceptions, readiness levels (`R0`–`R4`).
- **Configuration Engine:** Deterministic, serializable, SHA-256 hashable `SystemConfig`.
- **Causal Observations:** `Observation` model enforcing four-timestamp causal boundaries ($t_{\text{event}} \le t_{\text{arrival}} \le t_{\text{proc}} \le t_{\text{dec}}$).
- **Deterministic State Machine:** `SystemState`, `Event`, SHA-256 state hashing, event idempotency tracking.
- **State Serialization:** Versioned, hash-verified JSON serialization and deserialization routines.
- **Provenance Tracking:** `ProvenanceTracker` and `ProvenanceNode` lineage ancestry graphs.
- **Structured Telemetry:** `StructuredLogger` converting events to category JSON logs.
- **Research Isolation & FRACTAL-FLOW Guard:** AST-based automated import parser preventing unauthorized FRACTAL-FLOW imports.

### Specified Future Work (Architectural Specifications Only)
- Predictive state estimation & Kalman filtering engines
- Predictive Evidence Fabric (PEF) runtime
- Normalized Innovation Squared (NIS) regime classifier & model health engine
- Episode & Opportunity context framing
- Production Risk Authority engine
- Execution Authority & Order state machinery
- Live Broker / Exchange Adapters
- Write-Ahead-Log (WAL) / Disk persistence engines

---

## Getting Started

### Prerequisites
- Python 3.12+
- `pytest`

### Running Test Matrix & Quality Gates
```bash
pytest -v
python3 -m compileall gyroscope tests
```

---

## Foundation Documentation & Manifests

- **Foundation Manifest:** [`docs/FOUNDATION_MANIFEST_v1.0.md`](docs/FOUNDATION_MANIFEST_v1.0.md)
- **Baseline Audit:** [`docs/GYROSCOPE_BASELINE.md`](docs/GYROSCOPE_BASELINE.md)
- **System Constitution:** [`constitution/GYROSCOPE_CONSTITUTION_v1.0.md`](constitution/GYROSCOPE_CONSTITUTION_v1.0.md)
- **Logical Architecture:** [`docs/architecture/GYROSCOPE_ARCHITECTURE_v1.0.md`](docs/architecture/GYROSCOPE_ARCHITECTURE_v1.0.md)
- **Research Protocol:** [`docs/research/RESEARCH_PROTOCOL.md`](docs/research/RESEARCH_PROTOCOL.md)
- **FRACTAL-FLOW Import Plan:** [`docs/integration/FRACTAL_FLOW_IMPORT_PLAN.md`](docs/integration/FRACTAL_FLOW_IMPORT_PLAN.md)
- **Architectural Decision Records:** [`docs/decisions/`](docs/decisions/)
