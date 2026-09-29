# RESEARCH PROTOCOL v1.0

**Status:** APPROVED
**Scope:** Mandatory research pipeline, falsification protocols, statistical standards, and validation workflows.

---

## 1. THE GYROSCOPE RESEARCH PIPELINE

Every research model, trading strategy hypothesis, signal feature, or execution mechanism in Gyroscope must strictly progress through the following sequential stages:

```
Hypothesis Formulation
    │
    ▼
Mechanism & Causal Construction
    │
    ▼
Null Model Construction
    │
    ▼
Baseline Benchmarking
    │
    ▼
Ablation Testing (Incremental Value Verification)
    │
    ▼
In-Sample & Out-of-Sample (OOS) Validation
    │
    ▼
Walk-Forward & Dependence-Aware Inference
    │
    ▼
Decision (Promote to R3 or Reject / Archive)
```

---

## 2. MANDATORY FALSIFICATION REQUIREMENT

1. **Explicit Null Hypothesis ($H_0$):** Every research proposal must define a quantitative null model (e.g., block-bootstrapped price shuffled series, zero-drift random walk, or un-filtered Kalman baseline).
2. **Falsification First:** The primary goal of research is attempting to falsify the candidate mechanism. An un-falsifiable hypothesis is scientifically invalid and automatically rejected.
3. **Valid Outcome:** A failed hypothesis ($H_0$ retained) is a valid, valuable research outcome. Negative results MUST be registered in `EXPERIMENT_REGISTRY.md` to prevent duplicate effort.

---

## 3. STATISTICAL VALIDATION STANDARDS

- **Dependence-Aware Inference:** Standard i.i.d. $t$-tests are strictly prohibited for financial time-series. Stationary Block Bootstrap or Politis-Romano Block Bootstrap must be used to preserve serial correlation and volatility clustering.
- **Economic Thresholds:** A mechanism must exceed transaction costs, slippage estimates, and execution drag by a minimum 2.0x factor before advancing to R2/R3 status.
- **Multiple Testing Correction:** When screening across $N$ hypotheses or feature combinations, false discovery rate (FDR) control (e.g., Benjamini-Hochberg) or White's Reality Check / Hansen's SPA must be applied.
