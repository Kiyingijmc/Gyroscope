"""Deterministic, hashable configuration foundation."""

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Dict

from gyroscope.core.types import ReadinessLevel


@dataclass(frozen=True)
class SystemConfig:
    """Explicit, serializable, hashable, versioned system configuration."""
    config_version: str = "1.0.0"
    environment: str = "development"
    strategy_version: str = "1.0.0"
    model_version: str = "1.0.0"
    feature_version: str = "1.0.0"
    risk_version: str = "1.0.0"
    execution_version: str = "1.0.0"
    readiness_level: ReadinessLevel = ReadinessLevel.R3
    symbol: str = "BTC-USD"
    timeframe: str = "1m"
    max_drawdown_pct: float = 0.05
    max_position_size: float = 1.0
    custom_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to JSON-serializable dictionary."""
        d = asdict(self)
        d["readiness_level"] = self.readiness_level.value
        return d

    def compute_config_hash(self) -> str:
        """Calculate canonical SHA-256 hash of configuration."""
        d = self.to_dict()
        canonical_str = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemConfig":
        """Reconstruct SystemConfig from dictionary."""
        data_copy = dict(data)
        if "readiness_level" in data_copy and isinstance(data_copy["readiness_level"], str):
            data_copy["readiness_level"] = ReadinessLevel(data_copy["readiness_level"])
        return cls(**data_copy)
