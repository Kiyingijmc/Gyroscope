"""Durable SQLite fill/deal repository providing process-restart fill persistence and duplicate external execution deduplication."""

from decimal import Decimal
import json
from pathlib import Path
import sqlite3
from typing import List, Optional, Tuple, Union

from gyroscope.contracts.types import BrokerDeal, DecisionSide
from gyroscope.core.numeric import assert_exact_financial_quantity, to_authoritative_decimal


class SQLiteFillRepository:
    """Durable SQLite-backed fill/deal repository for external broker execution records."""

    def __init__(self, db_path: Union[str, Path] = ":memory:") -> None:
        self.db_path = str(db_path)
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS broker_deals (
                    broker_id TEXT NOT NULL,
                    external_execution_id TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    fill_quantity TEXT NOT NULL,
                    fill_price TEXT NOT NULL,
                    fee_amount TEXT NOT NULL,
                    fee_currency TEXT NOT NULL,
                    executed_at_ns INTEGER NOT NULL,
                    PRIMARY KEY (broker_id, external_execution_id)
                );
                """
            )
            conn.commit()

    def save_deal(self, broker_id: str, deal: BrokerDeal) -> None:
        """Save a broker deal durably, enforcing idempotent deduplication on (broker_id, external_execution_id)."""
        existing = self.get_deal(broker_id, deal.deal_id)
        if existing:
            if (
                existing.fill_quantity != deal.fill_quantity
                or existing.fill_price != deal.fill_price
                or existing.symbol != deal.symbol
                or existing.side != deal.side
                or existing.order_id != deal.order_id
            ):
                raise ValueError(
                    f"Conflicting external fill received for ({broker_id}, {deal.deal_id}): "
                    f"existing ({existing.fill_quantity} @ {existing.fill_price}) != new ({deal.fill_quantity} @ {deal.fill_price})"
                )
            return  # Idempotent duplicate delivery

        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO broker_deals (
                        broker_id, external_execution_id, order_id, intent_id, symbol,
                        side, fill_quantity, fill_price, fee_amount, fee_currency, executed_at_ns
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        broker_id,
                        deal.deal_id,
                        deal.order_id,
                        deal.intent_id,
                        deal.symbol,
                        deal.side.value,
                        f"{deal.fill_quantity:.8f}",
                        f"{deal.fill_price:.8f}",
                        f"{deal.fee_amount:.8f}",
                        deal.fee_currency,
                        deal.executed_at_ns,
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError:
            existing_after_race = self.get_deal(broker_id, deal.deal_id)
            if existing_after_race:
                if (
                    existing_after_race.fill_quantity != deal.fill_quantity
                    or existing_after_race.fill_price != deal.fill_price
                ):
                    raise ValueError(
                        f"Conflicting external fill received for ({broker_id}, {deal.deal_id}): "
                        f"existing ({existing_after_race.fill_quantity} @ {existing_after_race.fill_price}) != new ({deal.fill_quantity} @ {deal.fill_price})"
                    )
                return
            raise

    def _row_to_deal(self, row: sqlite3.Row) -> BrokerDeal:
        return BrokerDeal(
            deal_id=row["external_execution_id"],
            order_id=row["order_id"],
            intent_id=row["intent_id"],
            symbol=row["symbol"],
            side=DecisionSide(row["side"]),
            fill_quantity=to_authoritative_decimal(row["fill_quantity"]),
            fill_price=to_authoritative_decimal(row["fill_price"]),
            fee_amount=to_authoritative_decimal(row["fee_amount"]),
            fee_currency=row["fee_currency"],
            executed_at_ns=row["executed_at_ns"],
        )

    def get_deal(self, broker_id: str, external_execution_id: str) -> Optional[BrokerDeal]:
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM broker_deals WHERE broker_id = ? AND external_execution_id = ?",
                (broker_id, external_execution_id),
            )
            row = cur.fetchone()
            return self._row_to_deal(row) if row else None

    def get_deals_for_order(self, order_id: str) -> List[BrokerDeal]:
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM broker_deals WHERE order_id = ? ORDER BY executed_at_ns ASC, external_execution_id ASC",
                (order_id,),
            )
            rows = cur.fetchall()
            return [self._row_to_deal(r) for r in rows]

    def get_deals_for_intent(self, intent_id: str) -> List[BrokerDeal]:
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM broker_deals WHERE intent_id = ? ORDER BY executed_at_ns ASC, external_execution_id ASC",
                (intent_id,),
            )
            rows = cur.fetchall()
            return [self._row_to_intent_row(r) for r in rows]

    def _row_to_intent_row(self, row: sqlite3.Row) -> BrokerDeal:
        return self._row_to_deal(row)

    def compute_ledger_hash(self) -> str:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM broker_deals ORDER BY broker_id ASC, external_execution_id ASC")
            rows = cur.fetchall()
            canonical_records = []
            for r in rows:
                canonical_records.append(
                    {
                        "broker_id": r["broker_id"],
                        "external_execution_id": r["external_execution_id"],
                        "fill_price": r["fill_price"],
                        "fill_quantity": r["fill_quantity"],
                        "intent_id": r["intent_id"],
                        "order_id": r["order_id"],
                        "side": r["side"],
                        "symbol": r["symbol"],
                    }
                )
            canonical_json = json.dumps(canonical_records, sort_keys=True, separators=(",", ":"))
            import hashlib

            return f"fill_hash_{hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()[:32]}"
