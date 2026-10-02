# REPLAY CONTRACT v1.0

**Status:** FROZEN
**Scope:** Replay engine guarantees, determinism validation, and edge-case handling.

---

## 1. THE CORE REPLAY INVARIANT

$$
\text{LiveState}(O_1 \dots O_n) \equiv \text{ReplayState}(O_1 \dots O_n)
$$

Given an identical ordered sequence of observations $O_1, O_2, \dots, O_n$, initial configuration $C_0$, and initial model state $S_0$, the resulting system state $S_n$ produced by historical offline replay MUST be bit-for-bit identical to the state produced during live execution.

---

## 2. REPLAY EDGE-CASE REQUIREMENTS

| Edge Case | Expected System Behavior | Test Verification Required |
| :--- | :--- | :--- |
| **Normal Sequence** | State transitions sequentially; state hash updates monotonically. | `test_replay_normal_sequence` |
| **Duplicate Event** | Event processor detects identical `event_id`; suppresses duplicate processing (idempotent). | `test_replay_duplicate_event_idempotency` |
| **Missing Event / Gap** | Sequence gap detected via `sequence_number`; flag `DATA_GAP` warning, maintain state integrity. | `test_replay_sequence_gap_handling` |
| **Out-Of-Order Event** | Replay engine sorts buffered incoming events strictly by $t_{\text{event}}$ before applying state transitions. | `test_replay_out_of_order_buffering` |
| **Snapshot Restore & Resume** | Replaying $O_1 \dots O_k \to \text{Snapshot} \to \text{Resume } O_{k+1} \dots O_n$ matches continuous replay. | `test_replay_snapshot_resume_identity` |
| **Version Mismatch** | Engine rejects replaying events generated under incompatible model version without explicit migration. | `test_replay_version_mismatch_rejection` |

---

## 3. NON-DETERMINISM ELIMINATION LAWS

To guarantee the Replay Invariant:
1. **No Real Wall Clocks:** `datetime.now()` or `time.time()` calls inside state machinery are forbidden.
2. **No Unseeded Randomness:** `random` module usage without explicit seed derived from event context is forbidden.
3. **No Non-Deterministic Iteration:** Dictionary keys must be sorted or ordered (`collections.OrderedDict` or explicit key sorting) when serialized or hashed.
