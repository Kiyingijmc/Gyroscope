# ADR-0002: CAUSAL TIMESTAMPS & DETERMINISM LAWS

- **Decision ID:** ADR-0002
- **Date:** 2026-09-29
- **Status:** APPROVED
- **Context:** Quantitative state estimation and historical backtesting suffer from subtle lookahead bias and replay non-determinism if timestamps and state updates are not causally constrained.

---

## 1. PROBLEM
Common lookahead biases include:
- Conflating arrival time at the local socket ($t_{\text{arrival}}$) with event time at the matching engine ($t_{\text{event}}$).
- Incorporating information from bar $t$ into rolling volatility or state filters prior to signal calculation at decision point $t$.
- Using system wall clocks (`time.time()`) inside state transition logic, breaking replayability.

---

## 2. DECISION
1. **Four-Timestamp Contract:** Every observation must explicitly record `event_timestamp_ns`, `arrival_timestamp_ns`, `processing_timestamp_ns`, and `decision_timestamp_ns`.
2. **$F(t-)$ Information Cutoff:** Decisions made at timestamp $t$ may ONLY evaluate features derived strictly prior to $t$.
3. **Pure Determinism:** Real wall clocks and unseeded pseudo-random number generators are banned inside production state components.
4. **Canonical State Hash:** State snapshots must maintain a SHA-256 state hash calculated over canonical, ordered state serialization.

---

## 3. CONSEQUENCES
- **Positive:** Bit-for-bit replay equivalence between live execution and historical replay ($\text{LiveState} \equiv \text{ReplayState}$). Eliminates lookahead bias in research.
- **Negative:** Requires explicit timestamp passing and strict validation on all data ingestion pipelines.
