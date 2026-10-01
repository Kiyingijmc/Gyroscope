"""Execution intent building and durable persistence with stable idempotency keys, fingerprinting, and duplicate suppression."""

from decimal import Decimal
import hashlib
import json
from typing import Dict, List, Optional

from gyroscope.contracts.ports import ExecutionIntentPort, IntentRepositoryPort
from gyroscope.contracts.types import (
    CandidateDecision,
    ExecutionIntent,
    RiskAuthorization,
)
from gyroscope.core.exceptions import AuthorityViolationError


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

        # Compute stable idempotency key and request fingerprint
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


class InMemoryIntentRepository(IntentRepositoryPort):
    """In-memory durable intent repository with duplicate suppression and fingerprint validation."""

    def __init__(self) -> None:
        self._intents_by_id: Dict[str, ExecutionIntent] = {}
        self._intents_by_idem_key: Dict[str, ExecutionIntent] = {}

    def save_intent(self, intent: ExecutionIntent) -> None:
        existing = self._intents_by_idem_key.get(intent.idempotency_key)
        if existing:
            if existing.request_fingerprint != intent.request_fingerprint:
                raise ValueError(
                    f"Conflicting intent under same idempotency key '{intent.idempotency_key}': "
                    f"existing fingerprint {existing.request_fingerprint} != new fingerprint {intent.request_fingerprint}"
                )
            return  # Duplicate submission suppressed idempotently

        self._intents_by_id[intent.intent_id] = intent
        self._intents_by_idem_key[intent.idempotency_key] = intent

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ExecutionIntent]:
        return self._intents_by_idem_key.get(idempotency_key)

    def get_by_intent_id(self, intent_id: str) -> Optional[ExecutionIntent]:
        return self._intents_by_id.get(intent_id)

    def list_pending_intents(self) -> List[ExecutionIntent]:
        return list(self._intents_by_id.values())
