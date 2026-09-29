# ABLATION REGISTRY

**Status:** ACTIVE SCHEMA
**Purpose:** Incremental mechanism value verification tracking.

---

## 1. ABLATION PHILOSOPHY

No new mechanism (e.g. Kalman filter state, innovation threshold, NIS regime weighting, sequential evidence accumulator) may receive credit for system performance unless it demonstrates statistically significant incremental value relative to its immediate parent baseline:

$$
\text{Baseline} \longrightarrow \text{Baseline} + M_A \longrightarrow \text{Baseline} + M_A + M_B \longrightarrow \text{Baseline} + M_A + M_B + M_C
$$

If $M_B$ does not add statistically significant incremental performance over $M_A$, $M_B$ MUST be rejected regardless of how high total system performance is.

---

## 2. SCHEMA SPECIFICATION

| Field | Type | Description |
| :--- | :--- | :--- |
| `ablation_id` | String | Unique identifier (e.g., `ABL-2026-001`) |
| `parent_configuration` | String | Config hash or ID of parent baseline |
| `candidate_configuration` | String | Config hash or ID of candidate with added mechanism |
| `mechanism_added` | String | Description of newly introduced mechanism |
| `mechanism_removed` | String | Description of removed mechanism (if ablation test) |
| `dataset` | String | Dataset version and hash used |
| `metrics` | Object | Comparative performance delta (Delta Sharpe, Delta Drawdown) |
| `null_model` | String | Null hypothesis model for mechanism contribution |
| `bootstrap` | Object | Bootstrap parameters used for significance testing |
| `oos_result` | Object | Out-of-sample performance comparison |
| `economic_result` | Object | Net profit impact after fees/slippage |
| `stability_result` | Object | Parameter sensitivity & stability metric |
| `decision` | Enum | `ACCEPTED_INCREMENTAL_VALUE` \| `REJECTED_NO_VALUE` \| `REJECTED_INSTABILITY` |

---

## 3. ABLATION RECORD ENTRIES

*No ablations recorded yet. (Schema active).*
