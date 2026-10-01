"""Protocol and model abstractions for Phase 2 State Estimation boundary."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple


@dataclass(frozen=True)
class StateEstimate:
    """Canonical estimate of latent state with explicit uncertainty and provenance references.

    Preserves separation between observation, inference, and evidence.
    """
    estimate_id: str
    timestamp_ns: int
    symbol: str
    timeframe: str
    state_vector: List[float]
    covariance_matrix: List[List[float]]
    confidence: float
    innovation: Optional[List[float]] = None
    innovation_covariance: Optional[List[List[float]]] = None
    estimator_version: str = "1.0.0"
    observation_ids: List[str] = field(default_factory=list)
    prior_state_hash: str = ""
    resulting_state_hash: str = ""
    provenance_node_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class StateEstimator(Protocol):
    """Protocol contract for latent state estimators (e.g. Kalman filters, PEF)."""

    def estimate(
        self,
        observation: Any,
        prior_state: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> StateEstimate:
        """Produce a state estimate from an observation and prior state."""
        ...
