# CAUSAL TIMESTAMP CONTRACT v1.0

**Status:** FROZEN
**Scope:** Strict temporal causality, information cutoff enforcement, and clock disagreement prevention.

---

## 1. THE CAUSAL INFORMATION SET $F(t-)$

For any decision boundary at timestamp $t$:

$$
\mathcal{F}(t-) = \text{The set of all observations, events, and states causally available BEFORE } t
$$

No state calculation, feature calculation, model prediction, or risk evaluation performed at timestamp $t$ may access, compute over, or incorporate any information $X(t')$ where $t' \ge t$.

---

## 2. TAXONOMY OF TIMESTAMPS

Every observation event in Gyroscope MUST maintain four distinct, non-fungible timestamps:

| Timestamp Field | Name | Definition |
| :--- | :--- | :--- |
| `event_timestamp_ns` | Event Time ($t_{\text{event}}$) | Exact timestamp when the market event occurred at the source (e.g., exchange matching engine). |
| `arrival_timestamp_ns` | Arrival Time ($t_{\text{arrival}}$) | Timestamp when the raw packet arrived at Gyroscope network interface. |
| `processing_timestamp_ns` | Processing Time ($t_{\text{proc}}$) | Timestamp when the observation was processed by the state machine. |
| `decision_timestamp_ns` | Decision Time ($t_{\text{dec}}$) | Timestamp when an authorization or execution decision was evaluated. |

---

## 3. CAUSAL TIMESTAMP LAWS & PROHIBITIONS

### Law 1: Event Time Dominance
Feature calculations, rolling windows, state estimates, and Kalman updates MUST be driven strictly by `event_timestamp_ns`.

### Law 2: Arrival Time Non-Fungibility
`arrival_timestamp_ns` must NEVER be used as a substitute for `event_timestamp_ns`. Treating arrival time as event time introduces latency leakage and backtest lookahead bias.

### Law 3: Prohibition of Lookahead Statistics
The following constructions are EXPLICITLY PROHIBITED:

```python
# FORBIDDEN: Current return uses close of current bar, rolling volatility includes bar t,
# and current innovation uses current close prior to signal boundary t.
current_return = price[t] - price[t-1]
rolling_vol = std(prices[t-window : t+1]) # LEAK: includes price[t]
innovation = price[t] - kalman_predict(state[t-1])
```

Correct Causal Construction:

```python
# PERMITTED: Features at decision point t use information available strictly up to t-
prior_returns = price[t-1] - price[t-2]
rolling_vol = std(prices[t-window : t]) # Valid: window ends at t-1
innovation = price[t] - kalman_predict(state[t-1]) # Valid: prediction derived from state[t-1]
```

### Law 4: Out-Of-Order and Delayed Events
If an observation arrives with $t_{\text{event}} < t_{\text{last\_processed\_event}}$, it is classified as an **Out-Of-Order Event**. It MUST NOT silently corrupt current state; it must be routed through the re-ordering queue or handled via deterministic re-simulation.
