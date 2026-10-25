"""Engine-level tests for the desktop automation steps (fake provider)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.desktop import (
    DesktopApproval,
    approve_desktop_workflow,
    mutating_kind_names,
    requires_desktop_approval,
)
from engine.errors import ExecutionError, WorkflowValidationError
from engine.replay import (
    DESKTOP_INTERACTION_POLICY,
    MUTATING_DESKTOP_KINDS,
    READ_ONLY_POLICY,
    ReplayExecutor,
)
from engine.workflow import (
    StepKind,
    StepStatus,
    Workflow,
    WorkflowRunner,
    WorkflowStep,
)

WINDOW = {"title": "Once demo", "class_name": "DemoWindowClass"}
TYPE_TARGET = {
    "window": WINDOW,
    "element": {"class_name": "DemoEditClass", "control_type": "Edit"},
    "text": "hello once",
}
CLICK_TARGET = {
    "window": WINDOW,
    "element": {"automation_id": "okButton", "control_type": "Button"},
}
LAUNCH_TARGET = {"application": "notepad"}
SHORTCUT_TARGET = {"window": WINDOW, "keys": "ctrl+s"}


class FakeDesktopActions:
    """Deterministic provider: records targets, returns scripted results."""

    def __init__(self, script: dict[str, object] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.scripted: dict[str, object] = script or {}

    def _result(self, kind: str, message: str, status=StepStatus.SUCCEEDED, evidence=()):
        return self.scripted.get(kind, (status, message, evidence))

    def launch_application(self, target_json: str):
        self.calls.append(("LAUNCH_APPLICATION", target_json))
        status, message, evidence = self._result(
            "LAUNCH_APPLICATION", "The application was launched."
        )
        return make_result(status, message, evidence)

    def wait_window(self, target_json: str, timeout_seconds: float):
        self.calls.append(("WAIT_WINDOW", target_json))
        status, message, evidence = self._result("WAIT_WINDOW", "The identified window appeared.")
        return make_result(status, message, evidence)

    def click_element(self, target_json: str):
        self.calls.append(("CLICK_UI_ELEMENT", target_json))
        status, message, evidence = self._result(
            "CLICK_UI_ELEMENT", "The element interaction was performed (invoke)."
        )
        return make_result(status, message, evidence)

    def type_text(self, target_json: str):
        self.calls.append(("TYPE_TEXT", target_json))
        status, message, evidence = self._result("TYPE_TEXT", "The text was entered.")
        return make_result(status, message, evidence)

    def press_shortcut(self, target_json: str):
        self.calls.append(("PRESS_SHORTCUT", target_json))
        status, message, evidence = self._result("PRESS_SHORTCUT", "The shortcut was sent.")
        return make_result(status, message, evidence)


def make_result(status, message, evidence=()):
    from engine.workflow import StepResult

    return StepResult(step_id="", status=status, message=message, evidence=evidence)


def desktop_step(step_id: str, kind: StepKind, target: str, **kw) -> tuple[str, WorkflowStep]:
    return (
        step_id,
        WorkflowStep(
            step_id,
            step_id.replace("-", " "),
            kind,
            kw.pop("message", kind.value),
            target=target,
            **kw,
        ),
    )


def run_with_fakes(steps: tuple[WorkflowStep, ...], actions=None, *, root=None):
    if actions is None:
        actions = FakeDesktopActions()
    workflow = Workflow("desktop-demo", "Desktop demo", steps)
    runner = WorkflowRunner()
    run = runner.run(workflow, allowed_root=root, desktop_actions=actions)
    return run, actions


def test_read_only_policy_rejects_mutating_desktop_steps() -> None:
    """Unapproved replay must refuse every mutating desktop step kind."""
    launch = desktop_step("launch", StepKind.LAUNCH_APPLICATION, json.dumps(LAUNCH_TARGET))[1]
    workflow = Workflow("x", "x", (launch,))
    with pytest.raises(ExecutionError, match="does not allow these step kinds"):
        ReplayExecutor().validate(workflow)  # default policy = read-only


def test_desktop_policy_allows_and_media_pixels_nothing_unapproved() -> None:
    launch = desktop_step("launch", StepKind.LAUNCH_APPLICATION, json.dumps(LAUNCH_TARGET))[1]
    ReplayExecutor(DESKTOP_INTERACTION_POLICY).validate(Workflow("x", "x", (launch,)))


def test_launch_validation_rejects_shell_style_and_relative_executables() -> None:
    bad_relative = desktop_step(
        "s1", StepKind.LAUNCH_APPLICATION, json.dumps({"executable": "notepad.exe"})
    )[1]
    with pytest.raises(WorkflowValidationError, match="absolute path"):
        WorkflowRunner.validate(Workflow("w", "w", (bad_relative,)))

    bad_suffix = desktop_step(
        "s2",
        StepKind.LAUNCH_APPLICATION,
        json.dumps({"executable": "C:\\tmp\\evil.bat"}),
    )[1]
    with pytest.raises(WorkflowValidationError, match=r"must be a \.exe"):
        WorkflowRunner.validate(Workflow("w2", "w2", (bad_suffix,)))

    unknown_app = desktop_step(
        "s3", StepKind.LAUNCH_APPLICATION, json.dumps({"application": "cmd.exe"})
    )[1]
    with pytest.raises(WorkflowValidationError, match="registry does not allow"):
        WorkflowRunner.validate(Workflow("w3", "w3", (unknown_app,)))

    both = desktop_step(
        "s4",
        StepKind.LAUNCH_APPLICATION,
        json.dumps({"application": "notepad", "executable": "C:\\Windows\\notepad.exe"}),
    )[1]
    with pytest.raises(WorkflowValidationError, match="exactly one"):
        WorkflowRunner.validate(Workflow("w4", "w4", (both,)))

    too_many_args = desktop_step(
        "s5",
        StepKind.LAUNCH_APPLICATION,
        json.dumps({"application": "notepad", "arguments": ["a"] * (16 + 1)}),
    )[1]
    with pytest.raises(WorkflowValidationError, match="arguments"):
        WorkflowRunner.validate(Workflow("w5", "w5", (too_many_args,)))


def test_shortcut_validation_allows_only_listed_combinations() -> None:
    allowed = desktop_step("s", StepKind.PRESS_SHORTCUT, json.dumps(SHORTCUT_TARGET))[1]
    WorkflowRunner.validate(Workflow("w", "w", (allowed,)))
    alt_f4 = desktop_step(
        "s2", StepKind.PRESS_SHORTCUT, json.dumps({**SHORTCUT_TARGET, "keys": "alt+f4"})
    )[1]
    with pytest.raises(WorkflowValidationError, match="only allows these key combinations"):
        WorkflowRunner.validate(Workflow("w2", "w2", (alt_f4,)))


def test_type_text_validation_bounds_and_required_fields() -> None:
    ok = desktop_step("s", StepKind.TYPE_TEXT, json.dumps(TYPE_TARGET))[1]
    WorkflowRunner.validate(Workflow("w", "w", (ok,)))

    no_text = desktop_step("s2", StepKind.TYPE_TEXT, json.dumps({**TYPE_TARGET, "text": ""}))[1]
    with pytest.raises(WorkflowValidationError, match="needs text"):
        WorkflowRunner.validate(Workflow("w2", "w2", (no_text,)))

    long_text = desktop_step(
        "s3", StepKind.TYPE_TEXT, json.dumps({**TYPE_TARGET, "text": "x" * 501})
    )[1]
    with pytest.raises(WorkflowValidationError, match="too long"):
        WorkflowRunner.validate(Workflow("w3", "w3", (long_text,)))

    no_id_or_class = desktop_step(
        "s4",
        StepKind.TYPE_TEXT,
        json.dumps(
            {
                "window": WINDOW,
                "element": {"control_type": "Edit"},
                "text": "hello",
            }
        ),
    )[1]
    with pytest.raises(WorkflowValidationError, match="automation_id or class_name"):
        WorkflowRunner.validate(Workflow("w4", "w4", (no_id_or_class,)))


def test_timeout_bounds_are_enforced() -> None:
    ok = desktop_step("s", StepKind.WAIT_WINDOW, json.dumps(WINDOW), timeout_seconds=60.0)[1]
    WorkflowRunner.validate(Workflow("w", "w", (ok,)))
    too_short = desktop_step("s2", StepKind.WAIT_WINDOW, json.dumps(WINDOW), timeout_seconds=0.1)[1]
    with pytest.raises(WorkflowValidationError, match=r"between 0\.5 and 60"):
        WorkflowRunner.validate(Workflow("w2", "w2", (too_short,)))
    too_long = desktop_step("s3", StepKind.WAIT_WINDOW, json.dumps(WINDOW), timeout_seconds=120)[1]
    with pytest.raises(WorkflowValidationError, match=r"between 0\.5 and 60"):
        WorkflowRunner.validate(Workflow("w3", "w3", (too_long,)))


def test_postcondition_on_desktop_step_is_refused() -> None:
    from engine.workflow import PostconditionKind

    for kind in (StepKind.TYPE_TEXT, StepKind.LAUNCH_APPLICATION):
        target = json.dumps(TYPE_TARGET if kind is StepKind.TYPE_TEXT else LAUNCH_TARGET)
        bad = WorkflowStep(
            "s",
            "s",
            kind,
            kind.value,
            target=target,
            postcondition=PostconditionKind.PATH_EXISTS,
        )
        with pytest.raises(WorkflowValidationError, match="cannot carry a postcondition"):
            WorkflowRunner.validate(Workflow("w", "w", (bad,)))


def test_full_desktop_flow_runs_with_provider_and_records_step_ids() -> None:
    actions = FakeDesktopActions()
    steps = (
        desktop_step("launch", StepKind.LAUNCH_APPLICATION, json.dumps(LAUNCH_TARGET))[1],
        desktop_step("wait", StepKind.WAIT_WINDOW, json.dumps(WINDOW))[1],
        desktop_step("type", StepKind.TYPE_TEXT, json.dumps(TYPE_TARGET))[1],
        desktop_step("press", StepKind.PRESS_SHORTCUT, json.dumps(SHORTCUT_TARGET))[1],
    )
    run, actions = run_with_fakes(steps, actions)
    assert run.status.value == "SUCCEEDED"
    assert [result.step_id for result in run.results] == ["launch", "wait", "type", "press"]
    kinds_called = [kind for kind, _ in actions.calls]
    assert kinds_called == ["LAUNCH_APPLICATION", "WAIT_WINDOW", "TYPE_TEXT", "PRESS_SHORTCUT"]


def test_provider_failure_stops_following_steps() -> None:
    actions = FakeDesktopActions(
        script={"TYPE_TEXT": (StepStatus.FAILED, "The element is disabled.", ())}
    )
    steps = (
        desktop_step("launch", StepKind.LAUNCH_APPLICATION, json.dumps(LAUNCH_TARGET))[1],
        desktop_step("type", StepKind.TYPE_TEXT, json.dumps(TYPE_TARGET))[1],
        desktop_step("press", StepKind.PRESS_SHORTCUT, json.dumps(SHORTCUT_TARGET))[1],
    )
    run, _ = run_with_fakes(steps, actions)
    assert run.status.value == "FAILED"
    assert run.results[1].status is StepStatus.FAILED
    assert "disabled" in run.results[1].message
    assert run.results[2].status is StepStatus.SKIPPED


def test_missing_provider_is_inconclusive_not_executed() -> None:
    """Without a provider nothing runs and nothing changes on the desktop."""
    launch = desktop_step("launch", StepKind.LAUNCH_APPLICATION, json.dumps(LAUNCH_TARGET))[1]
    run = WorkflowRunner().run(Workflow("x", "x", (launch,)))
    assert run.status.value == "FAILED"
    assert run.results[0].status is StepStatus.INCONCLUSIVE


def test_verify_file_text_checks_bounded_content_inside_root(tmp_path: Path) -> None:
    """Text verification reads only inside the authorized root and bounded sizes."""
    target = tmp_path / "result.txt"
    target.write_text("Once automated this file\n", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("Once automated this file\n", encoding="utf-8")
    outside = Path(tmp_path.parent) / "outside.txt"

    verify = desktop_step(
        "verify",
        StepKind.VERIFY_FILE_TEXT,
        json.dumps({"path": str(target), "contains": "automated"}),
    )[1]
    run, _ = run_with_fakes((verify,), root=tmp_path)
    assert run.results[0].status is StepStatus.VERIFIED
    assert "match=true" in "".join(run.results[0].evidence)

    wrong_contains = desktop_step(
        "verify2",
        StepKind.VERIFY_FILE_TEXT,
        json.dumps({"path": str(target), "contains": "absent"}),
    )[1]
    run2, _ = run_with_fakes((wrong_contains,), root=tmp_path)
    assert run2.results[0].status is StepStatus.FAILED
    assert "match=false" in "".join(run2.results[0].evidence)

    outside_target = desktop_step(
        "verify3",
        StepKind.VERIFY_FILE_TEXT,
        json.dumps({"path": str(outside), "contains": "automated"}),
    )[1]
    run3, _ = run_with_fakes((outside_target,), root=tmp_path)
    assert run3.results[0].status is StepStatus.FAILED
    assert "outside" in run3.results[0].message


def test_pubsub_cancellation_skips_remaining_desktop_steps() -> None:
    """A cancellation before a pending desktop step skips it cleanly."""
    launched: list[str] = []
    actions = FakeDesktopActions()
    original_launch = actions.launch_application

    def count_launch(target_json: str):
        launched.append(target_json)
        return original_launch(target_json)

    actions.launch_application = count_launch  # type: ignore[method-assign]
    steps = (
        desktop_step("launch", StepKind.LAUNCH_APPLICATION, json.dumps(LAUNCH_TARGET))[1],
        desktop_step("wait", StepKind.WAIT_WINDOW, json.dumps(WINDOW))[1],
    )
    run = WorkflowRunner().run(
        Workflow("cancel", "cancel", steps), desktop_actions=actions, cancel_check=lambda: True
    )
    assert run.status.value == "CANCELLED"
    assert launched == []  # a pre-set cancellation stops before the first action


def test_approval_gate_records_the_exact_workflow() -> None:
    steps = (desktop_step("type", StepKind.TYPE_TEXT, json.dumps(TYPE_TARGET))[1],)
    approval = approve_desktop_workflow(Workflow("gate", "gate", steps))
    assert isinstance(approval, DesktopApproval)
    assert approval.workflow.steps == steps
    assert mutating_kind_names(approval.workflow) == ("TYPE_TEXT",)
    assert requires_desktop_approval(approval.workflow) is True


def test_approval_gate_refuses_invalid_desktop_workflows() -> None:
    bad = desktop_step(
        "s", StepKind.PRESS_SHORTCUT, json.dumps({**SHORTCUT_TARGET, "keys": "ctrl+q"})
    )[1]
    with pytest.raises(WorkflowValidationError):
        approve_desktop_workflow(Workflow("x", "x", (bad,)))


def test_mutating_kinds_constant_covers_the_four_mutations() -> None:
    assert frozenset(
        {
            StepKind.LAUNCH_APPLICATION,
            StepKind.CLICK_UI_ELEMENT,
            StepKind.TYPE_TEXT,
            StepKind.PRESS_SHORTCUT,
        }
    ) == MUTATING_DESKTOP_KINDS
    # read-only kinds are never part of the approval gate
    assert StepKind.WAIT_WINDOW not in MUTATING_DESKTOP_KINDS
    assert StepKind.VERIFY_FILE_TEXT not in MUTATING_DESKTOP_KINDS
    assert StepKind.WAIT_WINDOW in READ_ONLY_POLICY.allowed_kinds
    assert StepKind.VERIFY_FILE_TEXT in READ_ONLY_POLICY.allowed_kinds


def test_window_identity_allows_process_and_class_without_a_title() -> None:
    """Title-free identification is valid for windows whose title changes."""
    from engine.workflow import StepKind as Kind

    identity = {"process_id": 4321, "class_name": "Notepad"}
    step = WorkflowStep(
        "s",
        "Save",
        Kind.PRESS_SHORTCUT,
        "Saved.",
        target=json.dumps({"window": identity, "keys": "ctrl+s"}),
    )
    WorkflowRunner.validate(Workflow("w", "w", (step,)))


def test_window_identity_requires_some_identifier() -> None:
    from engine.errors import WorkflowValidationError

    step = WorkflowStep(
        "s",
        "Wait",
        StepKind.WAIT_WINDOW,
        "Waited.",
        target=json.dumps({}),
    )
    with pytest.raises(
        WorkflowValidationError, match="title, process ID, or class name"
    ):
        WorkflowRunner.validate(Workflow("w", "w", (step,)))


def test_verify_file_text_may_carry_a_path_postcondition(tmp_path: Path) -> None:
    from engine.errors import WorkflowValidationError
    from engine.workflow import PostconditionKind

    """Postconditions stay on plain-path steps; VERIFY_FILE_TEXT proves its own existence."""
    target = tmp_path / "note.txt"
    target.write_text("Once automated this file\n", encoding="utf-8")
    verify = WorkflowStep(
        "verify",
        "Verify",
        StepKind.VERIFY_FILE_TEXT,
        "Verified.",
        target=json.dumps({"path": str(target), "contains": "automated"}),
        postcondition=PostconditionKind.PATH_EXISTS,
    )
    with pytest.raises(WorkflowValidationError, match="cannot carry a postcondition"):
        WorkflowRunner.validate(Workflow("w", "w", (verify,)))
