# FRACTAL-FLOW IMPORT PLAN v1.0

**Status:** APPROVED PROTOCOL (Execution Pending Hardening Completion)
**Mandate:** Zero FRACTAL-FLOW code is imported, copied, or merged during foundation preparation.

---

## 1. CONTROLLED IMPORT PROCESS & CHECKLIST

When FRACTAL-FLOW hardening work is independently completed and audited, the import into Gyroscope will follow this strict 12-step sequence:

1. **Hardening Verification:** Confirm all FRACTAL-FLOW hardening tasks are completed and verified on FRACTAL-FLOW `main`.
2. **Audit Approval:** Conduct forensic code audit of FRACTAL-FLOW candidate commit.
3. **Source SHA Freeze:** Record the exact FRACTAL-FLOW source commit SHA (e.g., `FRACTAL_FLOW_COMMIT_SHA`).
4. **Gyroscope Baseline Snapshot:** Create a full test snapshot and git tag of Gyroscope before import (`gyroscope-pre-import-baseline`).
5. **Import Boundary Determination:** Identify exact target modules in Gyroscope (e.g., state estimation, signal processing) for baseline adoption.
6. **Explicit Scope Listing:** List every file and function slated for adoption; explicitly reject legacy/deprecated components.
7. **Divergence Documentation:** Record any structural or interface modifications required to adapt imported logic to Gyroscope Constitution v1.0.
8. **Test Adaptation:** Migrate and adapt FRACTAL-FLOW unit tests to Gyroscope test harness (`tests/unit`, `tests/deterministic`).
9. **Provenance Registration:** Log the import step in `docs/architecture/PROVENANCE_CONTRACT.md` and commit log with SHA references.
10. **Architecture Reconciliation:** Run full boundary check to ensure imported code does not bypass Risk, Execution, or Determinism controls.
11. **Verification Gate Execution:** Run complete `pytest` suite, determinism property tests, and CI quality gates.
12. **Independent Evolution:** Mark import baseline complete; Gyroscope continues independent architectural evolution.

---

## 2. PREVENTATIVE INVARIANTS

- **No Live Coupling:** FRACTAL-FLOW will not exist as a git submodule or runtime package dependency.
- **No Un-Audited Code:** Un-hardened FRACTAL-FLOW branches or intermediate commits are strictly prohibited from entering Gyroscope.
