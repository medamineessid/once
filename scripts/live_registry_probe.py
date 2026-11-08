"""Live Windows probe for the approved-application registry path.

Usage:
    python scripts/live_registry_probe.py --exe <path-to-exe> --db <temp-db-path>

Never hardcodes application names or paths, and never uses taskkill or force-kill.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.desktop import approve_desktop_workflow  # noqa: E402
from engine.replay import DESKTOP_INTERACTION_POLICY, ReplayExecutor  # noqa: E402
from engine.workflow import StepKind, StepStatus, Workflow, WorkflowStep  # noqa: E402
from integrations.windows_desktop import PywinautoDesktopActions  # noqa: E402
from storage.app_registry import SqliteApplicationRegistry  # noqa: E402
from storage.database import connect  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe the SQLite registry + desktop replay path.")
    parser.add_argument("--exe", required=True, type=Path, help="Absolute path to executable.")
    parser.add_argument("--db", required=True, type=Path, help="Path to temporary SQLite DB.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    exe: Path = args.exe.resolve()
    db_path: Path = args.db.resolve()

    if not exe.is_file():
        sys.stderr.write(f"ERROR: executable not found: {exe}\n")
        return 2

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    connection = connect(db_path)
    registry = SqliteApplicationRegistry(connection)
    target = json.dumps({"executable": str(exe)})

    # 1. Unapproved launch must be refused before starting any process.
    unapproved_actions = PywinautoDesktopActions(approvals=registry)
    unapproved_result = unapproved_actions.launch_application(target)
    print(f"[1/4] unapproved_status={unapproved_result.status.value}")
    print(f"[1/4] unapproved_evidence={list(unapproved_result.evidence)}")
    if unapproved_result.status is not StepStatus.FAILED:
        return 1

    # 2. Propose and approve the executable in SQLite.
    proposed = registry.propose(exe, exe.stem)
    approved = registry.approve(exe, display_name=exe.stem, close_supported=True)
    print(
        f"[2/4] proposed_approved={proposed.approved} "
        f"after_approve={approved.approved} sha256={approved.sha256[:16]}..."
    )

    # 3. Run a real LAUNCH_APPLICATION + CLOSE_APPLICATION workflow through ReplayExecutor.
    actions = PywinautoDesktopActions(approvals=registry)
    workflow = Workflow(
        workflow_id="live-registry-probe",
        name="Live registry probe",
        steps=(
            WorkflowStep("launch", "Launch", StepKind.LAUNCH_APPLICATION, "Launched.", target),
            WorkflowStep("close", "Close", StepKind.CLOSE_APPLICATION, "Closed.", target),
        ),
    )
    approval = approve_desktop_workflow(workflow)
    run = ReplayExecutor(DESKTOP_INTERACTION_POLICY).execute(
        approval.workflow,
        allowed_root=None,
        desktop_actions=actions,
    )
    print(f"[3/4] run_status={run.status.value}")
    for step_result in run.results:
        print(
            f"[3/4] step={step_result.step_id} status={step_result.status.value} "
            f"evidence={list(step_result.evidence)}"
        )
    if run.status.value != "SUCCEEDED":
        return 1

    # 4. Tamper with stored sha256 in DB and verify hash_mismatch refusal.
    connection.execute("UPDATE approved_applications SET sha256 = ?", ("0" * 64,))
    connection.commit()
    mismatch_actions = PywinautoDesktopActions(approvals=registry)
    mismatch_result = mismatch_actions.launch_application(target)
    print(f"[4/4] mismatch_status={mismatch_result.status.value}")
    print(f"[4/4] mismatch_evidence={list(mismatch_result.evidence)}")
    connection.close()
    if mismatch_result.status is not StepStatus.FAILED:
        return 1

    print("LIVE_REGISTRY_PROBE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
