"""Unit tests for SystemConfig hashing and serialization."""

from gyroscope.config.settings import SystemConfig
from gyroscope.core.types import ReadinessLevel


def test_system_config_hash_stability():
    cfg1 = SystemConfig(symbol="BTC-USD", readiness_level=ReadinessLevel.R3, custom_params={"a": 1, "b": 2})
    cfg2 = SystemConfig(symbol="BTC-USD", readiness_level=ReadinessLevel.R3, custom_params={"b": 2, "a": 1})

    assert cfg1.compute_config_hash() == cfg2.compute_config_hash()


def test_system_config_hash_changes_on_parameter_modification():
    cfg1 = SystemConfig(max_drawdown_pct=0.05)
    cfg2 = SystemConfig(max_drawdown_pct=0.10)

    assert cfg1.compute_config_hash() != cfg2.compute_config_hash()


def test_system_config_roundtrip():
    cfg = SystemConfig(symbol="SOL-USD", max_position_size=2.5, readiness_level=ReadinessLevel.R4)
    d = cfg.to_dict()
    restored = SystemConfig.from_dict(d)

    assert restored == cfg
    assert restored.compute_config_hash() == cfg.compute_config_hash()
