"""Unit tests for concurrent intent persistence safety and SQLite uniqueness constraint handling."""

from decimal import Decimal
from pathlib import Path
import threading
import pytest

from gyroscope.contracts.types import DecisionSide, ExecutionIntent, OrderType
from gyroscope.execution.repository import SQLiteIntentRepository


def test_sqlite_intent_repository_concurrency_race_handling(tmp_path: Path):
    """Verify that concurrent threads attempting to save identical or conflicting intents are handled safely and deterministically."""
    db_file = tmp_path / "concurrent_intents.db"
    repo = SQLiteIntentRepository(db_file)

    intent = ExecutionIntent(
        intent_id="intent_race_1",
        idempotency_key="idem_race_1",
        request_fingerprint="fp_race_1",
        authorization_id="auth_1",
        symbol="BTC-USD",
        side=DecisionSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1.00000000"),
        limit_price=Decimal("50000.00000000"),
        stop_price=None,
        configuration_hash="cfg_1",
        lineage_node_id="node_1",
        created_at_ns=1000,
    )

    errors = []

    def worker():
        try:
            repo.save_intent(intent)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # No unhandled sqlite3.IntegrityError or crash
    assert len(errors) == 0
    assert repo.exists("intent_race_1") is True
