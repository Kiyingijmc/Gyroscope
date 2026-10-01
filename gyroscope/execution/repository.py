"""Execution intent building and durable SQLite persistence with stable idempotency keys, fingerprinting, and duplicate suppression."""

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Dict, List, Optional, Union

from gyroscope.contracts.ports import ExecutionIntentPort, IntentRepositoryPort
from gyroscope.contracts.types import (
    CandidateDecision,
    DecisionSide,
    ExecutionIntent,
    OrderType,
    RiskAuthorization,
)
from gyroscope.core.exceptions import AuthorityViolationError
from gyroscope.core.numeric import assert_exact_financial_quantity, to_authoritative_decimal


class ExecutionIntentBuilder(ExecutionIntentPort):
    """Constructs durable authorized ExecutionIntents."""

    def build_intent(
        self,
        authorization: RiskAuthorization,
        candidate: CandidateDecision,
        configuration_hash: str,
    ) -> ExecutionIntent:
        """Construct an ExecutionIntent strictly requiring valid risk authorization."""
        if not authorization.is_executable:
            raise AuthorityViolationError(
                f"Cannot build ExecutionIntent for non-executable authorization: {authorization.decision_type.value}"
            )
        if authorization.candidate_decision_id != candidate.decision_id:
            raise AuthorityViolationError(
                f"Authorization candidate ID mismatch: {authorization.candidate_decision_id} != {candidate.decision_id}"
            )

        idempotency_raw = f"{candidate.decision_id}:{authorization.authorization_id}:{configuration_hash}"
        idempotency_key = f"idem_{hashlib.sha256(idempotency_raw.encode('utf-8')).hexdigest()[:32]}"

        fp_dict = {
            "approved_quantity": f"{authorization.approved_quantity:.8f}",
            "candidate_id": candidate.decision_id,
            "configuration_hash": configuration_hash,
            "limit_price": f"{authorization.approved_limit_price:.8f}" if authorization.approved_limit_price else "",
            "side": candidate.side.value,
            "symbol": candidate.symbol,
        }
        fp_json = json.dumps(fp_dict, sort_keys=True, separators=(",", ":"))
        fingerprint = f"fp_{hashlib.sha256(fp_json.encode('utf-8')).hexdigest()[:32]}"

        intent_id = f"intent_{hashlib.sha256(f'{idempotency_key}:{fingerprint}'.encode('utf-8')).hexdigest()[:16]}"

        return ExecutionIntent(
            intent_id=intent_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            authorization_id=authorization.authorization_id,
            symbol=candidate.symbol,
            side=candidate.side,
            order_type=candidate.order_type,
            quantity=authorization.approved_quantity,
            limit_price=authorization.approved_limit_price,
            stop_price=authorization.approved_stop_price,
            configuration_hash=configuration_hash,
            lineage_node_id=authorization.provenance_node_id,
            created_at_ns=authorization.evaluated_at_ns,
        )


class SQLiteIntentRepository(IntentRepositoryPort):
    """Durable SQLite-backed intent repository supporting restart survival, transactional safety, and duplicate suppression."""

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
                CREATE TABLE IF NOT EXISTS execution_intents (
                    intent_id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE NOT NULL,
                    request_fingerprint TEXT NOT NULL,
                    authorization_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    limit_price TEXT,
                    stop_price TEXT,
                    configuration_hash TEXT NOT NULL,
                    lineage_node_id TEXT NOT NULL,
                    created_at_ns INTEGER NOT NULL
                );
                """
            )
            conn.commit()

    def save_intent(self, intent: ExecutionIntent) -> None:
        existing = self.get_by_idempotency_key(intent.idempotency_key)
        if existing:
            if existing.request_fingerprint != intent.request_fingerprint:
                raise ValueError(
                    f"Conflicting intent under same idempotency key '{intent.idempotency_key}': "
                    f"existing fingerprint {existing.request_fingerprint} != new fingerprint {intent.request_fingerprint}"
                )
            return  # Idempotent duplicate suppression

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO execution_intents (
                    intent_id, idempotency_key, request_fingerprint, authorization_id,
                    symbol, side, order_type, quantity, limit_price, stop_price,
                    configuration_hash, lineage_node_id, created_at_ns
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    intent.intent_id,
                    intent.idempotency_key,
                    intent.request_fingerprint,
                    intent.authorization_id,
                    intent.symbol,
                    intent.side.value,
                    intent.order_type.value,
                    f"{intent.quantity:.8f}",
                    f"{intent.limit_price:.8f}" if intent.limit_price is not None else None,
                    f"{intent.stop_price:.8f}" if intent.stop_price is not None else None,
                    intent.configuration_hash,
                    intent.lineage_node_id,
                    intent.created_at_ns,
                ),
            )
            conn.commit()

    def _row_to_intent(self, row: sqlite3.Row) -> ExecutionIntent:
        qty = to_authoritative_decimal(row["quantity"])
        limit_p = to_authoritative_decimal(row["limit_price"]) if row["limit_price"] is not None else None
        stop_p = to_authoritative_decimal(row["stop_price"]) if row["stop_price"] is not None else None

        return ExecutionIntent(
            intent_id=row["intent_id"],
            idempotency_key=row["idempotency_key"],
            request_fingerprint=row["request_fingerprint"],
            authorization_id=row["authorization_id"],
            symbol=row["symbol"],
            side=DecisionSide(row["side"]),
            order_type=OrderType(row["order_type"]),
            quantity=qty,
            limit_price=limit_p,
            stop_price=stop_p,
            configuration_hash=row["configuration_hash"],
            lineage_node_id=row["lineage_node_id"],
            created_at_ns=row["created_at_ns"],
        )

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ExecutionIntent]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM execution_intents WHERE idempotency_key = ?", (idempotency_key,))
            row = cur.fetchone()
            return self._row_to_intent(row) if row else None

    def get_by_intent_id(self, intent_id: str) -> Optional[ExecutionIntent]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM execution_intents WHERE intent_id = ?", (intent_id,))
            row = cur.fetchone()
            return self._row_to_intent(row) if row else None

    def exists(self, intent_id: str) -> bool:
        return self.get_by_intent_id(intent_id) is not None

    def list_pending_intents(self) -> List[ExecutionIntent]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM execution_intents ORDER BY created_at_ns ASC")
            rows = cur.fetchall()
            return [self._row_to_intent(r) for r in rows]


class InMemoryIntentRepository(SQLiteIntentRepository):
    """In-memory SQLite-backed repository maintaining interface compatibility."""

    def __init__(self) -> None:
        super().__init__(db_path=":memory:")
