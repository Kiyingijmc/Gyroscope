"""AST-based static determinism audit for authoritative Gyroscope Phase 1 source code."""

import ast
from pathlib import Path
import pytest


AUTHORITATIVE_PATHS = [
    "gyroscope/core",
    "gyroscope/engine",
    "gyroscope/observation",
    "gyroscope/provenance",
    "gyroscope/state",
    "gyroscope/config",
]

# Forbidden AST attribute/function names in authoritative code paths
FORBIDDEN_CALL_PATTERNS = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("datetime", "today"),
    ("time", "time"),
    ("time", "time_ns"),
    ("time", "monotonic"),
    ("time", "monotonic_ns"),
    ("time", "perf_counter"),
    ("time", "perf_counter_ns"),
    ("random", "random"),
    ("random", "randint"),
    ("random", "choice"),
    ("secrets", "token_hex"),
    ("secrets", "token_bytes"),
    ("uuid", "uuid1"),
    ("uuid", "uuid4"),
    ("os", "urandom"),
}

FORBIDDEN_BUILTINS = {"id"}


class NondeterminismASTVisitor(ast.NodeVisitor):
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.findings = []

    def visit_Call(self, node: ast.Call):
        # Check forbidden function calls like datetime.now() or time.time()
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
                attr_name = node.func.attr
                if (module_name, attr_name) in FORBIDDEN_CALL_PATTERNS:
                    self.findings.append({
                        "file": str(self.filepath),
                        "line": node.lineno,
                        "api": f"{module_name}.{attr_name}",
                        "classification": "FORBIDDEN_NONDETERMINISTIC_CALL",
                    })
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in FORBIDDEN_BUILTINS:
                self.findings.append({
                    "file": str(self.filepath),
                    "line": node.lineno,
                    "api": func_name,
                    "classification": "FORBIDDEN_BUILTIN_CALL",
                })
        self.generic_visit(node)


def test_static_determinism_ast_audit():
    """Static AST audit ensuring zero forbidden nondeterministic sources exist in authoritative Phase 1 paths."""
    root = Path(__file__).parent.parent.parent
    findings = []

    for rel_path in AUTHORITATIVE_PATHS:
        dir_path = root / rel_path
        if not dir_path.exists():
            continue
        for py_file in dir_path.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
            visitor = NondeterminismASTVisitor(py_file.relative_to(root))
            visitor.visit(tree)
            findings.extend(visitor.findings)

    assert not findings, f"Forbidden nondeterministic dependencies discovered in authoritative code: {findings}"
