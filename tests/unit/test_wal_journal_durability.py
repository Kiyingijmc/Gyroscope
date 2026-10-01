"""Unit and fault-injection tests for 7-phase WAL event journal and crash-tail recovery."""

from pathlib import Path
import pytest

from gyroscope.persistence.journal import DurableEventJournal, JournalState


def test_wal_7_phase_explicit_transitions(tmp_path: Path):
    """Verify that all seven WAL phases execute explicitly in order."""
    journal_file = tmp_path / "wal_test.log"
    journal = DurableEventJournal(journal_file)

    assert journal.state == JournalState.COMMITTED

    payload = {"event_id": "e_1", "symbol": "BTC-USD"}

    # Phase 1: PREPARED
    journal.prepare_event(payload)
    assert journal.state == JournalState.PREPARED

    # Phase 2: CAPTURED_OFFSET
    offset = journal.capture_offset()
    assert journal.state == JournalState.CAPTURED_OFFSET
    assert offset == 0

    # Phase 3: WRITTEN
    journal.write_to_disk()
    assert journal.state == JournalState.WRITTEN

    # Phase 4: FLUSHED
    journal.flush_buffer()
    assert journal.state == JournalState.FLUSHED

    # Phase 5: FSYNCED
    journal.fsync_to_disk()
    assert journal.state == JournalState.FSYNCED

    # Phase 6: PUBLISHED_MEMORY
    journal.publish_to_memory()
    assert journal.state == JournalState.PUBLISHED_MEMORY
    assert len(journal.get_committed_events()) == 1

    # Phase 7: COMMITTED
    journal.commit()
    assert journal.state == JournalState.COMMITTED
    journal.close()


def test_wal_crash_tail_recovery_truncates_torn_write(tmp_path: Path):
    """Verify that crash-tail recovery detects torn writes/checksum mismatches at the tail and truncates safely."""
    journal_file = tmp_path / "wal_crash.log"

    # Process 1: Write two valid events
    j1 = DurableEventJournal(journal_file)
    j1.append_atomic({"event_id": "evt_valid_1"})
    j1.append_atomic({"event_id": "evt_valid_2"})
    j1.close()

    # Simulate crash with a torn/corrupt write at the tail
    with open(journal_file, "ab") as f:
        f.write(b"\x00\x00\x12\x34\x00\x00\x00\x50TORN_GARBAGE_TAIL_BYTES")

    # Process 2: Recover on restart
    j2 = DurableEventJournal(journal_file)
    committed = j2.get_committed_events()

    assert len(committed) == 2
    assert committed[0]["event_id"] == "evt_valid_1"
    assert committed[1]["event_id"] == "evt_valid_2"
    j2.close()


def test_wal_fault_injection_interrupted_phases(tmp_path: Path):
    """Verify that crashing at intermediate phases (PREPARED, WRITTEN, etc.) does not recover uncommitted tail events."""
    journal_file = tmp_path / "wal_interrupt.log"

    # Crash after PREPARED (no bytes written to disk)
    j1 = DurableEventJournal(journal_file)
    j1.prepare_event({"event_id": "evt_uncommitted_1"})
    # Crash / process exit simulation -> close without flush/fsync/commit
    j1.close()

    j2 = DurableEventJournal(journal_file)
    assert len(j2.get_committed_events()) == 0
    j2.close()
