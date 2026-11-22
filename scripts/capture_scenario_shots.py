"""Save one screenshot per scenario step so a human can see what happened.

The Qt scenario windows are rendered offscreen; each capture is that window
only (``window.grab``), never the desktop. Run from the repository root::

    python scripts/capture_scenario_shots.py

Output goes to ``shots/scenarios/<scenario>/NN-variant-phase.png``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.scenarios.catalog import qt_cases  # noqa: E402 - after sys.path setup
from tests.scenarios.lab import run_scenario  # noqa: E402 - after sys.path setup
from tests.scenarios.qt_window import ensure_application  # noqa: E402 - after sys.path setup

OUTPUT_DIR = ROOT / "shots" / "scenarios"


def main() -> int:
    """Capture every Qt scenario step and print what was written."""
    ensure_application()
    written: list[Path] = []
    with qt_cases(settle_ms=350) as cases:
        for scenario, adapter in cases:
            counter = {"value": 0}
            scenario_id = scenario.scenario_id

            def observer(
                variant: str,
                phase: str,
                *,
                _counter: dict[str, int] = counter,
                _scenario_id: str = scenario_id,
                _adapter=adapter,
            ) -> None:
                _counter["value"] += 1
                path = OUTPUT_DIR / _scenario_id / f"{_counter['value']:02d}-{variant}-{phase}.png"
                _adapter.save_screenshot(path)
                written.append(path)

            run_scenario(scenario, adapter, observer=observer)

    for path in written:
        print(f"{path.relative_to(ROOT).as_posix()} ({path.stat().st_size // 1024} KB)")
    print(f"{len(written)} screenshots in {OUTPUT_DIR.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
