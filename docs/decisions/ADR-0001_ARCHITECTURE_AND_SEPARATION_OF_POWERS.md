# ADR-0001: ARCHITECTURE & SEPARATION OF POWERS

- **Decision ID:** ADR-0001
- **Date:** 2026-09-29
- **Status:** APPROVED
- **Context:** Gyroscope requires a production-grade architecture that prevents speculative models or research algorithms from executing unauthorized trades or altering risk boundaries.

---

## 1. PROBLEM
In legacy or loosely structured quantitative platforms, feature generators or signal models often instantiate trading logic directly, place orders, or bypass risk controls. This leads to untraceable trading behavior, unquantified drawdown exposure, and catastrophic failure modes during model degradation.

---

## 2. DECISION
We establish an absolute Separation of Authorities across the system pipeline:

$$\text{Observation} \longrightarrow \text{Estimation} \longrightarrow \text{Evidence} \longrightarrow \text{Episodes} \longrightarrow \text{Risk} \longrightarrow \text{Execution} \longrightarrow \text{Adapter}$$

1. **Research & Model Isolation:** Research algorithms (R0–R2) emit state observations and statistical evidence ONLY. They have zero execution authority.
2. **Monopoly of Risk:** The Risk Authority possesses sole authority to approve, resize, or veto proposed position changes.
3. **Monopoly of Execution:** The Execution Authority possesses sole authority to manage order state machines, tactical routing, and execution slicing.
4. **Readiness Level Barriers:** Python package boundaries enforce that production paths (`gyroscope/core`, `gyroscope/execution`, `gyroscope/risk`) can NEVER import from research paths (`gyroscope/research`).

---

## 3. CONSEQUENCES
- **Positive:** Complete safety against runaway models; strict auditability; predictable risk containment.
- **Negative:** Slightly higher verbosity when passing data down the authority pipeline via explicit event contracts.
- **Rejected Alternatives:** Monolithic strategy classes that handle indicators, signals, risk management, and order placement inside a single file.
