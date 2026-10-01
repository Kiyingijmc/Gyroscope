"""Deterministic event ordering, gap detection, replay engine, and snapshot store abstractions."""

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Callable, Dict, List, Optional, Tuple

from gyroscope.core.exceptions import DeterminismViolationError, StateCorruptedException
from gyroscope.state.base import Event, SystemState
from gyroscope.state.serialization import compute_snapshot_hash, serialize_state, deserialize_state


class GapStatus(str, Enum):
    """Sequence continuity status."""
    CONTINUOUS = "CONTINUOUS"
    DATA_GAP = "DATA_GAP"
    DUPLICATE = "DUPLICATE"
    LATE_ARRIVING = "LATE_ARRIVING"
    SEQUENCE_REGRESSION = "SEQUENCE_REGRESSION"
    TIMESTAMP_REGRESSION = "TIMESTAMP_REGRESSION"


@dataclass(frozen=True)
class SequenceGapEvent:
    """Explicit domain representation of a sequence discontinuity or out-of-order event."""
    status: GapStatus
    expected_sequence: int
    received_sequence: int
    event_id: str
    event_timestamp_ns: int
    last_processed_timestamp_ns: int
    details: str = ""


class GapDetector:
    """Monitors incoming sequence numbers and timestamps for sequence gaps and regressions."""

    def __init__(self, initial_sequence: int = 0, initial_timestamp_ns: int = 0):
        self.expected_sequence = initial_sequence + 1
        self.last_timestamp_ns = initial_timestamp_ns
        self.detected_gaps: List[SequenceGapEvent] = []

    def inspect(self, event: Event) -> GapStatus:
        """Inspect an incoming event and return its continuity status."""
        status = GapStatus.CONTINUOUS
        details = ""

        if event.sequence_number > 0:
            if event.sequence_number < self.expected_sequence:
                status = GapStatus.DUPLICATE
                details = f"Received sequence {event.sequence_number} < expected {self.expected_sequence}"
            elif event.sequence_number > self.expected_sequence:
                status = GapStatus.DATA_GAP
                details = f"Sequence jump detected: expected {self.expected_sequence}, got {event.sequence_number}"

        if event.event_timestamp_ns < self.last_timestamp_ns:
            if status == GapStatus.CONTINUOUS:
                status = GapStatus.TIMESTAMP_REGRESSION
            details += f" Timestamp regression: event ts {event.event_timestamp_ns} < last ts {self.last_timestamp_ns}"

        if status in (GapStatus.DATA_GAP, GapStatus.TIMESTAMP_REGRESSION, GapStatus.SEQUENCE_REGRESSION):
            gap_evt = SequenceGapEvent(
                status=status,
                expected_sequence=self.expected_sequence,
                received_sequence=event.sequence_number,
                event_id=event.event_id,
                event_timestamp_ns=event.event_timestamp_ns,
                last_processed_timestamp_ns=self.last_timestamp_ns,
                details=details.strip(),
            )
            self.detected_gaps.append(gap_evt)

        # Resynchronize sequence expectation to sequence_number + 1 regardless of gap status (unless duplicate)
        if event.sequence_number >= self.expected_sequence:
            self.expected_sequence = event.sequence_number + 1

        if event.event_timestamp_ns > self.last_timestamp_ns:
            self.last_timestamp_ns = event.event_timestamp_ns

        return status


class CausalOrderingBuffer:
    """Buffers and reorders events deterministically based on timestamp, sequence, source, and event_id tie-breakers."""

    def __init__(self):
        self._buffer: List[Event] = []

    def push(self, event: Event) -> None:
        """Add an event to the reordering buffer."""
        self._buffer.append(event)

    def push_many(self, events: List[Event]) -> None:
        for evt in events:
            self.push(evt)

    def flush_ordered(self) -> List[Event]:
        """Flush all buffered events in canonical, deterministic total order.

        Ordering priority:
        1. event_timestamp_ns (ascending)
        2. sequence_number (ascending)
        3. source (ascending lexically)
        4. event_id (ascending lexically - deterministic tie-breaker)
        """
        ordered = sorted(
            self._buffer,
            key=lambda e: (e.event_timestamp_ns, e.sequence_number, e.source, e.event_id),
        )
        self._buffer.clear()
        return ordered


@dataclass
class SnapshotEnvelope:
    """Canonical snapshot wrapper for state resume and recovery."""
    snapshot_id: str
    sequence_number: int
    last_event_id: str
    last_event_timestamp_ns: int
    state_payload_hash: str
    state_hash: str
    snapshot_hash: str
    serialized_state: str
    schema_version: str = "1.0"
    model_version: str = "1.0.0"
    configuration_hash: str = "0000000000000000000000000000000000000000000000000000000000000000"


class SnapshotStore:
    """In-memory or persistent snapshot manager satisfying snapshot / replay equivalence contracts."""

    def __init__(self):
        self._snapshots: Dict[str, SnapshotEnvelope] = {}
        self._latest_snapshot_id: Optional[str] = None

    def save_snapshot(self, state: SystemState) -> SnapshotEnvelope:
        """Create and store a canonical snapshot envelope from a SystemState instance."""
        serialized = serialize_state(state)
        state_hash = state.compute_state_hash()
        payload_hash = state.compute_state_payload_hash()

        envelope_dict = {
            "configuration_hash": state.configuration_hash,
            "last_event_id": state.last_event_id,
            "last_event_timestamp_ns": state.last_event_timestamp_ns,
            "model_version": state.model_version,
            "schema_version": state.schema_version,
            "sequence_number": state.sequence_number,
            "serialized_state": serialized,
            "state_hash": state_hash,
            "state_payload_hash": payload_hash,
        }
        snap_hash = compute_snapshot_hash(envelope_dict)
        snapshot_id = f"snap_{snap_hash[:32]}"

        envelope = SnapshotEnvelope(
            snapshot_id=snapshot_id,
            sequence_number=state.sequence_number,
            last_event_id=state.last_event_id,
            last_event_timestamp_ns=state.last_event_timestamp_ns,
            state_payload_hash=payload_hash,
            state_hash=state_hash,
            snapshot_hash=snap_hash,
            serialized_state=serialized,
            schema_version=state.schema_version,
            model_version=state.model_version,
            configuration_hash=state.configuration_hash,
        )

        self._snapshots[snapshot_id] = envelope
        self._latest_snapshot_id = snapshot_id
        return envelope

    def get_latest_snapshot(self) -> Optional[SnapshotEnvelope]:
        if self._latest_snapshot_id:
            return self._snapshots.get(self._latest_snapshot_id)
        return None

    def load_state(self, snapshot_id: str) -> SystemState:
        """Load and verify a SystemState from a snapshot ID."""
        envelope = self._snapshots.get(snapshot_id)
        if not envelope:
            raise KeyError(f"Snapshot ID not found: {snapshot_id}")

        state = deserialize_state(
            envelope.serialized_state,
            expected_schema_version=envelope.schema_version,
            expected_model_version=envelope.model_version,
            expected_config_hash=envelope.configuration_hash,
        )
        return state


class ReplayStatus(str, Enum):
    """Explicit replay outcome status."""
    COMPLETE = "COMPLETE"
    COMPLETE_WITH_DUPLICATES = "COMPLETE_WITH_DUPLICATES"
    GAP_DETECTED = "GAP_DETECTED"
    TIMESTAMP_REGRESSION_DETECTED = "TIMESTAMP_REGRESSION_DETECTED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ReplayResult:
    """Explicit outcome object returned by DeterministicReplayEngine."""
    status: ReplayStatus
    final_state: SystemState
    processed_count: int
    duplicate_count: int
    gap_events: Tuple[SequenceGapEvent, ...]

    @property
    def is_authoritative(self) -> bool:
        """Explicit machine-readable authority boundary.

        Only COMPLETE and COMPLETE_WITH_DUPLICATES produce authoritative state.
        GAP_DETECTED, TIMESTAMP_REGRESSION_DETECTED, and FAILED states are strictly degraded/non-authoritative.
        """
        return self.status in (ReplayStatus.COMPLETE, ReplayStatus.COMPLETE_WITH_DUPLICATES)


class DeterministicReplayEngine:
    """Pure deterministic event replay engine.

    Responsibilities:
      - Validates event identity
      - Orders events deterministically
      - Detects sequence gaps
      - Applies events through SystemState reducer
      - Returns strongly typed ReplayResult with explicit is_authoritative boundary
      - Guarantees: Replay(E1...En) == Snapshot(Ek) + Replay(Ek+1...En)
    """

    def __init__(self, initial_state: Optional[SystemState] = None, fail_on_gap: bool = False):
        self.state = initial_state or SystemState()
        self.fail_on_gap = fail_on_gap
        self.gap_detector = GapDetector(
            initial_sequence=self.state.sequence_number,
            initial_timestamp_ns=self.state.last_event_timestamp_ns,
        )
        self.buffer = CausalOrderingBuffer()

    def submit_events(self, events: List[Event]) -> None:
        """Submit unordered events to the causal reordering buffer."""
        self.buffer.push_many(events)

    def process_buffered_events(self) -> ReplayResult:
        """Flush buffered events deterministically, inspect for gaps, and reduce state."""
        ordered = self.buffer.flush_ordered()
        processed_count = 0
        duplicate_count = 0

        for evt in ordered:
            status = self.gap_detector.inspect(evt)
            if self.fail_on_gap and status == GapStatus.DATA_GAP:
                raise DeterminismViolationError(f"Replay halted due to sequence gap at event {evt.event_id}")

            applied = self.state.process_event(evt)
            if applied:
                processed_count += 1
            else:
                duplicate_count += 1

        gap_events = tuple(self.gap_detector.detected_gaps)
        if any(g.status == GapStatus.DATA_GAP for g in gap_events):
            replay_status = ReplayStatus.GAP_DETECTED
        elif any(g.status == GapStatus.TIMESTAMP_REGRESSION for g in gap_events):
            replay_status = ReplayStatus.TIMESTAMP_REGRESSION_DETECTED
        elif duplicate_count > 0:
            replay_status = ReplayStatus.COMPLETE_WITH_DUPLICATES
        else:
            replay_status = ReplayStatus.COMPLETE

        return ReplayResult(
            status=replay_status,
            final_state=self.state,
            processed_count=processed_count,
            duplicate_count=duplicate_count,
            gap_events=gap_events,
        )

    def replay_stream_with_status(self, events: List[Event]) -> ReplayResult:
        """Replay stream of events and return full ReplayResult with explicit authority boundary."""
        self.submit_events(events)
        return self.process_buffered_events()

    def replay_stream(self, events: List[Event]) -> SystemState:
        """Replay a stream of events cleanly from scratch or current state and return state for compatibility."""
        res = self.replay_stream_with_status(events)
        return res.final_state
