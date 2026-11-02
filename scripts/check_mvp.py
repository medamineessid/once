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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.desktop import approve_desktop_workflow
from engine.replay import DESKTOP_INTERACTION_POLICY, ReplayExecutor
from engine.workflow import StepKind, StepStatus, WorkflowRun
from integrations.chrome_devtools import ChromeDevtoolsActions
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


def _browser_port_to_int(step_target: str | None) -> str | None:
    """Coerce the engine-controlled cdp_port value to the int the validator demands."""
    if step_target is None:
        return None
    target = json.loads(step_target)
    browser = target.get("browser")
    if isinstance(browser, dict) and "cdp_port" in browser:
        browser["cdp_port"] = int(browser["cdp_port"])
    return json.dumps(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    args = parser.parse_args()

    document = json.loads(args.fixture.read_text(encoding="utf-8"))
    text_input = str(document["params"]["text"])
    print(f"check text input parameterized from fixture: {text_input}")

    server = DemoServer()
    print(f"local fixture page: {server.url()}")
    actions = ChromeDevtoolsActions()
    executor = ReplayExecutor(DESKTOP_INTERACTION_POLICY)
    setup_run: WorkflowRun | None = None
    main_run: WorkflowRun | None = None

    try:
        launch_values = {"url": server.url(), "text": text_input}
        split_doc = _substitute(json.dumps(document["workflow"]), launch_values)
        steps = json.loads(split_doc)["steps"]
        if not steps or StepKind(steps[0]["kind"]) is not StepKind.LAUNCH_BROWSER:
            print("CHECK: FAIL - the fixture workspace must start with a launch step.")
            return 1

        setup_workflow = workflow_from_dict(
            {
                "schema_version": 3,
                "workflow_id": "mvp-chrome-demo-flow",
                "name": "MVP browser fixture setup",
                "steps": steps[:1],
            }
        )
        setup_run = executor.execute(
            approve_desktop_workflow(setup_workflow).workflow,
            allowed_root=None,
            browser_actions=actions,
        )
        show(setup_run)
        port = _cdp_port(setup_run.results[0].evidence) if setup_run.results else None
        if port is None:
            print("CHECK: FAIL - the launch step reported no DevTools port.")
            return 1

        full_doc = _substitute(split_doc, {"cdp_port": str(port)})
        main_steps = json.loads(full_doc)["steps"][1:]
        for step in main_steps:
            step["target"] = _browser_port_to_int(step["target"])
        main_workflow = workflow_from_dict(
            {
                "schema_version": 3,
                "workflow_id": "mvp-chrome-demo-flow",
                "name": "MVP browser fixture flow",
                "steps": main_steps,
            }
        )
        main_run = executor.execute(
            approve_desktop_workflow(main_workflow).workflow,
            allowed_root=None,
            browser_actions=actions,
        )
        show(main_run)

        if _run_report_pass(setup_run) and _run_report_pass(main_run):
            print(f"CHECK: PASS - run {main_run.run_id} verified end to end.")
            return 0
        print("CHECK: FAIL - see the step messages above.")
        return 1
    finally:
        actions.shutdown()
        print("cleanup: the engine-launched browser was closed and its profile removed.")
        server.stop()
        print("cleanup: the local fixture server was stopped.")


if __name__ == "__main__":
    raise SystemExit(main())
