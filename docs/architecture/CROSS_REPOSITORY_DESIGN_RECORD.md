# GYROSCOPE / FRACTAL-FLOW CROSS-REPOSITORY DESIGN RECORD v1.0

**Phase:** Phase 1 — Deterministic Contract, Identity, Replay & Provenance Kernel
**Date:** 2026-09-29

---

## 1. PURPOSE & ARCHITECTURAL RELATIONSHIP

This record documents the selective cross-pollination of production survivability, authority, exact accounting, idempotency, snapshot, and provenance patterns from **FRACTAL-FLOW** into **Gyroscope**.

Gyroscope does **NOT** import FRACTAL-FLOW strategy heuristics, scalping logic, legacy entry models, or broker adapters. Instead, Gyroscope extracts FRACTAL-FLOW's strongest engineering invariants and generalizes them for Gyroscope's deterministic, research-oriented architecture.

---

## 2. INVARIANT & ADAPTATION MATRIX

| FRACTAL-FLOW Concept | Gyroscope Adaptation | Architectural Reason & Implementation Location | Proving Tests |
| :--- | :--- | :--- | :--- |
| **Deterministic Intent Identity** | Deterministic Observation, Event, and Provenance Identity (`SHA-256`) | Replaces random UUIDs (`uuid.uuid4()`) to guarantee replay stability. Implemented in `gyroscope/observation/models.py`, `gyroscope/state/base.py`, `gyroscope/provenance/tracker.py`. | `test_deterministic_observation_identity`, `test_deterministic_provenance_identity`, `test_event_identity_and_idempotency` |
| **Idempotency** | Duplicate Event Processing & Tracking (`_processed_event_ids`) | Prevents duplicate event state mutation during replay or process restart. Implemented in `SystemState.process_event()`. | `test_event_identity_and_idempotency`, `test_state_event_processing_and_hash_stability` |
| **Decimal Risk Accounting** | Authoritative Numeric Boundary (`numeric.py`) | Prevents binary floating-point representation from defining financial/risk quantities. Implemented in `gyroscope/core/numeric.py`. | `test_numeric_determinism_boundary` |
| **State Snapshot Provenance** | Dual Hashing (`state_payload_hash` vs `state_hash` vs `snapshot_hash`) | Separates pure semantic state payload identity from configuration and sequence header context. Implemented in `gyroscope/state/serialization.py`. | `test_canonical_hashing_contracts` |
| **Gap Detection & Reordering** | Causal Reordering Buffer & Sequence Gap Detector (`GapDetector`) | Replaces silent state progression with explicit `DATA_GAP` and timestamp regression detection. Implemented in `gyroscope/engine/__init__.py`. | `test_causal_ordering_and_gap_detection` |
| **Snapshot / Replay Equivalence** | Pure Replay Engine & Snapshot Store (`DeterministicReplayEngine`) | Guarantees $Replay(E_1..E_n) == Snapshot(E_k) + Replay(E_{k+1}..E_n)$. Implemented in `gyroscope/engine/__init__.py`. | `test_full_replay_vs_snapshot_resume_equivalence` |
| **Lineage Auditability** | Immutability-Enforced Provenance Store (`InMemoryProvenanceStore`) | Guarantees causal ancestry tracing and forbids silent historical mutation. Implemented in `gyroscope/provenance/store.py`. | `test_provenance_store_ancestry_and_immutability` |
| **Unknown State Preservation** | Explicit Gap & Exception Fail-Closed Semantics | Unknown conditions remain explicitly unknown rather than defaulting to permissive state. Implemented across core exceptions. | All phase 1 tests |
| **Authority Separation** | Readiness Levels (`R0-R4`) & State Estimator Protocol Boundary | Research abstractions cannot acquire execution authority. Implemented in `gyroscope/core/types.py` and `gyroscope/core/estimation.py`. | `test_research_execution_boundary_invariant` |

---

## 3. CONCEPTS DELIBERATELY NOT IMPORTED & WHY

1. **Strategy Heuristics & Entry Models:** Strategy details (e.g. scalping logic, entry triggers) are domain-specific applications. Gyroscope is a state-centric research kernel, not a single-strategy bot.
2. **Broker-Specific Assumptions & Wire Coupling:** FRACTAL-FLOW's broker-specific execution semantics coupling internal state to specific exchange APIs was excluded to preserve model independence.
3. **Legacy Execution Coupling:** Gyroscope maintains strict separation between state estimation, evidence, opportunity, and execution authority.

---

## 4. INVARIANT STATUS SUMMARY

All non-negotiable invariants (I1–I20) defined for Phase 1 are fully satisfied, tested, and verified bit-for-bit across process boundaries.
