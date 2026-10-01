"""Read-only State Adapter providing state projections to strategy and risk without mutating authoritative state or creating duplicate state authorities."""

from typing import Any, Dict

from gyroscope.contracts.ports import StatePort
from gyroscope.state import SystemState


class ReadOnlyStateAdapter(StatePort):
    """Provides a read-only projection view of SystemState.

    Enforces that SystemState mutation occurs exclusively through Gyroscope's
    authoritative process_event reducer.
    """

    def __init__(self, state: SystemState) -> None:
        self._state = state

    @property
    def symbol(self) -> str:
        return self._state.symbol

    def get_latest_sequence_number(self) -> int:
        return self._state.sequence_number

    def get_state_payload_hash(self) -> str:
        return self._state.compute_state_payload_hash()

    def get_state_hash(self) -> str:
        return self._state.compute_state_hash()

    def get_snapshot_hash(self) -> str:
        payload_hash = self.get_state_payload_hash()
        state_hash = self.get_state_hash()
        import hashlib
        import json
        snap_dict = {
            "payload_hash": payload_hash,
            "sequence_number": self.get_latest_sequence_number(),
            "state_hash": state_hash,
            "symbol": self.symbol,
        }
        snap_json = json.dumps(snap_dict, sort_keys=True, separators=(",", ":"))
        return f"snap_{hashlib.sha256(snap_json.encode('utf-8')).hexdigest()[:32]}"

    def to_dict(self) -> Dict[str, Any]:
        """Return a copy of the underlying state payload."""
        return self._state.to_dict()
