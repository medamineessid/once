"""Tests for the screenshot output-folder guard (Sonar S8707).

scripts/capture_ui_shots.py writes PNGs. The output folder must resolve inside
the repository's shots/ folder or the system temp folder; anything else is
refused before a folder is created.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "capture_ui_shots.py"


def _load_script() -> object:
    spec = importlib.util.spec_from_file_location("capture_ui_shots", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


script = _load_script()


def test_relative_path_resolves_inside_shots() -> None:
    resolved = script.resolve_output_dir("shots/design-v4")

    assert resolved == (PROJECT_ROOT / "shots" / "design-v4").resolve()


def test_bare_folder_name_is_refused_because_it_is_not_under_shots() -> None:
    with pytest.raises(ValueError, match="outside shots/ or the temp folder"):
        script.resolve_output_dir("design-v4")


def test_absolute_path_inside_shots_is_allowed() -> None:
    target = PROJECT_ROOT / "shots" / "design-v4"

    assert script.resolve_output_dir(str(target)) == target.resolve()


def test_path_inside_the_temp_folder_is_allowed(tmp_path: Path) -> None:
    # pytest's tmp_path lives under the system temp folder.
    assert script.resolve_output_dir(str(tmp_path)) == tmp_path.resolve()


def test_path_outside_shots_and_temp_is_refused() -> None:
    with pytest.raises(ValueError, match="outside shots/ or the temp folder"):
        script.resolve_output_dir(str(PROJECT_ROOT / "build" / "captures"))


def test_parent_traversal_out_of_shots_is_refused() -> None:
    with pytest.raises(ValueError):
        script.resolve_output_dir(str(Path("shots") / ".." / ".." / "elsewhere"))


def test_tempfolder_prefix_lookalike_is_refused() -> None:
    lookalike = Path(tempfile.gettempdir()).parent / "not-the-temp-folder" / "shots"

    with pytest.raises(ValueError):
        script.resolve_output_dir(str(lookalike))
