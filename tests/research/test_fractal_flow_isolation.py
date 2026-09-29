"""Automated FRACTAL-FLOW Isolation Guard and Package Independence Tests.

This test enforces the constitutional mandate that Gyroscope source code contains ZERO
runtime imports, dependencies, or package couplings to FRACTAL-FLOW.
"""

import ast
from pathlib import Path
import pytest


def find_python_files(root_dir: Path):
    """Recursively find all Python source files in the project."""
    for p in root_dir.rglob("*.py"):
        if ".venv" in p.parts or "venv" in p.parts or ".pytest_cache" in p.parts:
            continue
        yield p


def check_ast_for_fractal_flow_imports(filepath: Path) -> list[str]:
    """Parse AST of a Python file and detect any import of 'fractal_flow'."""
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError as err:
        return [f"Syntax error in {filepath}: {err}"]

    for node in ast.walk(tree):
        # Direct import: import fractal_flow or import fractal_flow.something
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "fractal_flow" or alias.name.startswith("fractal_flow."):
                    violations.append(f"Line {node.lineno}: import {alias.name}")

        # From import: from fractal_flow import ...
        elif isinstance(node, ast.ImportFrom):
            if node.module == "fractal_flow" or (node.module and node.module.startswith("fractal_flow.")):
                violations.append(f"Line {node.lineno}: from {node.module} import ...")

        # Dynamic import call: importlib.import_module("fractal_flow...")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    if "fractal_flow" in node.args[0].value:
                        violations.append(f"Line {node.lineno}: import_module('{node.args[0].value}')")

    return violations


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
