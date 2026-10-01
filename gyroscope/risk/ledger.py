"""Opportunity Risk Ledger evaluating candidate proposals against exact Decimal financial, directional exposure, and risk boundaries with WAL event replay reconstruction."""

from decimal import Decimal
import hashlib
import json
from typing import Any, Dict, List, Optional, Union

from gyroscope.contracts.ports import RiskAuthorityPort, StatePort
from gyroscope.contracts.types import (
    CandidateDecision,
    DecisionSide,
    RiskAuthorization,
    RiskDecisionType,
)
from gyroscope.core.exceptions import AuthorityViolationError
from gyroscope.core.numeric import assert_exact_financial_quantity, to_authoritative_decimal


class OpportunityRiskLedger(RiskAuthorityPort):
    """Exact financial risk authority with directional BUY (+Q) / SELL (-Q) net position exposure accounting and WAL event reconstruction."""

    def __init__(
        self,
        max_position_limit: Decimal = Decimal("10.00000000"),
        max_notional_value: Decimal = Decimal("1000000.00000000"),
        max_slippage_bps: Decimal = Decimal("10.00000000"),
    ) -> None:
        self.max_position_limit = assert_exact_financial_quantity(max_position_limit)
        self.max_notional_value = assert_exact_financial_quantity(max_notional_value)
        self.max_slippage_bps = assert_exact_financial_quantity(max_slippage_bps)
        self._current_exposure: Dict[str, Decimal] = {}

    def get_exposure(self, symbol: str) -> Decimal:
        return self._current_exposure.get(symbol, Decimal("0.00000000"))

    def compute_ledger_state_hash(self) -> str:
        state_dict = {
            "exposure": {sym: f"{val:.8f}" for sym, val in sorted(self._current_exposure.items())},
            "max_notional_value": f"{self.max_notional_value:.8f}",
            "max_position_limit": f"{self.max_position_limit:.8f}",
            "max_slippage_bps": f"{self.max_slippage_bps:.8f}",
        }
        canonical_json = json.dumps(state_dict, sort_keys=True, separators=(",", ":"))
        return f"rsk_{hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()[:32]}"

    def apply_risk_event(self, event_dict: Dict[str, Union[str, float]]) -> None:
        """Deterministically apply/reconstruct a risk event record."""
        event_type = event_dict.get("event_type")
        if event_type == "RISK_AUTHORIZATION_GRANTED":
            symbol = str(event_dict["symbol"])
            side = str(event_dict["side"])
            qty = to_authoritative_decimal(event_dict["approved_quantity"])
            delta_qty = qty if side == DecisionSide.BUY.value else -qty
            curr_exp = self.get_exposure(symbol)
            self._current_exposure[symbol] = curr_exp + delta_qty

    def reconstruct_from_events(self, events: List[Dict[str, Any]]) -> None:
        """Reconstruct risk exposure state deterministically from an authoritative event sequence."""
        self._current_exposure.clear()
        for evt in events:
            self.apply_risk_event(evt)

    def evaluate_candidate_decision(
        self,
        candidate: CandidateDecision,
        state_projection: StatePort,
    ) -> RiskAuthorization:
        """Evaluate a candidate proposal against exact risk boundaries with directional exposure accounting."""
        symbol = candidate.symbol
        curr_exp = self.get_exposure(symbol)

        delta_qty = candidate.target_quantity if candidate.side == DecisionSide.BUY else -candidate.target_quantity
        new_exp = curr_exp + delta_qty

        price = candidate.limit_price or Decimal("1.00000000")
        notional = candidate.target_quantity * price

        eval_ns = candidate.decision_timestamp_ns
        auth_bytes = f"{candidate.decision_id}:{eval_ns}:{self.compute_ledger_state_hash()}".encode("utf-8")
        auth_id = f"auth_{hashlib.sha256(auth_bytes).hexdigest()[:16]}"

        if abs(new_exp) > self.max_position_limit:
            if candidate.side == DecisionSide.BUY:
                allowed_qty = max(Decimal("0.00000000"), self.max_position_limit - curr_exp)
            else:
                allowed_qty = max(Decimal("0.00000000"), self.max_position_limit + curr_exp)

            if allowed_qty > Decimal("0.00000000"):
                return RiskAuthorization(
                    authorization_id=auth_id,
                    candidate_decision_id=candidate.decision_id,
                    decision_type=RiskDecisionType.REDUCE,
                    approved_quantity=allowed_qty,
                    approved_limit_price=candidate.limit_price,
                    approved_stop_price=candidate.stop_price,
                    max_slippage_bps=self.max_slippage_bps,
                    risk_budget_consumed=allowed_qty * price,
                    reason=f"Directional quantity reduced from {candidate.target_quantity} to {allowed_qty} due to limit {self.max_position_limit}",
                    evaluated_at_ns=eval_ns,
                    risk_ledger_state_hash=self.compute_ledger_state_hash(),
                    provenance_node_id=candidate.provenance_node_id,
                )
            else:
                return RiskAuthorization(
                    authorization_id=auth_id,
                    candidate_decision_id=candidate.decision_id,
                    decision_type=RiskDecisionType.REJECT,
                    approved_quantity=Decimal("0.00000000"),
                    approved_limit_price=None,
                    approved_stop_price=None,
                    max_slippage_bps=Decimal("0.00000000"),
                    risk_budget_consumed=Decimal("0.00000000"),
                    reason="Position limit reached",
                    evaluated_at_ns=eval_ns,
                    risk_ledger_state_hash=self.compute_ledger_state_hash(),
                    provenance_node_id=candidate.provenance_node_id,
                )

        if notional > self.max_notional_value:
            return RiskAuthorization(
                authorization_id=auth_id,
                candidate_decision_id=candidate.decision_id,
                decision_type=RiskDecisionType.REJECT,
                approved_quantity=Decimal("0.00000000"),
                approved_limit_price=None,
                approved_stop_price=None,
                max_slippage_bps=Decimal("0.00000000"),
                risk_budget_consumed=Decimal("0.00000000"),
                reason="Max notional value exceeded",
                evaluated_at_ns=eval_ns,
                risk_ledger_state_hash=self.compute_ledger_state_hash(),
                provenance_node_id=candidate.provenance_node_id,
            )

        # Accept & apply exposure update
        self._current_exposure[symbol] = new_exp
        return RiskAuthorization(
            authorization_id=auth_id,
            candidate_decision_id=candidate.decision_id,
            decision_type=RiskDecisionType.ACCEPT,
            approved_quantity=candidate.target_quantity,
            approved_limit_price=candidate.limit_price,
            approved_stop_price=candidate.stop_price,
            max_slippage_bps=self.max_slippage_bps,
            risk_budget_consumed=notional,
            reason="Approved within exact risk limits",
            evaluated_at_ns=eval_ns,
            risk_ledger_state_hash=self.compute_ledger_state_hash(),
            provenance_node_id=candidate.provenance_node_id,
        )
