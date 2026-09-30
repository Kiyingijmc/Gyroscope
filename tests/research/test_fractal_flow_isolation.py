"""Automated FRACTAL-FLOW Isolation Guard and Package Independence Tests.

This test enforces the constitutional mandate that Gyroscope source code contains ZERO
runtime imports, dependencies, or package couplings to FRACTAL-FLOW.
"""

import ast
from pathlib import Path
import subprocess
import sys
import pytest


def find_python_files(root_dir: Path):
    """Recursively find all Python source files in the project."""
    for p in root_dir.rglob("*.py"):
        if ".venv" in p.parts or "venv" in p.parts or ".pytest_cache" in p.parts:
            continue
        yield p


def is_fractal_flow_module(module_name: str | None) -> bool:
    """Exact module-boundary matching for fractal_flow and its submodules."""
    if not module_name:
        return False
    return module_name == "fractal_flow" or module_name.startswith("fractal_flow.")


def check_ast_content_for_fractal_flow_imports(content: str, filename: str = "<string>") -> list[str]:
    """Parse AST string content and detect forbidden imports of 'fractal_flow' using exact module boundaries."""
    violations = []
    try:
        tree = ast.parse(content, filename=filename)
    except SyntaxError as err:
        return [f"Syntax error in {filename}: {err}"]

    for node in ast.walk(tree):
        # Direct import: import fractal_flow or import fractal_flow.core
        if isinstance(node, ast.Import):
            for alias in node.names:
                if is_fractal_flow_module(alias.name):
                    violations.append(f"Line {node.lineno}: import {alias.name}")

        # From import: from fractal_flow import core
        elif isinstance(node, ast.ImportFrom):
            if is_fractal_flow_module(node.module):
                violations.append(f"Line {node.lineno}: from {node.module} import ...")

        # Dynamic import call: importlib.import_module("fractal_flow...") or __import__("fractal_flow...")
        elif isinstance(node, ast.Call):
            target_mod = None
            if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    target_mod = node.args[0].value
            elif isinstance(node.func, ast.Name) and node.func.id == "__import__":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    target_mod = node.args[0].value

            if target_mod and is_fractal_flow_module(target_mod):
                violations.append(f"Line {node.lineno}: import call for '{target_mod}'")

    return violations


def check_ast_for_fractal_flow_imports(filepath: Path) -> list[str]:
    """Parse AST of a Python file and detect any import of 'fractal_flow'."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as err:
        return [f"Error reading {filepath}: {err}"]
    return check_ast_content_for_fractal_flow_imports(content, filename=str(filepath))


def test_no_fractal_flow_source_imports_in_codebase():
    """Verify that no Python file under gyroscope/ or tests/ imports fractal_flow."""
    project_root = Path(__file__).parent.parent.parent
    source_dirs = [project_root / "gyroscope", project_root / "tests"]

    all_violations = {}
    for sdir in source_dirs:
        if not sdir.exists():
            continue
        for py_file in find_python_files(sdir):
            violations = check_ast_for_fractal_flow_imports(py_file)
            if violations:
                rel_path = py_file.relative_to(project_root)
                all_violations[str(rel_path)] = violations

    assert not all_violations, f"FRACTAL-FLOW source import violations detected: {all_violations}"


def test_gyroscope_imports_independently():
    """Verify that gyroscope imports cleanly without external FRACTAL-FLOW package."""
    import gyroscope
    import gyroscope.config
    import gyroscope.core
    import gyroscope.logging
    import gyroscope.observation
    import gyroscope.provenance
    import gyroscope.state

    assert gyroscope.__version__ == "0.1.0"


def test_gyroscope_subprocess_package_independence():
    """Verify in a fresh Python subprocess that Gyroscope runtime packages import successfully when FRACTAL-FLOW is blocked."""
    repo_root = str(Path(__file__).parent.parent.parent.resolve())

    code = f"""
import sys

repo_root = r"{repo_root}"
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

class BlockFractalFlowFinder:
    def find_spec(self, fullname, path, target=None):
        if fullname == "fractal_flow" or fullname.startswith("fractal_flow."):
            raise ImportError(f"FRACTAL-FLOW blocked: {{fullname}}")
        return None

sys.meta_path.insert(0, BlockFractalFlowFinder())

try:
    import fractal_flow
    print("ERROR: fractal_flow should be blocked")
    sys.exit(1)
except ImportError:
    pass

import gyroscope
import gyroscope.config
import gyroscope.core
import gyroscope.logging
import gyroscope.observation
import gyroscope.provenance
import gyroscope.state

assert gyroscope.__version__ == "0.1.0"
assert "fractal_flow" not in sys.modules
print("OK")
"""

    res = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Subprocess isolation test failed:\nstdout: {res.stdout}\nstderr: {res.stderr}"
    assert "OK" in res.stdout.strip()


def test_ast_guard_module_boundary_matching_regressions():
    """Regression test for AST guard ensuring exact module boundary matching (reject vs accept)."""
    must_reject_cases = [
        "import fractal_flow",
        "import fractal_flow.core",
        "import fractal_flow.foo.bar",
        "from fractal_flow import something",
        "from fractal_flow.sub import feature",
        "import importlib\nimportlib.import_module('fractal_flow')",
        "import importlib\nimportlib.import_module('fractal_flow.engine')",
        "__import__('fractal_flow')",
        "__import__('fractal_flow.adapter')",
    ]

    must_accept_cases = [
        "import my_fractal_flow_adapter",
        "import research_fractal_flow",
        "import fractal_flowish",
        "from my_fractal_flow_adapter import foo",
        "import importlib\nimportlib.import_module('my_fractal_flow_adapter')",
        "__import__('research_fractal_flow')",
        "docstring = 'This system integrates with fractal_flow specification'",
    ]

    for code in must_reject_cases:
        violations = check_ast_content_for_fractal_flow_imports(code, filename="<test_case_reject>")
        assert violations, f"Expected AST guard to REJECT code: {code!r}, but got no violations."

    for code in must_accept_cases:
        violations = check_ast_content_for_fractal_flow_imports(code, filename="<test_case_accept>")
        assert not violations, f"Expected AST guard to ACCEPT code: {code!r}, but got violations: {violations}"
