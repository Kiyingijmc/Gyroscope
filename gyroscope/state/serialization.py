"""State serialization and deserialization routines adhering to STATE_SERIALIZATION_CONTRACT."""

import hashlib
import json
from typing import Any, Dict, Tuple

from gyroscope.core.exceptions import StateCorruptedException, VersionMismatchError
from gyroscope.state.base import SystemState


def compute_snapshot_hash(snapshot_data: Dict[str, Any]) -> str:
    """Compute canonical SHA-256 hash of a snapshot envelope."""
    canonical_str = json.dumps(snapshot_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def serialize_state(state: SystemState) -> str:
    """Serialize system state into a canonical versioned JSON string with dual hash contracts."""
    state_hash = state.compute_state_hash()
    payload_hash = state.compute_state_payload_hash()

    data: Dict[str, Any] = {
        "configuration_hash": state.configuration_hash,
        "feature_version": state.feature_version,
        "last_event_id": state.last_event_id,
        "last_event_timestamp_ns": state.last_event_timestamp_ns,
        "model_version": state.model_version,
        "schema_version": state.schema_version,
        "sequence_number": state.sequence_number,
        "state_hash": state_hash,
        "state_payload": {
            "custom_state": state.custom_state,
            "processed_event_ids": sorted(list(state._processed_event_ids)),
        },
        "state_payload_hash": payload_hash,
        "symbol": state.symbol,
        "timeframe": state.timeframe,
    }
    snapshot_hash = compute_snapshot_hash(data)
    data["snapshot_hash"] = snapshot_hash
    return json.dumps(data, sort_keys=True, indent=2)


def deserialize_state(
    json_str: str,
    expected_schema_version: str = "1.0",
    expected_model_version: str = "1.0.0",
    expected_config_hash: str = None,
) -> SystemState:
    """Deserialize state JSON string and verify state hash, payload hash, and version invariants."""
    try:
        data = json.loads(json_str)
    except Exception as err:
        raise StateCorruptedException(f"Failed to parse JSON state payload: {err}") from err

    schema_version = data.get("schema_version")
    if schema_version != expected_schema_version:
        raise VersionMismatchError(
            f"Schema version mismatch: payload has '{schema_version}', expected '{expected_schema_version}'"
        )

    model_version = data.get("model_version")
    if model_version != expected_model_version:
        raise VersionMismatchError(
            f"Model version mismatch: payload has '{model_version}', expected '{expected_model_version}'"
        )

    config_hash = data.get("configuration_hash", "")
    if expected_config_hash and config_hash != expected_config_hash:
        raise VersionMismatchError(
            f"Configuration hash mismatch: payload has '{config_hash}', expected '{expected_config_hash}'"
        )

    payload = data.get("state_payload", {})
    custom_state = payload.get("custom_state", {})
    processed_event_ids = payload.get("processed_event_ids", [])

    state = SystemState(
        schema_version=schema_version,
        model_version=model_version,
        feature_version=data.get("feature_version", "1.0.0"),
        symbol=data.get("symbol", "GENERIC"),
        timeframe=data.get("timeframe", "1m"),
        sequence_number=data.get("sequence_number", 0),
        last_event_id=data.get("last_event_id", "INIT"),
        last_event_timestamp_ns=data.get("last_event_timestamp_ns", 0),
        configuration_hash=config_hash,
        custom_state=custom_state,
        _processed_event_ids=set(processed_event_ids),
    )

    computed_state_hash = state.compute_state_hash()
    header_state_hash = data.get("state_hash")
    if computed_state_hash != header_state_hash:
        raise StateCorruptedException(
            f"State hash integrity failure: header state_hash '{header_state_hash}' does not match computed state_hash '{computed_state_hash}'"
        )

    computed_payload_hash = state.compute_state_payload_hash()
    header_payload_hash = data.get("state_payload_hash")
    if header_payload_hash and computed_payload_hash != header_payload_hash:
        raise StateCorruptedException(
            f"State payload hash integrity failure: header state_payload_hash '{header_payload_hash}' does not match computed '{computed_payload_hash}'"
        )

    return state
