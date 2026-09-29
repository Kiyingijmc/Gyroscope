# GYROSCOPE ARCHITECTURE SPECIFICATION v1.0

**Status:** APPROVED SPECIFICATION & FOUNDATION MATRIX
**Scope:** Architectural boundaries, directory mappings, dependency rules, authority boundaries, and implementation status.

---

## 1. LOGICAL MODULE BOUNDARIES

Gyroscope enforces strict package and directory boundaries to prevent authority corruption, circular dependencies, and illegal research leaks into production execution paths.

```
gyroscope/
├── core/            # Fundamental domain primitives, invariants, and base exceptions
├── observation/     # Canonical market data structures, causal timestamps, data quality checks
├── state/           # Deterministic state machine primitives, transitions, and state versioning
├── config/          # Explicit, serializable, hashable configuration
├── provenance/      # Provenance lineage tracking, hash chains, causal tracing
├── logging/         # Structured telemetry logging
├── estimation/      # State estimation interfaces (e.g. Kalman filter contracts - SPECIFIED_ONLY)
├── evidence/        # Evidence accumulation, confidence scoring (SPECIFIED_ONLY)
├── health/          # System sanity monitoring, circuit breakers (SPECIFIED_ONLY)
├── episodes/        # Opportunity framing, setup context (SPECIFIED_ONLY)
├── risk/            # Risk Authority, exposure limits, drawdown protection (SPECIFIED_ONLY)
├── execution/       # Execution Authority, order state machines (SPECIFIED_ONLY)
├── persistence/     # WAL abstractions (SPECIFIED_ONLY / Foundational contract implemented)
├── recovery/        # Snapshot restoration (SPECIFIED_ONLY / Foundational contract implemented)
├── research/        # Offline research harness (R0-R2 isolation enforced)
└── adapters/        # Exchange/broker protocol translators (SPECIFIED_ONLY)
```

---

## 2. ALLOWED & FORBIDDEN DEPENDENCY GRAPH

To maintain systemic integrity, dependencies between modules must follow a strict acyclic top-down direction:

```
[adapters] ──► [observation] ──► [estimation] ──► [evidence] ──► [episodes]
                                                                     │
[persistence] ◄── [state] ◄──────────────────────────────────────────┘
      ▲              │
      │              ▼
 [recovery]     [risk] ──► [execution] ──► [adapters]
                     ▲
 [health] ───────────┘
```

### Dependency Laws
1. **Core:** `gyroscope/core` must have ZERO dependencies on other internal Gyroscope packages.
2. **Observation:** `gyroscope/observation` depends only on `core`. It cannot import state, risk, or execution.
3. **Estimation & Evidence:** May import `core` and `observation`. Cannot import `risk` or `execution`.
4. **Risk Authority:** May import `core`, `observation`, `state`, `evidence`, `episodes`, `health`. **CANNOT** depend on `execution` or `adapters`.
5. **Execution Authority:** May import `core`, `state`, `risk`. **CANNOT** import `research` or `estimation`.
6. **Research:** `gyroscope/research` may import production interfaces, but **NO PRODUCTION PATHWAY MAY EVER IMPORT FROM `gyroscope/research`**.

---

## 3. COMPONENT IMPLEMENTATION STATUS MATRIX

| Component | Specification | Runtime Implementation | Tests | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Core Types & Invariants** | Yes | Yes | Yes | `IMPLEMENTED` |
| **Configuration Engine** | Yes | Yes | Yes | `IMPLEMENTED` |
| **Observation & Causality** | Yes | Yes | Yes | `IMPLEMENTED` |
| **State Machine & Hash** | Yes | Yes | Yes | `IMPLEMENTED` |
| **Provenance Tracking** | Yes | Yes | Yes | `IMPLEMENTED` |
| **Structured Telemetry** | Yes | Yes | Yes | `IMPLEMENTED` |
| **State Serialization** | Yes | Yes | Yes | `IMPLEMENTED` |
| **State Replay Contract** | Yes | Foundation Contract | Yes | `IMPLEMENTED` |
| **State Recovery Contract** | Yes | Foundation Contract | Yes | `IMPLEMENTED` |
| **State Estimation / Kalman** | Yes | No | No | `SPECIFIED_ONLY` |
| **Evidence Engine / PEF** | Yes | No | No | `SPECIFIED_ONLY` |
| **Model Health / NIS** | Yes | No | No | `SPECIFIED_ONLY` |
| **Episode Framing** | Yes | No | No | `SPECIFIED_ONLY` |
| **Risk Authority** | Yes | No | No | `SPECIFIED_ONLY` |
| **Execution Authority** | Yes | No | No | `SPECIFIED_ONLY` |
| **Broker Adapters** | Yes | No | No | `SPECIFIED_ONLY` |
| **Production Persistence WAL** | Yes | No | No | `SPECIFIED_ONLY` |

---

## 4. AUTHORITY OWNERSHIP MATRIX

| Domain Module | Primary Authority / Responsibility | Permitted Side Effects |
| :--- | :--- | :--- |
| `observation` | Data ingest, timestamp ordering, tick validity | None (Pure functional parsing) |
| `state` | Deterministic state transitions & state hash | In-memory state mutation |
| `risk` | **Risk Authority:** Sizing, Veto, Drawdown caps | Emit Risk Decision (Approve / Reject) |
| `execution` | **Execution Authority:** Order generation & tactics | Emit Broker Order Intents |
| `adapters` | Protocol translation to wire formats | External Network I/O |
| `persistence` | Snapshot disk writing, event log append | Append-only storage IO |

---

## 5. FUTURE EXTENSION POINTS

- **State Estimators (`gyroscope/estimation`):** Plug-and-play interfaces for linear, extended, or unscented state estimators.
- **Evidence Accumulators (`gyroscope/evidence`):** Abstractions for sequential statistical evidence scoring without modifying Risk or Execution layers.
- **Risk Plugins (`gyroscope/risk`):** Modular risk rules implementing a common `RiskRule` protocol.
