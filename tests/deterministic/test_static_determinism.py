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
    "gyroscope/adapters",
    "gyroscope/contracts",
    "gyroscope/risk",
    "gyroscope/execution",
    "gyroscope/persistence",
    "gyroscope/broker",
    "gyroscope/reconciliation",
]

# Map of forbidden modules and their dangerous attributes
FORBIDDEN_MODULE_ATTRS = {
    "datetime": {"now", "utcnow", "today"},
    "time": {"time", "time_ns", "monotonic", "monotonic_ns", "perf_counter", "perf_counter_ns"},
    "random": {"random", "randint", "randrange", "choice", "shuffle", "uniform", "getrandbits"},
    "secrets": {"token_hex", "token_bytes", "choice", "randbelow"},
    "uuid": {"uuid1", "uuid4"},
    "os": {"urandom"},
}

FORBIDDEN_BUILTINS = {"id", "hash"}


class NondeterminismASTVisitor(ast.NodeVisitor):
    """AST Visitor that tracks module imports, aliased imports, and symbol bindings to detect forbidden calls."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.findings = []
        # Maps local symbol name -> (module_name, original_attr_name)
        # e.g. import time as t -> self.module_aliases['t'] = 'time'
        # e.g. from time import time as clock -> self.symbol_aliases['clock'] = ('time', 'time')
        self.module_aliases = {}
        self.symbol_aliases = {}

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            mod_name = alias.name
            as_name = alias.asname or mod_name
            self.module_aliases[as_name] = mod_name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod_name = node.module or ""
        for alias in node.names:
            orig_attr = alias.name
            as_name = alias.asname or orig_attr
            self.symbol_aliases[as_name] = (mod_name, orig_attr)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # 1. Attribute call: obj.attr() e.g. time.time(), t.time(), datetime.now()
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                var_name = node.func.value.id
                attr_name = node.func.attr
                # Resolve module name from alias if applicable
                resolved_mod = self.module_aliases.get(var_name, var_name)
                if resolved_mod in FORBIDDEN_MODULE_ATTRS and attr_name in FORBIDDEN_MODULE_ATTRS[resolved_mod]:
                    self.findings.append({
                        "file": str(self.filepath),
                        "line": node.lineno,
                        "api": f"{resolved_mod}.{attr_name}",
                        "classification": "FORBIDDEN_NONDETERMINISTIC_CALL",
                    })

        # 2. Direct symbol call: func() e.g. time(), clock(), make_uuid(), id(), hash()
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in FORBIDDEN_BUILTINS:
                self.findings.append({
                    "file": str(self.filepath),
                    "line": node.lineno,
                    "api": func_name,
                    "classification": "FORBIDDEN_BUILTIN_CALL",
                })
            elif func_name in self.symbol_aliases:
                mod_name, orig_attr = self.symbol_aliases[func_name]
                if mod_name in FORBIDDEN_MODULE_ATTRS and orig_attr in FORBIDDEN_MODULE_ATTRS[mod_name]:
                    self.findings.append({
                        "file": str(self.filepath),
                        "line": node.lineno,
                        "api": f"{mod_name}.{orig_attr}",
                        "classification": "FORBIDDEN_NONDETERMINISTIC_CALL",
                    })

        self.generic_visit(node)


def audit_source_code(source: str, filepath: Path = Path("virtual.py")):
    tree = ast.parse(source, filename=str(filepath))
    visitor = NondeterminismASTVisitor(filepath)
    visitor.visit(tree)
    return visitor.findings


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
            file_findings = audit_source_code(source, py_file.relative_to(root))
            findings.extend(file_findings)

    assert not findings, f"Forbidden nondeterministic dependencies discovered in authoritative code: {findings}"


def test_static_determinism_negative_controls():
    """Negative-control unit tests proving the AST auditor catches all alias and import bypass variations, plus hash/id."""
    test_cases = [
        ("import time as t\nt.time()", "time.time"),
        ("from time import time\ntime()", "time.time"),
        ("from time import time as clock\nclock()", "time.time"),
        ("import random as r\nr.random()", "random.random"),
        ("from random import random\nrandom()", "random.random"),
        ("from random import random as rand\nrand()", "random.random"),
        ("import uuid as u\nu.uuid4()", "uuid.uuid4"),
        ("from uuid import uuid4\nuuid4()", "uuid.uuid4"),
        ("from uuid import uuid4 as make_uuid\nmake_uuid()", "uuid.uuid4"),
        ("x = id(object())", "id"),
        ("x = hash('test')", "hash"),
    ]

    for source_code, expected_api in test_cases:
        findings = audit_source_code(source_code)
        assert len(findings) == 1, f"Expected 1 finding for snippet: {source_code!r}, got: {findings}"
        assert findings[0]["api"] == expected_api, f"Expected API {expected_api}, got {findings[0]['api']}"


def test_static_determinism_legitimate_code_passes():
    """Verify legitimate deterministic constructs pass without false positives."""
    legitimate_source = """
import hashlib
import json
from decimal import Decimal

def compute_hash(data: dict) -> str:
    s = json.dumps(data, sort_keys=True)
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

class SafeObject:
    def __init__(self, val: int):
        self.val = val

def process():
    a = Decimal('100.50')
    b = compute_hash({'a': 1})
    return a, b
"""
    findings = audit_source_code(legitimate_source)
    assert not findings, f"Expected 0 findings for legitimate source code, got: {findings}"
