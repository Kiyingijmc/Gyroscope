"""Durable event journal adapted from FRACTAL-FLOW journal semantics.

Enforces strict transaction lifecycle:
PREPARE -> CAPTURE_OFFSET -> WRITE -> FLUSH -> FSYNC -> PUBLISH_MEMORY -> COMMITTED
"""

from enum import Enum, auto
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class JournalState(Enum):
    UNINITIALIZED = auto()
    PREPARED = auto()
    CAPTURED_OFFSET = auto()
    WRITTEN = auto()
    FLUSHED = auto()
    FSYNCED = auto()
    PUBLISHED_MEMORY = auto()
    COMMITTED = auto()
    FAULTED = auto()


class DurableEventJournal:
    """Durable WAL journal guaranteeing atomic commit and memory publish order."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._journal_state = JournalState.UNINITIALIZED
        self._committed_events: List[Dict[str, Any]] = []
        self._pending_event: Optional[Dict[str, Any]] = None

    @property
    def state(self) -> JournalState:
        return self._journal_state

    def prepare_event(self, event_data: Dict[str, Any]) -> None:
        if self._journal_state in (JournalState.UNINITIALIZED, JournalState.COMMITTED):
            self._pending_event = event_data
            self._journal_state = JournalState.PREPARED
        else:
            raise RuntimeError(f"Cannot prepare event in journal state {self._journal_state}")

    def capture_offset(self) -> None:
        if self._journal_state == JournalState.PREPARED:
            self._journal_state = JournalState.CAPTURED_OFFSET
        else:
            self._journal_state = JournalState.FAULTED
            raise RuntimeError(f"Invalid transition to CAPTURED_OFFSET from {self._journal_state}")

    def write_to_disk(self) -> None:
        if self._journal_state == JournalState.CAPTURED_OFFSET:
            # Append line to journal file
            import json
            line = json.dumps(self._pending_event, sort_keys=True) + "\n"
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(line)
            self._journal_state = JournalState.WRITTEN
        else:
            self._journal_state = JournalState.FAULTED
            raise RuntimeError(f"Invalid transition to WRITTEN from {self._journal_state}")

    def flush_and_fsync(self) -> None:
        if self._journal_state == JournalState.WRITTEN:
            # Sync to disk
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.flush()
                os.fsync(f.fileno())
            self._journal_state = JournalState.FSYNCED
        else:
            self._journal_state = JournalState.FAULTED
            raise RuntimeError(f"Invalid transition to FSYNCED from {self._journal_state}")

    def publish_to_memory(self) -> None:
        if self._journal_state == JournalState.FSYNCED:
            if self._pending_event:
                self._committed_events.append(self._pending_event)
            self._journal_state = JournalState.PUBLISHED_MEMORY
        else:
            self._journal_state = JournalState.FAULTED
            raise RuntimeError(f"Invalid transition to PUBLISHED_MEMORY from {self._journal_state}")

    def commit(self) -> None:
        if self._journal_state == JournalState.PUBLISHED_MEMORY:
            self._pending_event = None
            self._journal_state = JournalState.COMMITTED
        else:
            self._journal_state = JournalState.FAULTED
            raise RuntimeError(f"Invalid transition to COMMITTED from {self._journal_state}")

    def append_atomic(self, event_data: Dict[str, Any]) -> None:
        """Full transaction lifecycle helper."""
        self.prepare_event(event_data)
        self.capture_offset()
        self.write_to_disk()
        self.flush_and_fsync()
        self.publish_to_memory()
        self.commit()

    def get_committed_events(self) -> List[Dict[str, Any]]:
        return list(self._committed_events)
