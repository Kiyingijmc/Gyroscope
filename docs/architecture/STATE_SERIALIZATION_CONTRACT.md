# STATE SERIALIZATION CONTRACT v1.0

**Status:** FROZEN
**Scope:** Specification for all state snapshotting, event log serialization, and state restore operations.

---

## 1. MANDATORY SERIALIZATION PAYLOAD SCHEMA

Every serialized state snapshot in Gyroscope MUST be represented as a deterministic, versioned dictionary or JSON-compatible structure with the following root schema:

```json
{
  "schema_version": "1.0",
  "model_version": "1.0.0",
  "symbol": "BTC-USD",
  "timeframe": "1m",
  "last_event_id": "evt_01J8X9Z123456789ABCDEF",
  "last_event_timestamp_ns": 1759190400000000000,
  "state_hash": "a3f8c9b2...64chars",
  "configuration_hash": "e7d1a4f0...64chars",
  "feature_version": "1.0.0",
  "state_payload": {
    "sequence_number": 40291,
    "position": {
      "quantity": 0.0,
      "entry_price": 0.0
    },
    "custom_state": {}
  }
}
```

---

## 2. INVARIANTS OF STATE SERIALIZATION

1. **Determinism:** Serialized byte streams must use canonical JSON formatting (sorted keys, explicit UTF-8 encoding, no floating-point formatting ambiguity).
2. **State Hash Verifiability:** `state_hash` is computed as `SHA256(canonical_json(state_payload))`. On deserialization, `state_hash` MUST be re-calculated and verified against the header hash. If hashes mismatch, deserialization MUST raise `StateCorruptedException`.
3. **Version Incompatibility Rejection:** If `schema_version` or `model_version` is incompatible with the restoring runtime, deserialization MUST fail immediately without attempting unsafe partial migration.
4. **Configuration Lock:** `configuration_hash` must match the running environment's active configuration hash. Unannounced configuration drift invalidates snapshot restoration.
