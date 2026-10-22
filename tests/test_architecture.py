"""Architecture guards for the Once package layers.

Covers safety invariant S9 (the engine never imports Qt or upper layers) and
S8 (the UI never performs file-system mutations). The checks work on the AST,
so a forbidden name in a comment or string literal cannot trigger them.
"""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_ENGINE_IMPORT_ROOTS = frozenset(
    {"PySide6", "shiboken6", "ui", "controller", "storage"}
)

# Calls that can mutate the file system. The UI must reach these only through
# the controller and engine; mutations are allowed solely in
# engine/executor.py and engine/recovery.py.
FORBIDDEN_MUTATIONS = frozenset(
    {
        "os.rename",
        "os.replace",
        "os.remove",
        "os.unlink",
        "os.rmdir",
        "os.mkdir",
        "os.makedirs",
        "os.removedirs",
        "os.chmod",
        "os.truncate",
        "os.utime",
        "os.link",
        "os.symlink",
        "os.open",
        "shutil.move",
        "shutil.copy",
        "shutil.copy2",
        "shutil.copyfile",
        "shutil.copyfileobj",
        "shutil.copytree",
        "shutil.rmtree",
        "pathlib.Path.rename",
        "pathlib.Path.replace",
        "pathlib.Path.unlink",
        "pathlib.Path.rmdir",
        "pathlib.Path.mkdir",
        "pathlib.Path.touch",
        "pathlib.Path.write_text",
        "pathlib.Path.write_bytes",
        "pathlib.Path.chmod",
        "pathlib.Path.chown",
        "pathlib.Path.hardlink_to",
        "pathlib.Path.symlink_to",
        "pathlib.Path.link_to",
    }
)


def find_forbidden_engine_imports(source: str, filename: str = "<string>") -> list[str]:
    """Return human-readable violations of the engine import rules."""
    tree = ast.parse(source, filename=filename)
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_ENGINE_IMPORT_ROOTS:
                    violations.append(f"{filename}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level > 1:
                violations.append(
                    f"{filename}:{node.lineno}: relative import escapes the engine package"
                )
            elif node.level == 0 and node.module:
                if node.module.split(".")[0] in FORBIDDEN_ENGINE_IMPORT_ROOTS:
                    violations.append(f"{filename}:{node.lineno}: from {node.module} import ...")

    return violations


def _dotted_name(node: ast.AST) -> str | None:
    """Render a Name/Attribute chain (including a constructor call) as a dotted name."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return f"{base}.{node.attr}" if base is not None else None
    if isinstance(node, ast.Call):
        return _dotted_name(node.func)
    return None


def _import_aliases(tree: ast.Module) -> dict[str, str]:
    """Map local names to the fully qualified names they refer to."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                aliases[local] = alias.name if alias.asname else alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for alias in node.names:
                if alias.name == "*":
                    continue
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return aliases


def _resolve_name(raw: str, aliases: dict[str, str]) -> str:
    parts = raw.split(".")
    resolved_root = aliases.get(parts[0], parts[0])
    return ".".join([resolved_root, *parts[1:]])


def _instance_types(tree: ast.Module, aliases: dict[str, str]) -> dict[str, str]:
    """Track simple assignments such as ``path = Path('x')``."""
    instances: dict[str, str] = {}

    def record(target: ast.expr, value: ast.expr | None) -> None:
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
            return
        raw = _dotted_name(value.func)
        if raw is not None:
            instances[target.id] = _resolve_name(raw, aliases)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                record(target, node.value)
        elif isinstance(node, ast.AnnAssign):
            record(node.target, node.value)
        elif isinstance(node, ast.NamedExpr):
            record(node.target, node.value)

    return instances


def find_forbidden_ui_mutations(source: str, filename: str = "<string>") -> list[str]:
    """Return calls in UI code that could mutate the file system."""
    tree = ast.parse(source, filename=filename)
    aliases = _import_aliases(tree)
    instances = _instance_types(tree, aliases)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        raw = _dotted_name(node.func)
        if raw is None:
            continue

        parts = raw.split(".")
        if parts[0] in instances:
            target = ".".join([instances[parts[0]], *parts[1:]])
        else:
            target = _resolve_name(raw, aliases)

        if target in FORBIDDEN_MUTATIONS:
            violations.append(f"{filename}:{node.lineno}: {target}()")

    return violations


def _package_sources(package: str) -> list[tuple[Path, str]]:
    sources: list[tuple[Path, str]] = []
    for path in sorted((PROJECT_ROOT / package).rglob("*.py")):
        sources.append((path, path.read_text(encoding="utf-8")))
    return sources


def test_S9_engine_does_not_import_pyside_or_upper_layers() -> None:
    violations: list[str] = []
    for path, source in _package_sources("engine"):
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        violations.extend(find_forbidden_engine_imports(source, relative))

    assert violations == []


def test_S8_ui_contains_no_filesystem_mutation_calls() -> None:
    violations: list[str] = []
    for path, source in _package_sources("ui"):
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        violations.extend(find_forbidden_ui_mutations(source, relative))

    assert violations == []


def test_engine_import_guard_flags_forbidden_imports() -> None:
    assert find_forbidden_engine_imports("import PySide6\n", "sample.py")
    assert find_forbidden_engine_imports("from ui import main_window\n", "sample.py")
    assert find_forbidden_engine_imports("from .. import something\n", "sample.py")


def test_engine_import_guard_allows_internal_and_stdlib_imports() -> None:
    source = (
        "import os\n"
        "from enum import StrEnum\n"
        "from . import errors\n"
        "from .models import Severity\n"
        "from engine.errors import OnceError\n"
    )
    assert find_forbidden_engine_imports(source, "sample.py") == []


def test_engine_import_guard_ignores_comments_and_strings() -> None:
    source = '# import PySide6\nTEXT = "from ui import main_window"\n'
    assert find_forbidden_engine_imports(source, "sample.py") == []


def test_ui_mutation_guard_flags_direct_and_aliased_calls() -> None:
    cases = [
        "import os\nos.rename('a', 'b')\n",
        "from os import rename as move_it\nmove_it('a', 'b')\n",
        "from shutil import copy2\ncopy2('a', 'b')\n",
        "from pathlib import Path\nPath('a').unlink()\n",
        "from pathlib import Path\npath = Path('a')\npath.write_text('x')\n",
        "import pathlib\npathlib.Path('a').mkdir()\n",
    ]
    for source in cases:
        assert find_forbidden_ui_mutations(source, "sample.py"), source


def test_ui_mutation_guard_allows_read_only_calls() -> None:
    source = (
        "from pathlib import Path\n"
        "text = Path('a').read_text(encoding='utf-8')\n"
        "items = list(Path('.').iterdir())\n"
        "label.setText('os.rename(a, b)')\n"
        "# os.unlink('a')\n"
    )
    assert find_forbidden_ui_mutations(source, "sample.py") == []
