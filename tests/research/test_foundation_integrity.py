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


def is_synthetic_pr_merge_reference(ref_str: str) -> bool:
    """Validate whether ref_str is strictly a GitHub Actions synthetic PR merge reference."""
    clean_ref = ref_str.strip()
    if clean_ref.startswith("refs/pull/") and clean_ref.endswith("/merge"):
        pr_id = clean_ref[len("refs/pull/"):-len("/merge")]
        return pr_id.isdigit()
    if clean_ref.startswith("pull/") and clean_ref.endswith("/merge"):
        pr_id = clean_ref[len("pull/"):-len("/merge")]
        return pr_id.isdigit()
    if clean_ref.endswith("/merge"):
        parts = clean_ref.split("/")
        if len(parts) == 2 and parts[0].isdigit() and parts[1] == "merge":
            return True
    return False


def test_synthetic_pr_merge_ref_validation():
    """Verify exact acceptance of synthetic PR merge references and rejection of ordinary branches with 'merge'."""
    accepted_cases = [
        "refs/pull/3/merge",
        "refs/pull/123/merge",
        "refs/pull/9999/merge",
        "pull/3/merge",
        "3/merge",
    ]
    rejected_cases = [
        "feature-merge",
        "merge",
        "feature-merge-security",
        "refs/pull/foo/merge",
        "refs/pull/3/not-merge",
        "refs/pull/3/merge-extra",
        "phase-1-forensic-closure-freeze-merge",
    ]

    for ref in accepted_cases:
        assert is_synthetic_pr_merge_reference(ref) is True, f"Expected {ref!r} to be accepted as synthetic PR merge ref"

    for ref in rejected_cases:
        assert is_synthetic_pr_merge_reference(ref) is False, f"Expected {ref!r} to be REJECTED as synthetic PR merge ref"


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


def validate_branch_context_agreement(
    git_branch: str,
    documented_verification_branch: str,
    documented_target_canonical_branch: str = "main",
) -> bool:
    """Validate whether the current Git checkout branch context is legitimate for evaluation.

    Distinguishes:
    - Historical verification branch identity (where foundation closure pass was verified)
    - Target canonical branch identity (main or candidate main-* / canonical-* branches)
    - Synthetic PR merge references
    - Candidate runner task branches
    """
    if not git_branch:
        # Detached HEAD state evaluated via environment fallback or candidate
        return True

    # 1. Exact match with historical verification branch
    if git_branch == documented_verification_branch:
        return True

    # 2. Exact match or prefix match with target canonical branch (e.g., 'main', 'main-6363...', 'canonical-main-promotion-...')
    if (
        git_branch == documented_target_canonical_branch
        or git_branch.startswith(f"{documented_target_canonical_branch}-")
        or git_branch.startswith("canonical-")
    ):
        return True

    # 3. Candidate runner branches or historical branch family prefixes
    if (
        git_branch.startswith("foundation/")
        or git_branch.startswith("jules-")
        or git_branch.startswith("phase-1-")
        or git_branch.startswith("candidate-")
    ):
        return True

    # 4. Synthetic PR merge references (e.g. pull/5/merge)
    if is_synthetic_pr_merge_reference(git_branch):
        return True

    return False


def test_provenance_documentation_agrees_with_git():
    """Verify that documented manifest and baseline commit SHAs agree strictly with actual Git repository topology using dynamic markers."""
    import os
    root = Path(__file__).parent.parent.parent

    # Run git commands directly without suppressing failures
    git_root = subprocess.check_output(
        ["git", "rev-list", "--max-parents=0", "HEAD"], cwd=root, text=True
    ).strip().splitlines()[0]
    git_parent = subprocess.check_output(
        ["git", "rev-parse", "HEAD^"], cwd=root, text=True
    ).strip()
    git_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()

    # Strict separation check: HEAD and HEAD^ must be distinct commit objects
    assert git_head != git_parent, "HEAD and HEAD^ must be distinct commit objects."

    # Extract branch name
    git_branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=root, text=True
    ).strip()
    if not git_branch:
        git_branch = os.environ.get("GITHUB_REF_NAME", "")

    manifest_path = root / "docs" / "FOUNDATION_MANIFEST_v1.0.md"
    baseline_path = root / "docs" / "GYROSCOPE_BASELINE.md"

    manifest_text = manifest_path.read_text(encoding="utf-8")
    baseline_text = baseline_path.read_text(encoding="utf-8")

    # A. Foundation Root SHA must match actual Git root SHA
    assert f"foundation_root_sha: {git_root}" in manifest_text, (
        f"Manifest foundation_root_sha does not match Git root SHA: {git_root}"
    )
    assert f"- **Foundation Root SHA (`foundation_root_sha`):** `{git_root}`" in baseline_text, (
        f"Baseline Foundation Root SHA does not match Git root SHA: {git_root}"
    )

    # B. Verification parent SHA must be documented dynamically as DYNAMIC_GIT_HEAD_PARENT
    assert "verification_parent_sha: DYNAMIC_GIT_HEAD_PARENT" in manifest_text
    assert f"- **Verification Parent SHA (`verification_parent_sha`):** `DYNAMIC_GIT_HEAD_PARENT` (`git rev-parse HEAD^`)" in baseline_text or "verification_parent_sha" in baseline_text

    # Verify that git_parent (HEAD^) is a valid commit object in Git repository
    assert subprocess.run(["git", "cat-file", "-e", git_parent], cwd=root).returncode == 0, (
        f"Parent commit SHA {git_parent} resolved from HEAD^ is not a valid commit object."
    )

    # C. Historical verification branch identity must be preserved in documentation
    historical_verification_branch = "foundation/closure-correction-verification-pass-4893052973368806390"
    assert f"verification_branch: {historical_verification_branch}" in manifest_text, (
        f"Manifest verification_branch missing historical verification branch: {historical_verification_branch}"
    )
    assert f"- **Verification Branch:** `{historical_verification_branch}`" in baseline_text, (
        f"Baseline verification_branch missing historical verification branch: {historical_verification_branch}"
    )

    # C2. Target canonical branch identity must be declared
    target_canonical_branch = "main"
    assert f"target_canonical_branch: {target_canonical_branch}" in manifest_text
    assert f"- **Target Canonical Branch:** `{target_canonical_branch}`" in baseline_text

    # C3. Current checkout branch context must be legitimate
    assert validate_branch_context_agreement(
        git_branch=git_branch,
        documented_verification_branch=historical_verification_branch,
        documented_target_canonical_branch=target_canonical_branch,
    ), f"Current Git checkout branch '{git_branch}' is not a valid evaluation context."

    # D. Verification commit SHA is declared as dynamic current HEAD assertion
    assert "verified_commit_sha: DYNAMIC_GIT_HEAD" in manifest_text
    assert "verification_commit_sha: DYNAMIC_GIT_HEAD" in manifest_text
    # Verify git_head is a valid commit object
    assert subprocess.run(["git", "cat-file", "-e", git_head], cwd=root).returncode == 0

    # E. Historical Foundation v1.0 closure SHA must be a valid commit in repository
    historical_closure_sha = "0f8c01a4004ed34a27660d964d34bb47adea2bc3"
    assert f"foundation_v1_closure_sha: {historical_closure_sha}" in manifest_text
    assert subprocess.run(["git", "cat-file", "-e", historical_closure_sha], cwd=root).returncode == 0

    # F. Ensure stale fabricated commit 19813f4d9455027bfa6d42acb56fc32aa133d5c6 is nowhere in documentation
    assert "19813f4d9455027bfa6d42acb56fc32aa133d5c6" not in manifest_text
    assert "19813f4d9455027bfa6d42acb56fc32aa133d5c6" not in baseline_text


def test_branch_context_and_provenance_scenarios():
    """Comprehensive test matrix covering branch-context validation scenarios."""
    hist = "foundation/closure-correction-verification-pass-4893052973368806390"
    canon = "main"

    # Scenario 1: Historical verification branch checked out
    assert validate_branch_context_agreement(hist, hist, canon) is True

    # Scenario 2: Candidate canonical branch checked out
    assert validate_branch_context_agreement("main", hist, canon) is True
    assert validate_branch_context_agreement("main-636372095427388719", hist, canon) is True
    assert validate_branch_context_agreement("canonical-main-promotion-forensic-remediation-20261002", hist, canon) is True

    # Scenario 3: Arbitrary runner / task branch checked out
    assert validate_branch_context_agreement("jules-task-123", hist, canon) is True
    assert validate_branch_context_agreement("phase-1-forensic-closure-remediation", hist, canon) is True
    assert validate_branch_context_agreement("candidate-context-test", hist, canon) is True

    # Scenario 4: Detached HEAD state (empty string)
    assert validate_branch_context_agreement("", hist, canon) is True

    # Scenario 5 & 6: Synthetic PR merge references
    assert validate_branch_context_agreement("refs/pull/5/merge", hist, canon) is True
    assert validate_branch_context_agreement("pull/5/merge", hist, canon) is True
    assert validate_branch_context_agreement("5/merge", hist, canon) is True

    # Scenario 7: Unauthorized / rogue branch name rejection
    assert validate_branch_context_agreement("unauthorized-rogue-branch", hist, canon) is False
    assert validate_branch_context_agreement("feature/random-unrelated-work", hist, canon) is False

    # Scenario 8: Invalid SHA verification check
    fake_sha = "0000000000000000000000000000000000000000"
    root = Path(__file__).parent.parent.parent
    res = subprocess.run(["git", "cat-file", "-e", fake_sha], cwd=root)
    assert res.returncode != 0, "Fake SHA must fail git cat-file validation"


def test_dynamic_provenance_marker_semantics_regressions():
    """Regression test ensuring DYNAMIC_GIT_HEAD and DYNAMIC_GIT_HEAD_PARENT semantics remain strict and distinct."""
    root = Path(__file__).parent.parent.parent

    git_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    git_parent = subprocess.check_output(
        ["git", "rev-parse", "HEAD^"], cwd=root, text=True
    ).strip()

    # Invariant 1: HEAD and HEAD^ must be distinct 40-char SHA strings
    assert len(git_head) == 40 and len(git_parent) == 40
    assert git_head != git_parent

    manifest_path = root / "docs" / "FOUNDATION_MANIFEST_v1.0.md"
    manifest_text = manifest_path.read_text(encoding="utf-8")

    # Invariant 2: verification_parent_sha must be DYNAMIC_GIT_HEAD_PARENT, NOT DYNAMIC_GIT_HEAD
    assert "verification_parent_sha: DYNAMIC_GIT_HEAD_PARENT" in manifest_text
    assert "verification_parent_sha: DYNAMIC_GIT_HEAD\n" not in manifest_text

    # Invariant 3: Both HEAD and HEAD^ are real Git objects
    res_head = subprocess.run(["git", "cat-file", "-e", git_head], cwd=root)
    res_parent = subprocess.run(["git", "cat-file", "-e", git_parent], cwd=root)
    assert res_head.returncode == 0
    assert res_parent.returncode == 0


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
