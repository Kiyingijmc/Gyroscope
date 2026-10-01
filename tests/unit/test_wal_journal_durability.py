"""Unit and fault-injection tests for 7-phase WAL event journal, durable commit markers, and crash-tail recovery."""

from pathlib import Path
import pytest

from gyroscope.persistence.journal import DurableEventJournal, JournalState


def test_wal_uncommitted_fsync_is_not_replayed(tmp_path: Path):
    """Verify that a transaction written, flushed, and fsynced but WITHOUT a durable commit marker is NOT replayed as committed."""
    journal_file = tmp_path / "wal_uncommitted.log"

    # Process 1: Prepare, write, flush, fsync... BUT crash before writing commit marker
    j1 = DurableEventJournal(journal_file)
    payload = {"event_id": "evt_uncommitted"}
    tx_id = j1.prepare_event(payload)
    j1.capture_offset()
    j1.write_to_disk()
    j1.flush_buffer()
    j1.fsync_to_disk()
    # Simulate crash before j1.commit()!
    j1.close()

    # Process 2: Recover on restart -> uncommitted transaction must NOT be replayed as committed
    j2 = DurableEventJournal(journal_file)
    committed = j2.get_committed_events()

    assert len(committed) == 0
    assert tx_id not in j2._committed_tx_ids
    j2.close()


def test_wal_committed_transaction_survives_restart(tmp_path: Path):
    """Verify that a fully committed transaction with a durable commit marker survives restart."""
    journal_file = tmp_path / "wal_committed.log"

    j1 = DurableEventJournal(journal_file)
    tx_id = j1.append_atomic({"event_id": "evt_committed_1"})
    j1.close()

    j2 = DurableEventJournal(journal_file)
    committed = j2.get_committed_events()

    assert len(committed) == 1
    assert committed[0]["event_id"] == "evt_committed_1"
    assert tx_id in j2._committed_tx_ids
    j2.close()


def test_wal_fault_injection_matrix_across_all_phases(tmp_path: Path):
    """Fault-injection matrix crashing after every phase to verify no uncommitted event is replayed."""
    for crash_phase in ["PREPARED", "CAPTURED_OFFSET", "WRITTEN", "FLUSHED", "FSYNCED", "PUBLISHED_MEMORY"]:
        j_file = tmp_path / f"wal_crash_{crash_phase}.log"
        j = DurableEventJournal(j_file)
        payload = {"event_id": f"evt_crash_{crash_phase}"}

        if crash_phase == "PREPARED":
            j.prepare_event(payload)
        elif crash_phase == "CAPTURED_OFFSET":
            j.prepare_event(payload)
            j.capture_offset()
        elif crash_phase == "WRITTEN":
            j.prepare_event(payload)
            j.capture_offset()
            j.write_to_disk()
        elif crash_phase == "FLUSHED":
            j.prepare_event(payload)
            j.capture_offset()
            j.write_to_disk()
            j.flush_buffer()
        elif crash_phase == "FSYNCED":
            j.prepare_event(payload)
            j.capture_offset()
            j.write_to_disk()
            j.flush_buffer()
            j.fsync_to_disk()
        elif crash_phase == "PUBLISHED_MEMORY":
            j.prepare_event(payload)
            j.capture_offset()
            j.write_to_disk()
            j.flush_buffer()
            j.fsync_to_disk()
            j.publish_to_memory()

        # Simulate crash / abrupt exit before commit()
        j.close()

        # Recovery verification
        rec = DurableEventJournal(j_file)
        assert len(rec.get_committed_events()) == 0, f"Failed: uncommitted event replayed for crash at phase {crash_phase}"
        rec.close()
