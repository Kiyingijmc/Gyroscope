# STATE SERIALIZATION CONTRACT v1.0

**Contract Version:** 1.0.0
**Status:** IMPLEMENTED AND FORENSICALLY VERIFIED
**Last Updated:** 2026-09-29

---

## 1. PURPOSE & ARCHITECTURAL SCOPE

This document defines the canonical JSON state serialization format, versioning requirements, and triple-hash integrity verification layers (`state_payload_hash`, `state_hash`, `snapshot_hash`) for Gyroscope `SystemState`.

---

## 2. CANONICAL TRIPLE HASH CONTRACT

Deserialization strictly validates three distinct cryptographic hash layers:

1. **`state_payload_hash` (Semantic Payload Integrity):**
   - **Scope:** Hashes only the semantic state payload (`custom_state`, `feature_version`, `model_version`, `processed_event_ids`, `schema_version`, `symbol`, `timeframe`).
   - **Purpose:** Identifies pure semantic domain state independent of execution sequence context.
   - **Requirement:** `MANDATORY`. Missing `state_payload_hash` causes `StateCorruptedException`.

2. **`state_hash` (Authoritative State Context Integrity):**
   - **Scope:** Hashes semantic payload PLUS sequence header context (`sequence_number`, `last_event_id`, `last_event_timestamp_ns`, `configuration_hash`).
   - **Purpose:** Proves exact state advancement position in time and sequence.
   - **Requirement:** `MANDATORY`. Mismatches cause `StateCorruptedException`.

3. **`snapshot_hash` (Snapshot Envelope Integrity):**
   - **Scope:** Hashes the complete JSON snapshot envelope excluding `snapshot_hash` itself.
   - **Purpose:** Protects serialized snapshot wrapper against envelope tampering before state object construction.
   - **Requirement:** `MANDATORY`. Missing or mismatched `snapshot_hash` causes `StateCorruptedException`.

---

## 3. THREAT MODEL & ENVELOPE RECOMPUTING

If an attacker modifies `custom_state` AND recomputes all three hashes (`state_payload_hash`, `state_hash`, `snapshot_hash`) consistently, the system treats the input as a valid newly minted snapshot envelope. Cryptographic hashes protect against stream corruption and tampering; authorization boundaries prevent malicious envelope minting.
