"""Adapters package establishing ports & adapters layer."""

from gyroscope.adapters.observation import (
    ObservationAdapter,
    compute_semantic_observation_identity,
)

__all__ = [
    "ObservationAdapter",
    "compute_semantic_observation_identity",
]
