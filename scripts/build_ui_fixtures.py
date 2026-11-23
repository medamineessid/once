"""Build a synthetic app-data folder for the UI audit.

Usage:
    python scripts/build_ui_fixtures.py <folder>

The folder is created from scratch and is never the user's real
``%LOCALAPPDATA%/Once`` folder; the script refuses to write into it.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.ui_fixtures import build_ui_fixtures  # noqa: E402


def real_app_data_dir() -> Path:
    """The live data folder this script must never touch."""
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return (base / "Once").resolve()


def build(target: Path, *, force: bool = False) -> Path:
    """Create (or replace) the fixture folder at ``target``."""
    target = target.resolve()
    if target == real_app_data_dir():
        raise SystemExit("refusing to write fixtures into the real Once data folder")
    if target.exists():
        if not force:
            raise SystemExit(f"{target} already exists; pass --force to replace it")
        shutil.rmtree(target)
    target.mkdir(parents=True)
    return build_ui_fixtures(target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", help="target folder (default: a temp folder)")
    parser.add_argument("--force", action="store_true", help="replace an existing folder")
    args = parser.parse_args(argv)
    target = (
        Path(args.folder) if args.folder else Path(tempfile.mkdtemp(prefix="once-ui-fixtures-"))
    )
    built = build(target, force=args.force)
    print(built)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
