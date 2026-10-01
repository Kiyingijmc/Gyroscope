"""Deterministic simulation of external broker execution boundary supporting MARKET, LIMIT, STOP, STOP-LIMIT order execution, partial fills, rejections, and UNKNOWN state."""

from decimal import Decimal
import hashlib
from typing import Dict, List, Optional, Tuple

from gyroscope.contracts.ports import BrokerAdapterPort
from gyroscope.contracts.types import (
    BrokerDeal,
    BrokerOrderRecord,
    DecisionSide,
    ExecutionIntent,
    OrderStatus,
    OrderType,
)
from gyroscope.core.numeric import assert_exact_financial_quantity, to_authoritative_decimal


class DeterministicBrokerSimulator(BrokerAdapterPort):
    """Deterministic broker simulator supporting partial fills, multiple fills, overfill prevention, and deduplication."""

    def __init__(self, simulate_unknown: bool = False, simulate_rejection: bool = False) -> None:
        self.simulate_unknown = simulate_unknown
        self.simulate_rejection = simulate_rejection
        self._orders_by_broker_id: Dict[str, BrokerOrderRecord] = {}
        self._broker_id_by_intent_id: Dict[str, str] = {}
        self._deals_by_broker_id: Dict[str, List[BrokerDeal]] = {}

    def submit_intent(self, intent: ExecutionIntent) -> BrokerOrderRecord:
        """Submit intent to broker boundary and receive deterministic order record."""
        if intent.intent_id in self._broker_id_by_intent_id:
            b_id = self._broker_id_by_intent_id[intent.intent_id]
            return self._orders_by_broker_id[b_id]

        broker_order_id = f"ord_sim_{hashlib.sha256(intent.intent_id.encode()).hexdigest()[:16]}"
        self._broker_id_by_intent_id[intent.intent_id] = broker_order_id
        self._deals_by_broker_id[broker_order_id] = []

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
            # Generate full deal
            deal_id = f"deal_{hashlib.sha256(f'{broker_order_id}:1'.encode()).hexdigest()[:16]}"
            self._deals_by_broker_id[broker_order_id].append(
                BrokerDeal(
                    deal_id=deal_id,
                    order_id=broker_order_id,
                    intent_id=intent.intent_id,
                    symbol=intent.symbol,
                    side=intent.side,
                    fill_quantity=filled_qty,
                    fill_price=avg_price,
                    fee_amount=Decimal("0.00000000"),
                    fee_currency="USD",
                    executed_at_ns=intent.created_at_ns + 100,
                )
            )

        raw_hash = hashlib.sha256(f"{broker_order_id}:{status.value}:{filled_qty:.8f}".encode()).hexdigest()

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

    def execute_partial_fill(
        self,
        broker_order_id: str,
        fill_quantity: Decimal,
        fill_price: Decimal,
        executed_at_ns: int,
    ) -> Tuple[BrokerOrderRecord, BrokerDeal]:
        """Execute a partial fill against an existing order, maintaining exact invariant: filled_quantity + remaining_quantity == requested_quantity."""
        existing = self._orders_by_broker_id.get(broker_order_id)
        if not existing:
            raise ValueError(f"Unknown broker order ID: {broker_order_id}")

        assert_exact_financial_quantity(fill_quantity)
        assert_exact_financial_quantity(fill_price)

        new_filled_qty = existing.filled_quantity + fill_quantity
        if new_filled_qty > existing.requested_quantity:
            raise ValueError(
                f"Overfill error: new filled quantity ({new_filled_qty}) exceeds requested quantity ({existing.requested_quantity})"
            )

        # Compute weighted average fill price
        deals = self._deals_by_broker_id[broker_order_id]
        total_val = sum((d.fill_quantity * d.fill_price for d in deals), Decimal("0.00000000")) + (fill_quantity * fill_price)
        avg_price = total_val / new_filled_qty

        deal_id = f"deal_{hashlib.sha256(f'{broker_order_id}:{len(deals)+1}'.encode()).hexdigest()[:16]}"
        deal = BrokerDeal(
            deal_id=deal_id,
            order_id=broker_order_id,
            intent_id=existing.intent_id,
            symbol=existing.symbol,
            side=existing.side,
            fill_quantity=fill_quantity,
            fill_price=fill_price,
            fee_amount=Decimal("0.00000000"),
            fee_currency="USD",
            executed_at_ns=executed_at_ns,
        )
        deals.append(deal)

        status = OrderStatus.FILLED if new_filled_qty == existing.requested_quantity else OrderStatus.PARTIALLY_FILLED
        raw_hash = hashlib.sha256(f"{broker_order_id}:{status.value}:{new_filled_qty:.8f}".encode()).hexdigest()

        updated_record = BrokerOrderRecord(
            broker_order_id=existing.broker_order_id,
            intent_id=existing.intent_id,
            idempotency_key=existing.idempotency_key,
            symbol=existing.symbol,
            side=existing.side,
            order_type=existing.order_type,
            status=status,
            requested_quantity=existing.requested_quantity,
            filled_quantity=new_filled_qty,
            avg_fill_price=avg_price,
            last_update_ns=executed_at_ns,
            raw_response_hash=raw_hash,
        )

        self._orders_by_broker_id[broker_order_id] = updated_record
        return updated_record, deal

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

    def get_deals(self, broker_order_id: str) -> List[BrokerDeal]:
        return list(self._deals_by_broker_id.get(broker_order_id, []))
