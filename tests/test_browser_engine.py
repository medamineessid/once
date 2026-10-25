"""Deterministic tests for the isolated-browser engine contracts (fake provider)."""

from __future__ import annotations

import json

import pytest

from engine.desktop import approve_desktop_workflow
from engine.errors import WorkflowValidationError
from engine.replay import DESKTOP_INTERACTION_POLICY, MUTATING_DESKTOP_KINDS, ReplayExecutor
from engine.workflow import (
    StepKind,
    StepStatus,
    Workflow,
    WorkflowRunner,
    WorkflowStatus,
    WorkflowStep,
)

BROWSER = {"cdp_port": 51922}
NAVIGATE_TARGET = {"browser": BROWSER, "url": "http://127.0.0.1:8000/demo.html"}
INSPECT_TARGET = {"browser": BROWSER}
FIND_TARGET = {"browser": BROWSER, "selector": "h1"}
INTERACT_TARGET = {"browser": BROWSER, "selector": "button", "interaction": "click"}
TYPE_TARGET = {"browser": BROWSER, "selector": "input", "interaction": "type", "text": "hello"}
WAIT_TARGET = {"browser": BROWSER, "conditions": {"title": "Demo"}}


def step(step_id, kind, target, timeout=10.0):
    return WorkflowStep(
        step_id, step_id.replace("-", " "), kind, kind.value, target=json.dumps(target)
    )


class FakeBrowserActions:
    """Records targets and scripts results per kind."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def _record(self, kind: str):
        from engine.workflow import StepResult

        return StepResult(step_id="", status=StepStatus.SUCCEEDED, message="ok")

    def launch_browser(self, target_json: str):
        self.calls.append(("LAUNCH_BROWSER", target_json))
        return self._record("LAUNCH_BROWSER")

    def navigate(self, target_json: str):
        self.calls.append(("NAVIGATE_BROWSER", target_json))
        return self._record("NAVIGATE_BROWSER")

    def inspect_page(self, target_json: str):
        self.calls.append(("INSPECT_PAGE", target_json))
        return self._record("INSPECT_PAGE")

    def find_page_element(self, target_json: str):
        self.calls.append(("FIND_PAGE_ELEMENT", target_json))
        return self._record("FIND_PAGE_ELEMENT")

    def interact_page_element(self, target_json: str):
        self.calls.append(("INTERACT_PAGE_ELEMENT", target_json))
        return self._record("INTERACT_PAGE_ELEMENT")

    def wait_page(self, target_json: str, timeout_seconds: float):
        self.calls.append(("WAIT_PAGE", target_json))
        return self._record("WAIT_PAGE")


def run_with(actions: FakeBrowserActions, steps: tuple[WorkflowStep, ...]):
    workflow = Workflow("browser-flow", "Browser flow", steps)
    run = WorkflowRunner().run(workflow, browser_actions=actions)
    return run, actions


# ------------------------------------------------------------------ validation


def test_launch_browser_requires_registered_chrome() -> None:
    ok = step("launch", StepKind.LAUNCH_BROWSER, {"application": "chrome"})
    WorkflowRunner.validate(Workflow("w", "w", (ok,)))
    unknown_app = step("bad", StepKind.LAUNCH_BROWSER, {"application": "edge"})
    with pytest.raises(WorkflowValidationError, match="registry does not allow"):
        WorkflowRunner.validate(Workflow("w2", "w2", (unknown_app,)))
    bad_exe = step("bad2", StepKind.LAUNCH_BROWSER, {"executable": "C:/tools/browser.exe"})
    with pytest.raises(WorkflowValidationError, match="other than the registered"):
        WorkflowRunner.validate(Workflow("w3", "w3", (bad_exe,)))


def test_navigate_url_validation_rejects_unsafe_values() -> None:
    for target, message in (
        ({"browser": BROWSER, "url": "file:///C:/Windows/notepad.exe"}, "must be one of"),
        ({"browser": BROWSER, "url": "javascript:alert(1)"}, "must be one of"),
        ({"browser": BROWSER, "url": "chrome://settings"}, "must be one of"),
        ({"browser": BROWSER, "url": "ftp://host/file"}, "must be one of"),
        ({"browser": BROWSER, "url": "http://user:pw@host/"}, "must not embed user names"),
        ({"browser": BROWSER, "url": "http:///no-host"}, "needs a host name"),
        ({"browser": BROWSER, "url": "http://host/\tpath"}, "whitespace or control"),
        ({"browser": BROWSER, "url": "http://" + "a" * 3000 + ".com/"}, "too long"),
        ({"browser": BROWSER}, "needs a URL"),
    ):
        with pytest.raises(WorkflowValidationError) as caught:
            WorkflowRunner.validate(
                Workflow("w", "w", (step("nav", StepKind.NAVIGATE_BROWSER, target),))
            )
        assert message in str(caught.value), target


def test_navigate_accepts_https_and_localhost() -> None:
    ok = step("nav", StepKind.NAVIGATE_BROWSER, NAVIGATE_TARGET)
    WorkflowRunner.validate(Workflow("w", "w", (ok,)))
    https = step(
        "nav", StepKind.NAVIGATE_BROWSER, {"browser": BROWSER, "url": "https://example.com/"}
    )
    WorkflowRunner.validate(Workflow("w", "w", (https,)))


def test_browser_target_binds_the_port_range() -> None:
    for port in (80, 66_000, "51922", True, True, 1023):
        target = json.dumps({"browser": {"cdp_port": port}, "url": "http://h/"})
        with pytest.raises(WorkflowValidationError, match="port between"):
            WorkflowRunner.validate(
                Workflow(
                    "w",
                    "w",
                    (WorkflowStep("nav", "nav", StepKind.NAVIGATE_BROWSER, "n", target=target),),
                )
            )
    ok = step("nav", StepKind.NAVIGATE_BROWSER, NAVIGATE_TARGET)
    WorkflowRunner.validate(Workflow("w", "w", (ok,)))
    boundary_ok = step(
        "nav", StepKind.NAVIGATE_BROWSER, {"browser": {"cdp_port": 1024}, "url": "http://h/"}
    )
    WorkflowRunner.validate(Workflow("w", "w", (boundary_ok,)))


def test_inspect_page_bounded_flags() -> None:
    ok = step("inspect", StepKind.INSPECT_PAGE, {"browser": BROWSER, "include_text": True})
    WorkflowRunner.validate(Workflow("w", "w", (ok,)))
    bad = step("inspect", StepKind.INSPECT_PAGE, {"browser": BROWSER, "include_text": "yes"})
    with pytest.raises(WorkflowValidationError, match="true or false"):
        WorkflowRunner.validate(Workflow("w2", "w2", (bad,)))


def test_selector_validation() -> None:
    bad = step("find", StepKind.FIND_PAGE_ELEMENT, {"browser": BROWSER, "selector": ""})
    with pytest.raises(WorkflowValidationError, match="needs a CSS selector"):
        WorkflowRunner.validate(Workflow("w", "w", (bad,)))
    long_sel = step(
        "find", StepKind.FIND_PAGE_ELEMENT, {"browser": BROWSER, "selector": "a" * 1000}
    )
    with pytest.raises(WorkflowValidationError, match="selector is too long"):
        WorkflowRunner.validate(Workflow("w2", "w2", (long_sel,)))
    scheme = step(
        "find",
        StepKind.FIND_PAGE_ELEMENT,
        {"browser": BROWSER, "selector": "[href*=javascript:]"},
    )
    with pytest.raises(WorkflowValidationError, match="forbidden scheme"):
        WorkflowRunner.validate(Workflow("w3", "w3", (scheme,)))


def test_interact_element_validation() -> None:
    ok = step("interact", StepKind.INTERACT_PAGE_ELEMENT, INTERACT_TARGET)
    WorkflowRunner.validate(Workflow("w", "w", (ok,)))
    type_ok = step("interact", StepKind.INTERACT_PAGE_ELEMENT, TYPE_TARGET)
    WorkflowRunner.validate(Workflow("w2", "w2", (type_ok,)))
    bad_interaction = step(
        "interact",
        StepKind.INTERACT_PAGE_ELEMENT,
        {"browser": BROWSER, "selector": "a", "interaction": "drag"},
    )
    with pytest.raises(WorkflowValidationError, match="must be one of"):
        WorkflowRunner.validate(Workflow("w3", "w3", (bad_interaction,)))
    type_missing = step(
        "interact",
        StepKind.INTERACT_PAGE_ELEMENT,
        {"browser": BROWSER, "selector": "a", "interaction": "type"},
    )
    with pytest.raises(WorkflowValidationError, match="needs text"):
        WorkflowRunner.validate(Workflow("w4", "w4", (type_missing,)))


def test_wait_page_conditions_validation() -> None:
    ok = step("wait", StepKind.WAIT_PAGE, WAIT_TARGET)
    WorkflowRunner.validate(Workflow("w", "w", (ok,)))
    empty = step("wait", StepKind.WAIT_PAGE, {"browser": BROWSER, "conditions": {}})
    with pytest.raises(WorkflowValidationError, match="conditions among"):
        WorkflowRunner.validate(Workflow("w2", "w2", (empty,)))
    bad_fields = step(
        "wait", StepKind.WAIT_PAGE, {"browser": BROWSER, "conditions": {"cookies": True}}
    )
    with pytest.raises(WorkflowValidationError, match="conditions among"):
        WorkflowRunner.validate(Workflow("w3", "w3", (bad_fields,)))
    bad_url = step(
        "wait",
        StepKind.WAIT_PAGE,
        {"browser": BROWSER, "conditions": {"url": "beispiel.com"}},
    )
    with pytest.raises(WorkflowValidationError, match="condition url"):
        WorkflowRunner.validate(Workflow("w4", "w4", (bad_url,)))


# ------------------------------------------------------------------- execution


def test_browser_flow_runs_through_provider_and_records_step_ids() -> None:
    actions = FakeBrowserActions()
    steps = (
        step("launch", StepKind.LAUNCH_BROWSER, {"application": "chrome"}),
        step("navigate", StepKind.NAVIGATE_BROWSER, NAVIGATE_TARGET),
        step("inspect", StepKind.INSPECT_PAGE, INSPECT_TARGET),
        step("wait", StepKind.WAIT_PAGE, WAIT_TARGET),
    )
    run, actions = run_with(actions, steps)
    assert run.status.value == "SUCCEEDED"
    assert [r.step_id for r in run.results] == ["launch", "navigate", "inspect", "wait"]
    kinds = [kind for kind, _ in actions.calls]
    assert kinds == ["LAUNCH_BROWSER", "NAVIGATE_BROWSER", "INSPECT_PAGE", "WAIT_PAGE"]


def test_missing_browser_provider_is_inconclusive() -> None:
    launch = WorkflowStep(
        "launch",
        "Launch",
        StepKind.LAUNCH_BROWSER,
        "Launched",
        target=json.dumps({"application": "chrome"}),
    )
    run = WorkflowRunner().run(Workflow("x", "x", (launch,)))
    assert run.status.value == "FAILED"
    assert run.results[0].status is StepStatus.INCONCLUSIVE
    assert "Nothing was changed in any browser" in run.results[0].message


def test_browser_failure_stops_following_steps() -> None:
    class FailingNavigate(FakeBrowserActions):
        def navigate(self, target_json: str):
            from engine.errors import ExecutionError

            raise ExecutionError("The page did not load.")

    actions = FailingNavigate()
    steps = (
        step("navigate", StepKind.NAVIGATE_BROWSER, NAVIGATE_TARGET),
        step("inspect", StepKind.INSPECT_PAGE, INSPECT_TARGET),
    )
    run, _ = run_with(actions, steps)
    assert run.status.value == "FAILED"
    assert run.results[0].status is StepStatus.FAILED
    assert run.results[1].status is StepStatus.SKIPPED


# ------------------------------------------------------------------- approvals


def test_read_only_policy_rejects_browser_mutations() -> None:
    navigate = step("nav", StepKind.NAVIGATE_BROWSER, NAVIGATE_TARGET)
    with pytest.raises(Exception, match="does not allow these step kinds"):
        ReplayExecutor().validate(Workflow("x", "x", (navigate,)))


def test_browser_reads_run_without_mutation_approval() -> None:
    inspect = step("inspect", StepKind.INSPECT_PAGE, INSPECT_TARGET)
    ReplayExecutor(DESKTOP_INTERACTION_POLICY).validate(Workflow("x", "x", (inspect,)))


def test_approval_gate_covers_browser_mutations() -> None:
    navigate = step("nav", StepKind.NAVIGATE_BROWSER, NAVIGATE_TARGET)
    approval = approve_desktop_workflow(Workflow("x", "x", (navigate,)))
    assert isinstance(approval.workflow.steps, tuple)
    assert StepKind.NAVIGATE_BROWSER in MUTATING_DESKTOP_KINDS


def test_browser_step_cancellation_before_a_pending_step() -> None:
    actions = FakeBrowserActions()
    launched = step("launch", StepKind.LAUNCH_BROWSER, {"application": "chrome"})
    next_step = step("nav2", StepKind.NAVIGATE_BROWSER, NAVIGATE_TARGET)
    # False before "launch" runs, True before "nav2" starts.
    checks = iter((False, True))
    run = WorkflowRunner().run(
        Workflow("cancel-flow", "Cancel flow", (launched, next_step)),
        cancel_check=lambda: next(checks),
        browser_actions=actions,
    )
    assert run.status is WorkflowStatus.CANCELLED
    assert run.results[0].status is StepStatus.SUCCEEDED
    assert run.results[1].status is StepStatus.SKIPPED
    assert [kind for kind, _ in actions.calls] == ["LAUNCH_BROWSER"]


def test_browser_mutating_steps_refuse_postconditions() -> None:
    from engine.workflow import PostconditionKind

    for kind, target in (
        (StepKind.LAUNCH_BROWSER, {"application": "chrome"}),
        (StepKind.NAVIGATE_BROWSER, NAVIGATE_TARGET),
        (StepKind.INTERACT_PAGE_ELEMENT, INTERACT_TARGET),
        (StepKind.VERIFY_FILE_TEXT, {"path": "x.txt", "contains": "hi"}),
    ):
        bad = WorkflowStep(
            "pc",
            "postcondition",
            kind,
            "desc",
            target=json.dumps(target),
            postcondition=PostconditionKind.PATH_EXISTS,
        )
        with pytest.raises(WorkflowValidationError, match="cannot carry a postcondition"):
            WorkflowRunner.validate(Workflow("p", "p", (bad,)))


def test_typed_text_is_never_recorded_in_evidence() -> None:
    """The result records a character count only; secret text stays out of evidence."""
    actions = FakeBrowserActions()
    typed = step("type", StepKind.INTERACT_PAGE_ELEMENT, TYPE_TARGET)
    run, _ = run_with(actions, (typed,))
    assert run.status is WorkflowStatus.SUCCEEDED
    recorded = run.results[0].message + " ".join(run.results[0].evidence)
    assert "hello" not in recorded
