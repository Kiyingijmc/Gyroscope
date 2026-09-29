# GYROSCOPE CONSTITUTION v1.0

**Status:** RATIFIED & ACTIVE
**Scope:** Entire Gyroscope Repository and Subsystems
**Precedence:** Supreme Governance Document for Code, Architecture, and Research

---

## 1. SYSTEM IDENTITY

Gyroscope is an independent, deterministic research and production trading system. It operates as an autonomous, self-contained platform designed for quantitative state estimation, evidence aggregation, risk control, and trade execution.

Gyroscope retains full independent evolution rights and is not bound by legacy constraints or direct coupling to external projects.

---

## 2. CONSTITUTIONAL PRIORITY OF INVARIANTS

The core engineering and operational priorities of Gyroscope are ordered as follows:

$$
\text{Survival} > \text{Correctness} > \text{Auditability / Provenance} > \text{Determinism} > \text{Stealth} > \text{Speed} > \text{PnL}
$$

1. **Survival:** System integrity, memory safety, drawdown limits, capital protection, and disaster containment override all other considerations.
2. **Correctness:** Mathematical, state-machine, and logical correctness take absolute priority over speed or speculative opportunities.
3. **Auditability / Provenance:** Every production state transition, risk decision, order event, and research output must be immutably recorded with complete lineage.
4. **Determinism:** Given identical inputs, configuration, model versions, and event sequences, Gyroscope must yield bit-for-bit identical state transitions and decisions.
5. **Stealth:** Execution footprint, order routing, and market interactions must minimize toxic signaling and information leakage.
6. **Speed:** Latency optimization is permitted only when it does not compromise items 1–5.
7. **PnL:** Profitability is an outcome of system correctness and disciplined risk management, never a justification for violating system invariants.

---

## 3. STRICT SEPARATION OF AUTHORITIES

Gyroscope mandates an absolute separation of functional authorities. Information flows strictly down the hierarchy; execution authority resides exclusively in explicit downstream authorities.

```
Observation (Market / Event Data)
   │
   ▼
Feature / State Estimation (Kalman / Filtered States)
   │
   ▼
Evidence (Signal / Confidence / Innovation Metrics)
   │
   ▼
Episode / Opportunity (Setup Context)
   │
   ▼
Risk Decision (Risk Authority Evaluation)
   │
   ▼
Execution Authorization (Execution Authority Validation)
   │
   ▼
Broker Command (Adapter / Wire Interface)
```

### Laws of Authority Boundaries
- **Research & Feature Laws:** Research models, Kalman filters, and evidence generators **NEVER** possess execution authority. They emit observations and metrics, not orders.
- **Risk Monopoly:** The **Risk Authority** holds exclusive veto and sizing power over all proposed opportunities. No position or order can bypass Risk Authority verification.
- **Execution Separation:** The **Execution Authority** controls order construction, timing, and routing tactics. It cannot alter risk boundaries or create unsanctioned trades.
- **Broker Isolation:** Broker/Exchange adapters are passive command translators. They possess zero discretionary trading logic.

---

## 4. RESEARCH VS PRODUCTION READINESS LEVELS (R0 - R4)

All code, models, features, and algorithms in Gyroscope must explicitly declare their Readiness Level (RL).

| Level | Classification | Description | Execution Permission |
| :--- | :--- | :--- | :--- |
| **R0** | Unvalidated | Exploratory idea, unverified math, or stub code | **FORBIDDEN** in Production |
| **R1** | Diagnostic | Offline empirical analysis, diagnostic scripts | **FORBIDDEN** in Production |
| **R2** | Research Candidate | Backtested model, validated against null hypothesis | **FORBIDDEN** in Production |
| **R3** | Production Candidate | Audited, deterministic implementation under paper testing | Simulated Execution Only |
| **R4** | Production | Fully hardened, benchmarked, audited code | Production Allowed |

### Enforcement Directive
No mechanism, parameter, or model classified as R0, R1, or R2 may silently enter or influence the production execution path. Attempts to pass R0–R2 artifacts into R4 execution paths must fail hard at runtime.

---

## 5. DETERMINISM LAW

1. **State Replayability:** LiveState given observation sequence $O_1 \dots O_n$ must match ReplayState given identical observation sequence $O_1 \dots O_n$.
2. **Randomness Banned in Production:** Pseudo-random number generators (PRNG) in production components are prohibited unless seeded with a deterministic, recorded seed derived strictly from event sequence and state hash.
3. **Clock Isolation:** System wall-clock time (`time.now()`) must **NEVER** be used inside state estimation or trading logic. Only explicit event timestamps ($F(t-)$) are valid for temporal calculation.

---

## 6. PROVENANCE & CAUSAL INTEGRITY

1. **Information Cutoff Rule:** For any decision made at temporal boundary $t$, only information $F(t-)$ (strictly prior to $t$) is accessible.
2. **Arrival vs Event Time:** Event timestamp ($t_{\text{event}}$) and arrival timestamp ($t_{\text{arrival}}$) are fundamentally distinct. Processing logic must never treat $t_{\text{arrival}}$ as $t_{\text{event}}$.
3. **Immutable Lineage:** Every decision artifact must log:
   - Code SHA and package versions
   - Configuration hash
   - Model version
   - Input observation IDs
   - Pre-state and post-state hashes
   - Causal timestamp lineage

---

## 7. AMENDMENT CONSTITUTIONAL PROCESS

Amendments to this Constitution require:
1. Formal Architectural Decision Record (ADR) justifying the amendment.
2. Explicit forensic audit confirming no safety, risk, or deterministic invariants are degraded.
3. Version increment (v1.0 → v1.1 or v2.0).
