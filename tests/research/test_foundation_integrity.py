"""Foundation Integrity Test suite validating Gyroscope architectural invariants."""

from pathlib import Path
import subprocess
import pytest

import gyroscope
from gyroscope.config import SystemConfig
from gyroscope.core.exceptions import AuthorityViolationError
from gyroscope.core.types import ReadinessLevel
from gyroscope.observation import Observation
from gyroscope.state import Event, SystemState, deserialize_state, serialize_state


def test_foundation_package_structure():
    """Verify that required package directories and core files exist on disk."""
    root = Path(__file__).parent.parent.parent
    required_paths = [
        root / "gyroscope" / "core",
        root / "gyroscope" / "config",
        root / "gyroscope" / "observation",
        root / "gyroscope" / "state",
        root / "gyroscope" / "provenance",
        root / "gyroscope" / "logging",
        root / "constitution" / "GYROSCOPE_CONSTITUTION_v1.0.md",
        root / "docs" / "GYROSCOPE_BASELINE.md",
        root / "docs" / "FOUNDATION_MANIFEST_v1.0.md",
        root / "docs" / "architecture" / "GYROSCOPE_ARCHITECTURE_v1.0.md",
    ]
    for path in required_paths:
        assert path.exists(), f"Missing required foundation path: {path}"


def test_configuration_determinism_invariant():
    """Verify that configuration hashing is bit-for-bit deterministic."""
    c1 = SystemConfig(symbol="BTC-USD", readiness_level=ReadinessLevel.R3)
    c2 = SystemConfig(symbol="BTC-USD", readiness_level=ReadinessLevel.R3)
    assert c1.compute_config_hash() == c2.compute_config_hash()


def test_research_execution_boundary_invariant():
    """Verify that R0, R1, R2, and R3 readiness levels cannot enter live execution."""
    for rl in [ReadinessLevel.R0, ReadinessLevel.R1, ReadinessLevel.R2, ReadinessLevel.R3]:
        assert not rl.is_production_executable
    assert ReadinessLevel.R4.is_production_executable


def test_provenance_documentation_agrees_with_git():
    """Verify that documented manifest and baseline commit SHAs agree with actual Git repository history."""
    root = Path(__file__).parent.parent.parent

    # Run git commands locally to extract topology
    try:
        git_root = subprocess.check_output(
            ["git", "rev-list", "--max-parents=0", "HEAD"], cwd=root, text=True
        ).strip().splitlines()[0]
        git_parent = subprocess.check_output(
            ["git", "rev-parse", "HEAD^"], cwd=root, text=True
        ).strip()
        git_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
    except Exception as exc:
        pytest.skip(f"Git command failed in environment: {exc}")

    manifest_path = root / "docs" / "FOUNDATION_MANIFEST_v1.0.md"
    baseline_path = root / "docs" / "GYROSCOPE_BASELINE.md"

    manifest_text = manifest_path.read_text(encoding="utf-8")
    baseline_text = baseline_path.read_text(encoding="utf-8")

    # The documented root SHA must match actual Git root SHA
    assert f"root_commit_sha: {git_root}" in manifest_text, (
        f"Manifest root_commit_sha does not match Git root SHA: {git_root}"
    )
    assert f"- **Root Commit SHA:** `{git_root}`" in baseline_text, (
        f"Baseline Root Commit SHA does not match Git root SHA: {git_root}"
    )

    # In closure state (or when checking history), parent SHA matches git_parent
    assert f"parent_commit_sha: {git_parent}" in manifest_text, (
        f"Manifest parent_commit_sha does not match Git parent SHA: {git_parent}"
    )
    assert f"- **Parent Commit SHA:** `{git_parent}`" in baseline_text, (
        f"Baseline Parent Commit SHA does not match Git parent SHA: {git_parent}"
    )

    # Ensure stale commit 19813f4d9455027bfa6d42acb56fc32aa133d5c6 is nowhere in documentation
    assert "19813f4d9455027bfa6d42acb56fc32aa133d5c6" not in manifest_text
    assert "19813f4d9455027bfa6d42acb56fc32aa133d5c6" not in baseline_text


def test_state_event_processing_and_hash_stability():
    """Verify state hash evolution and duplicate event suppression."""
    state = SystemState(symbol="ETH-USD")
    initial_hash = state.compute_state_hash()

    evt = Event(event_id="evt_1", event_type="TICK", event_timestamp_ns=1000, payload={"price": 3000.0})
    processed = state.process_event(evt)
    post_hash = state.compute_state_hash()

    assert processed is True
    assert initial_hash != post_hash

    # Duplicate re-processing must be suppressed and produce identical state hash
    duplicate_processed = state.process_event(evt)
    assert duplicate_processed is False
    assert state.compute_state_hash() == post_hash
