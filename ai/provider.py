"""Provider protocol and deterministic fake implementation."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from engine.errors import AIProviderError, WorkflowValidationError
from engine.workflow import (
    ALLOWED_SHORTCUTS,
    StepKind,
    Workflow,
    WorkflowRunner,
    WorkflowStep,
)
from recorder.drafts import RawDraftAction
from recorder.models import RecordedEventKind, UIElementInfo

from .models import AnalysisRequest, ProviderDraft, ProviderQuestion, ProviderResponse

_CLICKABLE_CONTROLS = frozenset(
    {
        "Button",
        "MenuItem",
        "CheckBox",
        "RadioButton",
        "ListItem",
        "TabItem",
        "Hyperlink",
        "TreeItem",
        "SplitButton",
        "HeaderItem",
    }
)
_TEXT_CONTROLS = frozenset({"Edit", "Document", "ComboBox"})

OS_SHELL_PROCESSES = frozenset(
    {
        "startmenuexperiencehost.exe",
        "applicationframehost.exe",
        "shellexperiencehost.exe",
        "searchhost.exe",
        "textinputhost.exe",
        "systemsettings.exe",
        "explorer.exe",
    }
)

MAX_INTERVIEW_TURNS = 5


class AnalysisProvider(Protocol):
    """Analyze a recording and return one bounded question or draft."""

    def analyze(self, request: AnalysisRequest) -> ProviderResponse:
        """Return a proposal without executing any workflow step."""


class FakeAnalysisProvider:
    """Deterministic provider used by tests and offline demonstrations."""

    def __init__(self, responses: Sequence[ProviderResponse]) -> None:
        self._responses = tuple(responses)
        self._index = 0

    def analyze(self, request: AnalysisRequest) -> ProviderResponse:
        """Return the next configured response and reject unbounded interviews."""
        if len(request.conversation) > MAX_INTERVIEW_TURNS:
            raise AIProviderError("The AI interview reached its question limit.")
        if self._index >= len(self._responses):
            raise AIProviderError("The fake provider has no response configured.")
        response = self._responses[self._index]
        self._index += 1
        if isinstance(response, ProviderDraft):
            try:
                WorkflowRunner.validate(response.workflow)
            except WorkflowValidationError as error:
                raise AIProviderError("The provider returned an invalid workflow draft.") from error
        return response


def deterministic_demo_provider() -> FakeAnalysisProvider:
    """Return an offline provider that proposes a real, validated workflow."""
    return FakeAnalysisProvider(
        (
            ProviderQuestion("What result should confirm that this task succeeded?"),
            ProviderDraft(
                goal="Record the observed task",
                workflow=Workflow(
                    "recorded-task",
                    "Recorded task",
                    (
                        WorkflowStep(
                            "summary",
                            "Summarize observation",
                            StepKind.REPORT,
                            "Review the recorded task before approval.",
                        ),
                        WorkflowStep(
                            "verify",
                            "Verify recorded output",
                            StepKind.VERIFY_PATH_EXISTS,
                            "Confirm the recorded output exists.",
                            "C:/work/recorded.txt",
                        ),
                    ),
                ),
            ),
        ),
    )


def deterministic_recording_provider() -> AnalysisProvider:
    """Return a local provider that maps observations into engine step drafts."""

    class RecordingProvider:
        def analyze(self, request: AnalysisRequest) -> ProviderDraft:
            steps: list[WorkflowStep] = []
            launched: set[str] = set()
            actions = request.draft.actions
            for index, action in enumerate(actions, start=1):
                steps.append(_step_for_action(action, index, launched, actions))
            workflow = Workflow(
                workflow_id=f"recording-{request.draft.recording_id}",
                name="Recorded task draft",
                steps=tuple(steps)
                or (
                    WorkflowStep(
                        step_id="observation-empty",
                        name="No actions captured",
                        kind=StepKind.REPORT,
                        message="No usable actions were captured. Record the task again.",
                    ),
                ),
            )
            WorkflowRunner.validate(workflow)
            return ProviderDraft(
                goal="Review the recorded observations and turn them into safe steps.",
                workflow=workflow,
            )

    return RecordingProvider()


def _is_flapping_or_title_change(
    action: RawDraftAction,
    actions: Sequence[RawDraftAction],
    index: int,
) -> bool:
    """True if this WINDOW_CLOSE was caused by title changes or flapping rather than real close."""
    exec_path = _recorded_executable(action)
    if not exec_path:
        return False
    target_name = Path(exec_path).name.lower()

    # 1. If the app is opened again later in the recording, earlier closes were not genuine closes
    for other in actions[index:]:
        other_exec = _recorded_executable(other)
        if (
            other_exec
            and Path(other_exec).name.lower() == target_name
            and other.source_event is RecordedEventKind.WINDOW_OPEN
        ):
            return True

    # 2. If close is paired with an open of the same executable (title transition):
    start = max(0, index - 3)
    end = min(len(actions), index + 2)
    for i, other in enumerate(actions[start:end], start=start):
        if i == index - 1:
            continue
        other_exec = _recorded_executable(other)
        if (
            other_exec
            and Path(other_exec).name.lower() == target_name
            and other.source_event is RecordedEventKind.WINDOW_OPEN
            and other.window_title != action.window_title
        ):
            return True

    return False


def _recorded_executable(action: RawDraftAction) -> str | None:
    """The executable path the recording captured for this action, if it has one.

    The recording is the only source of application identity: Once never maps a
    process name to an application it happens to know. Without a recorded path
    the observation is kept for review and no launch or close is proposed.
    """
    for attr in ("executable_path", "executable"):
        recorded = getattr(action, attr, None)
        if isinstance(recorded, str) and recorded.strip():
            return recorded.strip()
    return None


def _step_for_action(
    action: RawDraftAction,
    index: int,
    launched: set[str],
    all_actions: Sequence[RawDraftAction] = (),
) -> WorkflowStep:
    """Turn one observation into a validated engine step deterministically."""
    step_id = f"observation-{action.sequence}"
    name = f"Observation {index}"
    executable = _recorded_executable(action)
    exe_name = Path(executable).name.lower() if executable else ""
    if action.source_event is RecordedEventKind.WINDOW_OPEN:
        if executable is None:
            return WorkflowStep(
                step_id,
                name,
                StepKind.REPORT,
                f"{action.description} (executable path not recorded)",
            )
        if exe_name in OS_SHELL_PROCESSES:
            return WorkflowStep(
                step_id,
                name,
                StepKind.REPORT,
                f"{action.description} (OS shell process ignored for application lifecycle)",
            )
        if executable not in launched:
            launched.add(executable)
            return WorkflowStep(
                step_id,
                name,
                StepKind.LAUNCH_APPLICATION,
                f"Launch {Path(executable).stem}.",
                target=json.dumps({"executable": executable}),
            )
        return WorkflowStep(
            step_id,
            name,
            StepKind.REPORT,
            f"{action.description} The application is already part of this draft.",
        )
    if action.source_event is RecordedEventKind.WINDOW_CLOSE:
        if executable is None:
            return WorkflowStep(
                step_id,
                name,
                StepKind.REPORT,
                f"{action.description} (executable path not recorded)",
            )
        if exe_name in OS_SHELL_PROCESSES:
            return WorkflowStep(
                step_id,
                name,
                StepKind.REPORT,
                f"{action.description} (OS shell process ignored for application lifecycle)",
            )
        if _is_flapping_or_title_change(action, all_actions, index):
            return WorkflowStep(
                step_id,
                name,
                StepKind.REPORT,
                f"{action.description} (Window title change observation; not an application close)",
            )
        if executable in launched:
            return WorkflowStep(
                step_id,
                name,
                StepKind.CLOSE_APPLICATION,
                f"Close {Path(executable).stem}.",
                target=json.dumps({"executable": executable}),
            )
        return WorkflowStep(
            step_id,
            name,
            StepKind.REPORT,
            (
                f"{action.description} This draft does not launch "
                f"{Path(executable).stem}, so nothing is allowed to close it."
            ),
        )
    if action.source_event is RecordedEventKind.WINDOW_TITLE_CHANGED:
        return WorkflowStep(step_id, name, StepKind.REPORT, action.description)
    if action.source_event is RecordedEventKind.MOUSE_CLICK:
        element = getattr(action, "element", None)
        auto_id = getattr(element, "automation_id", None) or ""
        if auto_id.strip() == "Close" and executable in launched:
            return WorkflowStep(step_id, name, StepKind.REPORT, action.description)
        click_step = _semantic_click_step(action, step_id, name)
        if click_step is not None:
            return click_step
    if action.source_event is RecordedEventKind.TEXT_INPUT:
        type_step = _semantic_type_step(action, step_id, name)
        if type_step is not None:
            return type_step
    if action.source_event is RecordedEventKind.KEY_PRESS:
        shortcut_step = _semantic_shortcut_step(action, step_id, name)
        if shortcut_step is not None:
            return shortcut_step
    return WorkflowStep(step_id, name, StepKind.REPORT, action.description)


def _element_target_dict(element: UIElementInfo) -> dict[str, str] | None:
    """Build a validated UIA element selector dict from element identity fields."""
    auto_id = (element.automation_id or "").strip()
    cls_name = (element.class_name or "").strip()
    elem_name = (element.name or "").strip()
    if not auto_id and not cls_name and not elem_name:
        return None
    result: dict[str, str] = {}
    if auto_id:
        result["automation_id"] = auto_id
    if element.control_type and element.control_type.strip():
        result["control_type"] = element.control_type.strip()
    if cls_name:
        result["class_name"] = cls_name
    if not auto_id and elem_name:
        result["name"] = elem_name
    return result


def _semantic_click_step(
    action: RawDraftAction, step_id: str, fallback_name: str
) -> WorkflowStep | None:
    """Convert a UIA-identified control click into CLICK_UI_ELEMENT."""
    window_title = (getattr(action, "window_title", None) or "").strip()
    element = getattr(action, "element", None)
    if not window_title or not isinstance(element, UIElementInfo):
        return None
    if element.control_type not in _CLICKABLE_CONTROLS:
        return None
    elem_dict = _element_target_dict(element)
    if elem_dict is None:
        return None
    if element.control_type in ("CheckBox", "RadioButton"):
        interaction = "toggle"
    elif element.control_type in ("ListItem", "TabItem", "TreeItem"):
        interaction = "select"
    else:
        interaction = "invoke"
    auto_id = (element.automation_id or "").strip()
    label = (element.name or element.automation_id or element.class_name or "control").strip()
    close_keywords = ("close", "fermer", "fermer paramètres", "fermer la fenêtre")
    if auto_id == "Close" or label.lower() in close_keywords:
        step_name = f"Close {window_title}"
    else:
        step_name = f"Click {label}"[:80] if label else fallback_name
    target = json.dumps(
        {
            "window": {"title": window_title},
            "element": elem_dict,
            "interaction": interaction,
        }
    )
    return WorkflowStep(
        step_id,
        step_name,
        StepKind.CLICK_UI_ELEMENT,
        f"Click {element.control_type} '{label}' in {window_title}."[:500],
        target=target,
    )


def _semantic_type_step(
    action: RawDraftAction, step_id: str, fallback_name: str
) -> WorkflowStep | None:
    """Convert non-password UIA text entry into TYPE_TEXT."""
    window_title = (getattr(action, "window_title", None) or "").strip()
    element = getattr(action, "element", None)
    text = getattr(action, "text", None)
    if (
        not window_title
        or not isinstance(element, UIElementInfo)
        or element.is_password
        or element.control_type not in _TEXT_CONTROLS
        or not isinstance(text, str)
        or not text
    ):
        return None
    elem_dict = _element_target_dict(element)
    if elem_dict is None:
        return None
    bounded_text = text[:500]
    label = (element.name or element.automation_id or element.control_type or "field").strip()
    step_name = f"Type in {label}"[:80] if label else fallback_name
    target = json.dumps(
        {
            "window": {"title": window_title},
            "element": elem_dict,
            "text": bounded_text,
        }
    )
    return WorkflowStep(
        step_id,
        step_name,
        StepKind.TYPE_TEXT,
        f"Enter text into '{label}' in {window_title}."[:500],
        target=target,
    )


def _semantic_shortcut_step(
    action: RawDraftAction, step_id: str, fallback_name: str
) -> WorkflowStep | None:
    """Convert an allowlisted shortcut in a known window into PRESS_SHORTCUT."""
    window_title = (getattr(action, "window_title", None) or "").strip()
    key = (getattr(action, "key", None) or "").strip().lower()
    if not window_title or key not in ALLOWED_SHORTCUTS:
        return None
    step_name = f"Press {key.upper()}"[:80] if key else fallback_name
    target = json.dumps(
        {
            "window": {"title": window_title},
            "keys": key,
        }
    )
    return WorkflowStep(
        step_id,
        step_name,
        StepKind.PRESS_SHORTCUT,
        f"Send shortcut {key} to {window_title}."[:500],
        target=target,
    )
