# REPLAY & SNAPSHOT EQUIVALENCE CONTRACT v1.0

**Contract Version:** 1.0.0
**Status:** IMPLEMENTED AND FORENSICALLY VERIFIED
**Last Updated:** 2026-09-29

---

## 1. PURPOSE & ARCHITECTURAL SCOPE

This document defines the deterministic event replay engine (`DeterministicReplayEngine`), causal reordering buffer (`CausalOrderingBuffer`), sequence gap detector (`GapDetector`), and snapshot store (`SnapshotStore`).

---

## 2. REPLAY EQUIVALENCE INVARIANT

For any valid, ordered sequence of deterministic events $E_1, E_2, \dots, E_n$:

$$\text{Replay}(E_1 \dots E_n) \equiv \text{Snapshot}(E_1 \dots E_k) + \text{Replay}(E_{k+1} \dots E_n)$$

This equivalence is verified bit-for-bit across all boundary points $k \in [0, n]$ by checking:
- `state_payload_hash`
- `state_hash`
- `sequence_number`
- `custom_state`

---

## 3. REPLAY STATUS & AUTHORITY SEMANTICS

`DeterministicReplayEngine.process_buffered_events()` returns a strongly typed `ReplayResult` with explicit outcome statuses:

1. **`COMPLETE`**: Clean replay with continuous sequences. State is **FULLY AUTHORITATIVE**.
2. **`COMPLETE_WITH_DUPLICATES`**: Clean replay containing idempotent duplicate events. State is **FULLY AUTHORITATIVE**.
3. **`GAP_DETECTED`**: Sequence jump detected. `SequenceGapEvent` recorded. State is **DEGRADED / NON-AUTHORITATIVE** unless `fail_on_gap=True` halts execution.
4. **`TIMESTAMP_REGRESSION_DETECTED`**: Timestamp regression detected. State is **DEGRADED / NON-AUTHORITATIVE**.
5. **`FAILED`**: Replay halted due to deterministic error. State is **INVALID**.
