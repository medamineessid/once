"""Fixture-based end-to-end check for the desktop automation MVP flow.

One command: start a local fixture page host, load scripts/fixtures/mvp_flow.json
(the automation: explicit intent plus ordered steps), substitute the parameter
inputs, run the flow unattended through the approval/verify engine on a real
isolated Chrome session, then print PASS or FAIL.

Exit code 0 means the whole flow verified; exit code 1 means any step failed,
the fixture is invalid, or the launch did not report a browser port. A failing
step stops the run and is reported; the engine never improvises.

Run with (Windows Python, only where a real Chrome exists):
  C:\\Users\\DELL\\once\\.venv\\Scripts\\python.exe scripts\\check_mvp.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.desktop import approve_desktop_workflow
from engine.replay import DESKTOP_INTERACTION_POLICY, ReplayExecutor
from engine.workflow import (
    VALID_CDP_PORT_MAX as VALID_CDP_PORT_MAX,
)
from engine.workflow import (
    VALID_CDP_PORT_MIN as VALID_CDP_PORT_MIN,
)
from engine.workflow import (
    StepKind,
    StepStatus,
    Workflow,
    WorkflowRun,
)
from integrations.chrome_devtools import ChromeDevtoolsActions
from storage.database import connect as connect_database
from storage.history import ExecutionHistory
from storage.workflows import workflow_from_dict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "mvp_flow.json"
ACCEPTED_STEP_STATUSES = (StepStatus.SUCCEEDED, StepStatus.VERIFIED)

# Imported last so the fixture-page host stays an explicit demo dependency.
from chrome_demo import DemoServer, show  # noqa: E402


def _run_report_pass(run: WorkflowRun | None) -> bool:
    """A run is acceptable only when it ran and every step succeeded."""
    return (
        run is not None
        and run.status.value == "SUCCEEDED"
        and all(result.status in ACCEPTED_STEP_STATUSES for result in run.results)
    )


def _cdp_port(evidence: tuple[str, ...]) -> int | None:
    for entry in evidence:
        if entry.startswith("cdp_port="):
            return int(entry.split("=", 1)[1])
    return None


def _substitute(text: str, values: dict[str, str]) -> str:
    substituted = text
    for name, value in values.items():
        substituted = substituted.replace("{" + name + "}", value)
    return substituted


def _coerce_browser_port(target: str | None) -> str | None:
    """Coerce the engine-controlled cdp_port value to the int the validator demands."""
    if target is None:
        return None
    parsed = json.loads(target)
    browser = parsed.get("browser")
    if isinstance(browser, dict) and "cdp_port" in browser:
        browser["cdp_port"] = int(browser["cdp_port"])
    return json.dumps(parsed)


def _split_workflow(document: dict, demo_url: str) -> tuple[list, list]:
    """Prepare the fixture's ordered steps: static parameters in, launch split out."""
    text_input = str(document["params"]["text"])
    raw = _substitute(
        json.dumps(document["workflow"]),
        {"url": demo_url, "text": text_input},
    )
    steps = json.loads(raw)["steps"]
    if not steps or StepKind(steps[0]["kind"]) is not StepKind.LAUNCH_BROWSER:
        raise ValueError("The fixture workflow must start with a launch step.")
    return steps[:1], steps[1:]


def _workflow_object(steps: list, name: str) -> Workflow:
    return workflow_from_dict(
        {
            "schema_version": 3,
            "workflow_id": "mvp-chrome-demo-flow",
            "name": name,
            "steps": steps,
        }
    )


def checked_outcome(
    setup_run: WorkflowRun | None, main_run: WorkflowRun | None
) -> tuple[bool, str]:
    """The single pass/fail verdict for the MVP flow."""
    if not _run_report_pass(setup_run):
        return False, "The launch step did not succeed."
    port = _cdp_port(setup_run.results[0].evidence)
    if port is None or not (VALID_CDP_PORT_MIN <= port <= VALID_CDP_PORT_MAX):
        return False, "The launch step reported no DevTools port."
    if not _run_report_pass(main_run):
        return False, "One or more flow steps failed; see the step messages."
    return True, "The fixture flow ran and verified end to end."


def run_fixture_flow(
    demo_url: str, actions, executor
) -> tuple[WorkflowRun | None, WorkflowRun | None]:
    """Execute the fixture automation: launch first, then the ordered flow."""
    document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    setup_steps, main_steps = _split_workflow(document, demo_url)

    setup_run = executor.execute(
        approve_desktop_workflow(
            _workflow_object(setup_steps, "MVP browser fixture setup")
        ).workflow,
        allowed_root=None,
        browser_actions=actions,
    )
    port = _cdp_port(setup_run.results[0].evidence) if setup_run.results else None
    if port is None or not (VALID_CDP_PORT_MIN <= port <= VALID_CDP_PORT_MAX):
        return setup_run, None

    prepared = []
    for step in main_steps:
        step["target"] = _substitute(str(step["target"]), {"cdp_port": str(port)})
        step["target"] = _coerce_browser_port(step["target"])
        prepared.append(step)
    main_run = executor.execute(
        approve_desktop_workflow(_workflow_object(prepared, "MVP browser fixture flow")).workflow,
        allowed_root=None,
        browser_actions=actions,
    )
    return setup_run, main_run


def default_history_path() -> Path:
    """App-data location for the run history database (same convention as app.py)."""
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / "Once" / "history.db"


def record_runs(db_path: Path, *runs: WorkflowRun | None) -> str:
    """Append every completed run snapshot to the history database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect_database(db_path)
    try:
        history = ExecutionHistory(connection)
        for run in runs:
            if run is not None:
                history.record(run)
    finally:
        connection.close()
    return str(db_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--history-db",
        type=Path,
        default=default_history_path(),
        help="Optional path for the run history SQLite database.",
    )
    args = parser.parse_args()

    server = DemoServer()
    print(f"local fixture page: {server.url()}")
    actions = ChromeDevtoolsActions()
    executor = ReplayExecutor(DESKTOP_INTERACTION_POLICY)

    try:
        setup_run, main_run = run_fixture_flow(server.url(), actions, executor)
        show(setup_run)
        if main_run is not None:
            show(main_run)
        recorded_at = record_runs(args.history_db, setup_run, main_run)
        print(f"history: run snapshots recorded in {recorded_at}")
        ok, verdict = checked_outcome(setup_run, main_run)
        if ok and main_run is not None:
            print(f"CHECK: PASS - run {main_run.run_id} verified end to end.")
            return 0
        print("CHECK: FAIL - " + verdict)
        return 1
    finally:
        actions.shutdown()
        print("cleanup: the engine-launched browser was closed and its profile removed.")
        server.stop()
        print("cleanup: the local fixture server was stopped.")


if __name__ == "__main__":
    raise SystemExit(main())
