# GYROSCOPE ARCHITECTURE SPECIFICATION v1.0

**Status:** APPROVED
**Scope:** Architectural boundaries, directory mappings, dependency rules, and authority boundaries.

---

## 1. LOGICAL MODULE BOUNDARIES

Gyroscope enforces strict package and directory boundaries to prevent authority corruption, circular dependencies, and illegal research leaks into production execution paths.

```
gyroscope/
├── core/            # Fundamental domain primitives, invariants, and base exceptions
├── observation/     # Canonical market data structures, causal timestamps, data quality checks
├── state/           # Deterministic state machine primitives, transitions, and state versioning
├── estimation/      # State estimation interfaces (e.g. Kalman filter contracts)
├── evidence/        # Evidence accumulation, confidence scoring, and innovation contracts
├── health/          # System sanity monitoring, circuit breakers, integrity validation
├── episodes/        # Opportunity framing, setup context, trade episode primitives
├── risk/            # Risk Authority, exposure limits, drawdown protection, position sizing
├── execution/       # Execution Authority, order state machines, fill processing
├── persistence/     # State snapshots, event logging, WAL (Write-Ahead-Log) abstractions
├── recovery/        # Snapshot restoration, crash recovery, crash replay engine
├── provenance/      # Provenance lineage tracking, hash chains, causal tracing
├── research/        # Offline research, backtesting harness, hypothesis validation (R0-R2)
└── adapters/        # Exchange/broker protocol translators and data feeds
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

## 3. AUTHORITY OWNERSHIP MATRIX

| Domain Module | Primary Authority / Responsibility | Permitted Side Effects |
| :--- | :--- | :--- |
| `observation` | Data ingest, timestamp ordering, tick validity | None (Pure functional parsing) |
| `state` | Deterministic state transitions & state hash | In-memory state mutation |
| `risk` | **Risk Authority:** Sizing, Veto, Drawdown caps | Emit Risk Decision (Approve / Reject) |
| `execution` | **Execution Authority:** Order generation & tactics | Emit Broker Order Intents |
| `adapters` | Protocol translation to wire formats | External Network I/O |
| `persistence` | Snapshot disk writing, event log append | Append-only storage IO |

---

## 4. FUTURE EXTENSION POINTS

- **State Estimators (`gyroscope/estimation`):** Plug-and-play interfaces for linear, extended, or unscented state estimators.
- **Evidence Accumulators (`gyroscope/evidence`):** Abstractions for sequential statistical evidence scoring without modifying Risk or Execution layers.
- **Risk Plugins (`gyroscope/risk`):** Modular risk rules implementing a common `RiskRule` protocol.
