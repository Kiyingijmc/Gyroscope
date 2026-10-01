"""Interface specifications (ports) for all integration domain boundaries."""

from typing import Any, Dict, List, Optional, Protocol, Tuple

from gyroscope.contracts.types import (
    AuthorityDomain,
    BrokerDeal,
    BrokerOrderRecord,
    CandidateDecision,
    ExecutionIntent,
    OrderType,
    ReconciliationEvidence,
    RecoveryEvidence,
    RecoveryState,
    ResearchEvidencePayload,
    RiskAuthorization,
    SemanticObservationRef,
)


class ObservationPort(Protocol):
    """Port for mapping Gyroscope Observations into semantic content identities."""

    def extract_semantic_ref(self, raw_observation: Any) -> SemanticObservationRef:
        ...


class StatePort(Protocol):
    """Port for read-only projection of deterministic state to downstream logic."""

    def get_latest_sequence_number(self) -> int:
        ...

    def get_state_payload_hash(self) -> str:
        ...

    def get_state_hash(self) -> str:
        ...

    def get_snapshot_hash(self) -> str:
        ...


class StrategyDecisionPort(Protocol):
    """Port for strategy decision proposal (no direct execution authority)."""

    def evaluate_opportunity(
        self,
        observation_ref: SemanticObservationRef,
        evidence: Optional[ResearchEvidencePayload],
        state_projection: StatePort,
    ) -> Optional[CandidateDecision]:
        ...


class EvidencePort(Protocol):
    """Port for generating research and state estimation evidence."""

    def generate_evidence(
        self,
        observation_ref: SemanticObservationRef,
        state_projection: StatePort,
    ) -> ResearchEvidencePayload:
        ...


class RiskAuthorityPort(Protocol):
    """Port for evaluating strategy proposals against exact Decimal risk boundaries."""

    def evaluate_candidate_decision(
        self,
        candidate: CandidateDecision,
        state_projection: StatePort,
    ) -> RiskAuthorization:
        ...


class ExecutionIntentPort(Protocol):
    """Port for constructing durable, risk-authorized ExecutionIntents."""

    def build_intent(
        self,
        authorization: RiskAuthorization,
        candidate: CandidateDecision,
        configuration_hash: str,
    ) -> ExecutionIntent:
        ...


class IntentRepositoryPort(Protocol):
    """Port for durable persistence and duplicate suppression of ExecutionIntents."""

    def save_intent(self, intent: ExecutionIntent) -> None:
        ...

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ExecutionIntent]:
        ...

    def get_by_intent_id(self, intent_id: str) -> Optional[ExecutionIntent]:
        ...

    def list_pending_intents(self) -> List[ExecutionIntent]:
        ...


class BrokerAdapterPort(Protocol):
    """Port for broker boundary interaction."""

    def submit_intent(self, intent: ExecutionIntent) -> BrokerOrderRecord:
        ...

    def cancel_order(self, broker_order_id: str, intent_id: str) -> BrokerOrderRecord:
        ...

    def query_order(self, broker_order_id: str) -> Optional[BrokerOrderRecord]:
        ...


class BrokerObservationPort(Protocol):
    """Port for capturing broker deals and converting them into authoritative observations."""

    def record_deal(self, deal: BrokerDeal) -> SemanticObservationRef:
        ...


class ReconciliationPort(Protocol):
    """Port for broker state reconciliation and UNKNOWN state resolution."""

    def reconcile_broker_state(
        self,
        active_intents: List[ExecutionIntent],
        fresh_broker_orders: List[BrokerOrderRecord],
    ) -> ReconciliationEvidence:
        ...


class ProvenancePort(Protocol):
    """Port for logging lineage nodes in the single authoritative provenance DAG."""

    def record_node(
        self,
        authority: AuthorityDomain,
        payload: Dict[str, Any],
        parent_node_ids: Tuple[str, ...],
    ) -> str:
        ...


class RecoveryPort(Protocol):
    """Port for managing system recovery lifecycle and gating production execution."""

    def evaluate_recovery_status(
        self,
        reconciliation_evidence: ReconciliationEvidence,
    ) -> RecoveryEvidence:
        ...
