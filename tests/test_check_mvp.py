"""Targeted checks for the MVP check command (no real Chrome needed).

scripts/check_mvp.py must stay a thin shell: the fixture loads through the
strict workflow validator, the ordered steps dispatch through the engine with
any BrowserActions implementation, and the pass/fail verdict has no hidden
"PASS on missing data" branch.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from engine.replay import DESKTOP_INTERACTION_POLICY, ReplayExecutor
from engine.workflow import StepKind, StepResult, StepStatus

REPO = Path(__file__).resolve().parent.parent


def _load_check():
    spec = importlib.util.spec_from_file_location("check_mvp", REPO / "scripts" / "check_mvp.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeBrowserActions:
    """Fixed browser session: one launch, ordered step results."""

    def __init__(self, port: int = 51922) -> None:
        self.port = port
        self.calls: list[str] = []

    def launch_browser(self, target_json: str) -> StepResult:
        self.calls.append("launch")
        return StepResult(
            "launch",
            StepStatus.SUCCEEDED,
            "Fake isolated Chrome is running.",
            evidence=(
                f"cdp_port={self.port}",
                "browser=Fake",
            ),
        )

    def navigate(self, target_json: str) -> StepResult:
        self.calls.append("NAVIGATE")
        return StepResult("navigate", StepStatus.SUCCEEDED, "The page loaded.")

    def inspect_page(self, target_json: str) -> StepResult:
        self.calls.append("INSPECT")
        return StepResult("inspect", StepStatus.SUCCEEDED, "Inspected.")

    def find_page_element(self, target_json: str) -> StepResult:
        self.calls.append("FIND")
        return StepResult("find", StepStatus.VERIFIED, "Found.")

    def interact_page_element(self, target_json: str) -> StepResult:
        self.calls.append("INTERACT")
        return StepResult("interact", StepStatus.SUCCEEDED, "Interacted.")

    def wait_page(self, target_json: str, timeout_seconds: float) -> StepResult:
        self.calls.append("WAIT")
        return StepResult("wait", StepStatus.SUCCEEDED, "Matched.")

    def shutdown(self) -> None:
        self.calls.append("SHUTDOWN")


class FailingActions(FakeBrowserActions):
    """A fake that fails one specific step to prove the check does not gloss over it."""

    failure_step = "navigate"

    def _fail(self, step_id: str) -> StepResult:
        return StepResult(step_id, StepStatus.FAILED, self.failure_step + " could not run.")

    def navigate(self, target_json: str) -> StepResult:
        self.calls.append("NAVIGATE")
        return self._fail("navigate")


def test_fixture_loads_through_strict_validator_and_splits_correctly():
    check = _load_check()
    document = json.loads((REPO / "scripts" / "fixtures" / "mvp_flow.json").read_text("utf-8"))
    setup_steps, main_steps = check._split_workflow(document, "http://127.0.0.1:1/")
    assert len(setup_steps) == 1 and len(main_steps) == 8
    setup = check._workflow_object(setup_steps, "setup")
    assert next(iter(setup.steps)).kind is StepKind.LAUNCH_BROWSER
    port = 51922
    prepared = []
    for step in main_steps:
        step["target"] = check._substitute(str(step["target"]), {"cdp_port": str(port)})
        step["target"] = check._coerce_browser_port(step["target"])
        prepared.append(step)
    main = check._workflow_object(prepared, "main")
    kinds = [step.kind for step in main.steps]
    assert kinds == [
        StepKind.NAVIGATE_BROWSER,
        StepKind.WAIT_PAGE,
        StepKind.INSPECT_PAGE,
        StepKind.FIND_PAGE_ELEMENT,
        StepKind.INTERACT_PAGE_ELEMENT,
        StepKind.INTERACT_PAGE_ELEMENT,
        StepKind.WAIT_PAGE,
        StepKind.FIND_PAGE_ELEMENT,
    ]
    assert "{url}" not in json.dumps(prepared)
    assert any('"text": "demo input"' in str(step.get("target")) for step in prepared)


def test_run_fixture_flow_dispatches_ordered_steps_through_engine_with_fake_actions():
    check = _load_check()
    actions = FakeBrowserActions()
    setup_run, main_run = check.run_fixture_flow(
        "http://127.0.0.1:1/", actions, ReplayExecutor(DESKTOP_INTERACTION_POLICY)
    )
    assert check.checked_outcome(setup_run, main_run) == (
        True,
        "The fixture flow ran and verified end to end.",
    )
    order = [call for call in actions.calls if call != "SHUTDOWN"]
    assert order == [
        "launch",
        "NAVIGATE",
        "WAIT",
        "INSPECT",
        "FIND",
        "INTERACT",
        "INTERACT",
        "WAIT",
        "FIND",
    ]


def test_missing_port_prevents_flow_and_fails_fairly():
    check = _load_check()
    setup_run, main_run = check.run_fixture_flow(
        "http://127.0.0.1:1/",
        FakeBrowserActions(port=0),
        ReplayExecutor(DESKTOP_INTERACTION_POLICY),
    )
    assert setup_run is not None and main_run is None
    ok, verdict = check.checked_outcome(setup_run, None)
    assert ok is False and "launch" in verdict
    assert check.checked_outcome(None, None)[0] is False


def test_record_runs_persists_snapshots_for_a_second_invocation(tmp_path):
    check = _load_check()
    from storage.database import connect as connect_database

    db = tmp_path / "history.db"
    actions = FakeBrowserActions()
    setup_run, main_run = check.run_fixture_flow(
        "http://127.0.0.1:1/", actions, ReplayExecutor(DESKTOP_INTERACTION_POLICY)
    )
    recorded_at = check.record_runs(db, setup_run, main_run)
    assert str(recorded_at).endswith("history.db")
    connection = connect_database(db)
    try:
        rows = connection.execute("SELECT run_id, status FROM workflow_runs").fetchall()
        assert len(rows) == 2
        assert {row[1] for row in rows} == {"SUCCEEDED"}
        step_rows = connection.execute("SELECT COUNT(*) FROM workflow_step_results").fetchone()
        assert step_rows[0] == 9
    finally:
        connection.close()


def test_failing_step_turns_the_verdict_false():
    check = _load_check()
    setup_run, main_run = check.run_fixture_flow(
        "http://127.0.0.1:1/", FailingActions(), ReplayExecutor(DESKTOP_INTERACTION_POLICY)
    )
    assert main_run is not None and main_run.status.value == "FAILED"
    ok, verdict = check.checked_outcome(setup_run, main_run)
    assert ok is False and "steps" in verdict
