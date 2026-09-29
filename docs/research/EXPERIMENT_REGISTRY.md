# EXPERIMENT REGISTRY

**Status:** ACTIVE SCHEMA
**Purpose:** Registry tracking every empirical experiment, configuration hash, dataset version, and execution result.

---

## 1. SCHEMA SPECIFICATION

Every experiment execution MUST record the following machine-readable metadata:

| Field | Type | Description |
| :--- | :--- | :--- |
| `experiment_id` | String | Unique identifier (e.g., `EXP-2026-001`) |
| `hypothesis_id` | String | Associated `hypothesis_id` |
| `family_id` | String | Model or strategy family identifier |
| `repository_sha` | String | Git commit SHA of exact code used |
| `dataset_version` | String | Version or key of dataset |
| `dataset_hash` | String | SHA-256 hash of dataset files |
| `feature_version` | String | Exact feature code version |
| `model_version` | String | Model version |
| `config_hash` | String | SHA-256 hash of experiment JSON/YAML config |
| `symbols` | List[String] | Asset universe |
| `timeframes` | List[String] | Bar aggregations or tick series |
| `date_range` | Object | `{ start: ISO8601, end: ISO8601 }` |
| `train_period` | Object | In-sample training dates |
| `validation_period` | Object | In-sample validation dates |
| `oos_period` | Object | Out-of-sample testing dates |
| `holdout_period` | Object | Strict unseen holdout dates |
| `execution_model` | String | Cost & latency simulation parameters |
| `cost_model` | String | Fee structure, slippage, bid-ask spread assumption |
| `null_model` | String | Benchmark null distribution used |
| `bootstrap_method` | String | e.g. `STATIONARY_BLOCK_BOOTSTRAP` |
| `block_length` | Integer | Average block length for bootstrap |
| `bootstrap_repetitions` | Integer | Number of resamples (e.g., 10,000) |
| `random_seed_policy` | String | Deterministic seed generation formula |
| `primary_metrics` | Object | Value, $p$-value, confidence interval |
| `secondary_metrics` | Object | Additional performance diagnostics |
| `status` | Enum | `RUNNING` \| `COMPLETED` \| `FAILED` \| `ABORTED` |
| `result_artifact` | String | Path or URI to detailed result artifact |
| `decision` | String | Conclusion, promotion to R2/R3 or rejection |

---

## 2. EXPERIMENT ENTRIES

*No active experiments executed yet. (Schema ready for initial research campaign).*
