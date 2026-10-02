"""Unit tests for SQLiteIntentRepository process-restart survival, concurrency, and Decimal exactness."""

from decimal import Decimal
from pathlib import Path
import pytest

from gyroscope.contracts.types import DecisionSide, ExecutionIntent, OrderType
from gyroscope.execution.repository import SQLiteIntentRepository


def test_sqlite_intent_repository_restart_survival(tmp_path: Path):
    """Verify committed ExecutionIntents survive process/database restart and maintain exact Decimal precision."""
    db_file = tmp_path / "intents.db"

    # Process 1: Open repository and save intent
    repo1 = SQLiteIntentRepository(db_file)
    intent1 = ExecutionIntent(
        intent_id="intent_100",
        idempotency_key="idem_100",
        request_fingerprint="fp_100",
        authorization_id="auth_100",
        symbol="BTC-USD",
        side=DecisionSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1.23456789"),
        limit_price=Decimal("50000.12345678"),
        stop_price=None,
        configuration_hash="cfg_100",
        lineage_node_id="node_100",
        created_at_ns=1000,
    )
    repo1.save_intent(intent1)

    # Process 2: Open fresh repository connection on same file
    repo2 = SQLiteIntentRepository(db_file)
    recovered = repo2.get_by_intent_id("intent_100")

    assert recovered is not None
    assert recovered.intent_id == "intent_100"
    assert recovered.idempotency_key == "idem_100"
    assert recovered.quantity == Decimal("1.23456789")
    assert recovered.limit_price == Decimal("50000.12345678")
    assert isinstance(recovered.quantity, Decimal)


def test_sqlite_intent_repository_conflicting_fingerprint_rejection(tmp_path: Path):
    """Verify same idempotency key with conflicting fingerprint raises ValueError."""
    repo = SQLiteIntentRepository(tmp_path / "intents.db")

    intent = ExecutionIntent(
        intent_id="intent_1",
        idempotency_key="idem_key_1",
        request_fingerprint="fp_original",
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
    repo.save_intent(intent)

    conflicting_intent = ExecutionIntent(
        intent_id="intent_2",
        idempotency_key="idem_key_1",  # Same idempotency key
        request_fingerprint="fp_TAMPERED",  # Different fingerprint!
        authorization_id="auth_1",
        symbol="BTC-USD",
        side=DecisionSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("2.00000000"),
        limit_price=Decimal("50000.00000000"),
        stop_price=None,
        configuration_hash="cfg_1",
        lineage_node_id="node_1",
        created_at_ns=1000,
    )

    with pytest.raises(ValueError, match="Conflicting intent under same idempotency key"):
        repo.save_intent(conflicting_intent)
