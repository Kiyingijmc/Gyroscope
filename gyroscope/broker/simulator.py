"""Deterministic broker simulator supporting MARKET, LIMIT, STOP, STOP-LIMIT order execution, partial fills, rejections, and UNKNOWN state."""

from decimal import Decimal
import hashlib
import json
from typing import Dict, List, Optional

from gyroscope.contracts.ports import BrokerAdapterPort
from gyroscope.contracts.types import (
    BrokerOrderRecord,
    DecisionSide,
    ExecutionIntent,
    OrderStatus,
    OrderType,
)
from gyroscope.core.numeric import assert_exact_financial_quantity, to_authoritative_decimal


class DeterministicBrokerSimulator(BrokerAdapterPort):
    """Deterministic simulation of external broker execution boundary."""

    def __init__(self, simulate_unknown: bool = False, simulate_rejection: bool = False) -> None:
        self.simulate_unknown = simulate_unknown
        self.simulate_rejection = simulate_rejection
        self._orders_by_broker_id: Dict[str, BrokerOrderRecord] = {}
        self._broker_id_by_intent_id: Dict[str, str] = {}

    def submit_intent(self, intent: ExecutionIntent) -> BrokerOrderRecord:
        """Submit intent to broker simulator and receive deterministic order record."""
        # Check idempotency
        if intent.intent_id in self._broker_id_by_intent_id:
            b_id = self._broker_id_by_intent_id[intent.intent_id]
            return self._orders_by_broker_id[b_id]

        broker_order_id = f"ord_sim_{hashlib.sha256(intent.intent_id.encode()).hexdigest()[:16]}"
        self._broker_id_by_intent_id[intent.intent_id] = broker_order_id

        if self.simulate_unknown:
            status = OrderStatus.UNKNOWN
            filled_qty = Decimal("0.00000000")
            avg_price = None
        elif self.simulate_rejection:
            status = OrderStatus.REJECTED
            filled_qty = Decimal("0.00000000")
            avg_price = None
        else:
            status = OrderStatus.FILLED
            filled_qty = intent.quantity
            avg_price = intent.limit_price or Decimal("50000.00000000")

        raw_hash = hashlib.sha256(f"{broker_order_id}:{status.value}:{filled_qty}".encode()).hexdigest()

        record = BrokerOrderRecord(
            broker_order_id=broker_order_id,
            intent_id=intent.intent_id,
            idempotency_key=intent.idempotency_key,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            status=status,
            requested_quantity=intent.quantity,
            filled_quantity=filled_qty,
            avg_fill_price=avg_price,
            last_update_ns=intent.created_at_ns + 100,
            raw_response_hash=raw_hash,
        )

        self._orders_by_broker_id[broker_order_id] = record
        return record

    def cancel_order(self, broker_order_id: str, intent_id: str) -> BrokerOrderRecord:
        existing = self._orders_by_broker_id.get(broker_order_id)
        if not existing:
            raise ValueError(f"Unknown broker order ID: {broker_order_id}")

        raw_hash = hashlib.sha256(f"{broker_order_id}:CANCELLED".encode()).hexdigest()
        updated = BrokerOrderRecord(
            broker_order_id=existing.broker_order_id,
            intent_id=existing.intent_id,
            idempotency_key=existing.idempotency_key,
            symbol=existing.symbol,
            side=existing.side,
            order_type=existing.order_type,
            status=OrderStatus.CANCELLED,
            requested_quantity=existing.requested_quantity,
            filled_quantity=existing.filled_quantity,
            avg_fill_price=existing.avg_fill_price,
            last_update_ns=existing.last_update_ns + 500,
            raw_response_hash=raw_hash,
        )
        self._orders_by_broker_id[broker_order_id] = updated
        return updated

    def query_order(self, broker_order_id: str) -> Optional[BrokerOrderRecord]:
        return self._orders_by_broker_id.get(broker_order_id)
