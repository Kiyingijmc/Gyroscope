"""Durable WAL event journal enforcing 7-phase transaction lifecycle and crash-tail recovery.

Lifecycle:
PREPARED -> CAPTURED_OFFSET -> WRITTEN -> FLUSHED -> FSYNCED -> PUBLISHED_MEMORY -> COMMITTED
"""

from enum import Enum, auto
import json
import os
from pathlib import Path

from zlib import crc32
from typing import Any, Dict, List, Optional, Tuple


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
    """Write-Ahead Log event journal with strict 7-stage commit lifecycle and CRC32 crash-tail recovery."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._journal_state = JournalState.UNINITIALIZED
        self._committed_events: List[Dict[str, Any]] = []
        self._pending_event: Optional[Dict[str, Any]] = None
        self._pending_offset: Optional[int] = None
        self._file_obj = None

        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.recover_and_replay()

    @property
    def state(self) -> JournalState:
        return self._journal_state

    def prepare_event(self, event_data: Dict[str, Any]) -> None:
        """Stage 1: Validate event data and establish transaction record."""
        if self._journal_state in (JournalState.UNINITIALIZED, JournalState.COMMITTED):
            self._pending_event = event_data
            self._pending_offset = None
            self._journal_state = JournalState.PREPARED
        else:
            self._journal_state = JournalState.FAULTED
            raise RuntimeError(f"Cannot prepare event in journal state {self._journal_state}")

    def capture_offset(self) -> int:
        """Stage 2: Capture actual file append offset."""
        if self._journal_state == JournalState.PREPARED:
            if self._file_obj is None or self._file_obj.closed:
                self._file_obj = open(self.file_path, "a+b")
            self._file_obj.seek(0, os.SEEK_END)
            self._pending_offset = self._file_obj.tell()
            self._journal_state = JournalState.CAPTURED_OFFSET
            return self._pending_offset
        else:
            self._journal_state = JournalState.FAULTED
            raise RuntimeError(f"Invalid transition to CAPTURED_OFFSET from {self._journal_state}")

    def write_to_disk(self) -> None:
        """Stage 3: Write CRC32-framed record bytes to file buffer."""
        if self._journal_state == JournalState.CAPTURED_OFFSET:
            payload_json = json.dumps(self._pending_event, sort_keys=True, separators=(",", ":")).encode("utf-8")
            checksum = crc32(payload_json) & 0xFFFFFFFF
            length = len(payload_json)

            # Frame header: 4-byte CRC32 + 4-byte payload length + payload
            frame = checksum.to_bytes(4, byteorder="big") + length.to_bytes(4, byteorder="big") + payload_json
            self._file_obj.write(frame)
            self._journal_state = JournalState.WRITTEN
        else:
            self._journal_state = JournalState.FAULTED
            raise RuntimeError(f"Invalid transition to WRITTEN from {self._journal_state}")

    def flush_buffer(self) -> None:
        """Stage 4: Explicitly flush user-space file buffer to OS."""
        if self._journal_state == JournalState.WRITTEN:
            self._file_obj.flush()
            self._journal_state = JournalState.FLUSHED
        else:
            self._journal_state = JournalState.FAULTED
            raise RuntimeError(f"Invalid transition to FLUSHED from {self._journal_state}")

    def fsync_to_disk(self) -> None:
        """Stage 5: Invoke OS sync primitive (os.fsync)."""
        if self._journal_state == JournalState.FLUSHED:
            os.fsync(self._file_obj.fileno())
            self._journal_state = JournalState.FSYNCED
        else:
            self._journal_state = JournalState.FAULTED
            raise RuntimeError(f"Invalid transition to FSYNCED from {self._journal_state}")

    def publish_to_memory(self) -> None:
        """Stage 6: Publish event to authoritative in-memory state."""
        if self._journal_state == JournalState.FSYNCED:
            if self._pending_event:
                self._committed_events.append(self._pending_event)
            self._journal_state = JournalState.PUBLISHED_MEMORY
        else:
            self._journal_state = JournalState.FAULTED
            raise RuntimeError(f"Invalid transition to PUBLISHED_MEMORY from {self._journal_state}")

    def commit(self) -> None:
        """Stage 7: Mark transaction committed."""
        if self._journal_state == JournalState.PUBLISHED_MEMORY:
            self._pending_event = None
            self._pending_offset = None
            self._journal_state = JournalState.COMMITTED
        else:
            self._journal_state = JournalState.FAULTED
            raise RuntimeError(f"Invalid transition to COMMITTED from {self._journal_state}")

    def append_atomic(self, event_data: Dict[str, Any]) -> None:
        """Execute complete 7-stage transaction lifecycle."""
        self.prepare_event(event_data)
        self.capture_offset()
        self.write_to_disk()
        self.flush_buffer()
        self.fsync_to_disk()
        self.publish_to_memory()
        self.commit()

    def get_committed_events(self) -> List[Dict[str, Any]]:
        return list(self._committed_events)

    def recover_and_replay(self) -> None:
        """Scan WAL file, validate framing & CRC32 checksums, truncate incomplete/torn tail, and rebuild committed memory state."""
        if self._file_obj and not self._file_obj.closed:
            self._file_obj.close()
            self._file_obj = None

        self._committed_events.clear()
        if not self.file_path.exists():
            self._journal_state = JournalState.COMMITTED
            return

        valid_bytes_offset = 0
        with open(self.file_path, "rb") as f:
            while True:
                header = f.read(8)
                if not header or len(header) < 8:
                    break  # End of file or incomplete header at tail

                expected_crc = int.from_bytes(header[:4], byteorder="big")
                payload_len = int.from_bytes(header[4:8], byteorder="big")

                payload_bytes = f.read(payload_len)
                if len(payload_bytes) < payload_len:
                    break  # Incomplete payload (torn write at tail)

                computed_crc = crc32(payload_bytes) & 0xFFFFFFFF
                if computed_crc != expected_crc:
                    break  # Corrupt record at tail

                try:
                    event_dict = json.loads(payload_bytes.decode("utf-8"))
                    self._committed_events.append(event_dict)
                    valid_bytes_offset = f.tell()
                except Exception:
                    break  # Corrupt JSON payload

        # Truncate any incomplete or corrupt tail bytes
        with open(self.file_path, "a+b") as f:
            f.truncate(valid_bytes_offset)

        self._journal_state = JournalState.COMMITTED

    def close(self) -> None:
        if self._file_obj and not self._file_obj.closed:
            self._file_obj.close()
            self._file_obj = None
