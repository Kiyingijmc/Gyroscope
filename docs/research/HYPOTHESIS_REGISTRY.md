# HYPOTHESIS REGISTRY

**Status:** ACTIVE SCHEMA
**Purpose:** Machine-readable registry and schema for tracking all quantitative hypotheses in Gyroscope.

---

## 1. SCHEMA SPECIFICATION

Each entry in `HYPOTHESIS_REGISTRY.md` or its JSON/YAML equivalent MUST conform to the following schema:

| Field | Type | Description |
| :--- | :--- | :--- |
| `hypothesis_id` | String | Unique identifier (e.g., `HYP-2026-001`) |
| `title` | String | Short descriptive title |
| `description` | String | Detailed scientific hypothesis statement |
| `mechanism` | String | Underlying structural/market microstructure mechanism |
| `motivation` | String | Empirical or theoretical motivation |
| `expected_effect` | String | Expected direction and nature of signal/predictive edge |
| `null_hypothesis` | String | Quantitative statement of $H_0$ |
| `alternative_hypothesis` | String | Quantitative statement of $H_1$ |
| `causal_requirements` | List[String] | Causal timestamp $F(t-)$ guarantees required |
| `dataset_requirements` | List[String] | Minimum data resolution, timeframes, symbols |
| `primary_metric` | String | Primary evaluation metric (e.g., Information Ratio, Deflated Sharpe) |
| `secondary_metrics` | List[String] | Max drawdown, turn-over, win-rate |
| `economic_threshold` | String | Minimum hurdle rate net of fees |
| `validation_protocol` | String | Bootstrap method, block length, OOS split ratio |
| `status` | Enum | `PROPOSED` \| `UNDER_TEST` \| `CONFIRMED` \| `REJECTED` \| `ARCHIVED` |
| `created_at` | Timestamp | ISO-8601 UTC creation date |
| `created_by` | String | Author / Researcher ID |
| `source_commit` | String | Commit SHA where hypothesis was registered |
| `related_experiments` | List[String] | List of `experiment_id`s |
| `decision` | String | Final decision summary and rationale |

---

## 2. REGISTRY ENTRIES

*No experimental results populated yet. (Schema active for future research registration).*
