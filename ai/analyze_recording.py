"""Optional cloud analysis of recorded observations (opt-in, fail-safe).

A configured provider receives ONLY the redacted draft action list (kinds,
plain-language descriptions, process names, and window titles) - never
screenshots, never raw keystroke text, never credentials - and must answer
with one workflow-steps JSON object. The answer is untrusted data: it is
re-serialized onto the versioned workflow schema and checked by the existing
strict validator (`storage.workflows.workflow_from_dict`), and every step kind
must belong to the engine's desktop interaction policy. Any missing key, HTTP
or output failure falls back to the deterministic local mapping, so a cloud
outage can only downgrade quality, never safety.

The prompt's method (event-first reconstruction, grounded past-tense actions,
an exact structured-output contract, and "say nothing outside the JSON"
discipline) is adapted from microsoft/skill-recorder's describer brief
(`electron/describer/instructions.ts`, MIT). See THIRD-PARTY-NOTICES.md.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable

from engine.errors import AIProviderError, WorkflowValidationError
from engine.replay import DESKTOP_INTERACTION_POLICY
from engine.workflow import StepKind
from recorder.drafts import RawDraft
from storage.workflows import SCHEMA_VERSION, workflow_from_dict

from .credentials import CredentialSource, configured_anthropic_key, configured_gemini_key
from .models import AnalysisRequest, ProviderDraft
from .provider import deterministic_recording_provider

ProviderName = str
#: Provider selected by ONCE_LLM_PROVIDER; default per product decision.
DEFAULT_PROVIDER: ProviderName = "gemini"
SUPPORTED_PROVIDERS: tuple[ProviderName, ...] = ("gemini", "anthropic")

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"

#: Model endpoints pinned as configuration constants, never inline in logic.
#: Verified 2026-11-04 from ai.google.dev/gemini-api/docs: current models docs
#: state new projects should use "3.5 Flash-Lite or 3.8 Flash" (the 2.5
#: generation routes to 3.5-flash-lite from 2026-12-01).
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

#: Verified 2026-11-04: current Anthropic lineup pins the fastest/cheapest
#: model as claude-haiku-5-5; https://platform.claude.com/docs/en/models/overview
ANTHROPIC_MODEL = "claude-haiku-5-5"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

API_KEY_ENV_VARS: dict[str, str] = {
    "gemini": GEMINI_API_KEY_ENV,
    "anthropic": ANTHROPIC_API_KEY_ENV,
}

MAX_PROMPT_ACTIONS = 200
MAX_PROMPT_CHARS = 20_000
MAX_DRAFT_STEPS = 20
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_OUTPUT_TOKENS = 2048

RemotePoster = Callable[[str, dict[str, str], bytes], bytes]


def analyze_recording(
    request: AnalysisRequest,
    *,
    provider: ProviderName | None = None,
    credentials: object | None = None,
    poster: RemotePoster | None = None,
) -> ProviderDraft:
    """Return an analyzed draft; on any failure return the local mapping."""
    selected = (provider or os.environ.get("ONCE_LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if selected not in SUPPORTED_PROVIDERS:
        return deterministic_recording_provider().analyze(request)
    if poster is None:
        poster = _default_poster
    try:
        answer_text = _request_analysis(
            selected, _read_api_key(selected, credentials), request, poster
        )
        draft = _provider_draft_from(answer_text, request.draft.recording_id)
        local_draft = deterministic_recording_provider().analyze(request)
        local_replayable = sum(
            1 for s in local_draft.workflow.steps if s.kind is not StepKind.REPORT
        )
        cloud_replayable = sum(1 for s in draft.workflow.steps if s.kind is not StepKind.REPORT)
        if local_replayable > cloud_replayable:
            return local_draft
        return draft
    except (
        AIProviderError,
        WorkflowValidationError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        OSError,
    ):
        # Expected condition, not an error to hide: any outage or invalid
        # answer degrades exactly to the deterministic local mapping.
        return deterministic_recording_provider().analyze(request)


def _read_api_key(provider: ProviderName, credentials: CredentialSource | None) -> str:
    """Read the provider key without logging or persisting it.

    Windows Credential Manager is the normal store; the environment variable
    named in the product requirement (GEMINI_API_KEY / ANTHROPIC_API_KEY) is
    the development fallback. Keys are read only here and used only in the
    request header of the fixed HTTPS endpoint.
    """
    if credentials is not None:
        key = credentials.get(API_KEY_ENV_VARS[provider])
        if not key:
            raise AIProviderError(f"No {provider} API key is configured.")
        return key
    configured = configured_gemini_key() if provider == "gemini" else configured_anthropic_key()
    if not configured:
        raise AIProviderError(f"No {provider} API key is configured.")
    return configured


def _request_analysis(
    provider: ProviderName,
    api_key: str,
    request: AnalysisRequest,
    poster: RemotePoster,
) -> str:
    """One structured HTTP round trip; raises instead of half-answering."""
    prompt = _build_prompt(request.draft)
    if provider == "gemini":
        url = f"{GEMINI_GENERATE_URL}/{GEMINI_MODEL}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": MAX_OUTPUT_TOKENS},
        }
    else:
        url = ANTHROPIC_MESSAGES_URL
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        body = {
            "model": ANTHROPIC_MODEL,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
    raw = poster(url, headers, json.dumps(body).encode("utf-8"))
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise AIProviderError("The provider answer was not an object.")
    text = _answer_text(provider, payload)
    if not text.strip():
        raise AIProviderError("The provider answer was empty.")
    return text


def _default_poster(url: str, headers: dict[str, str], body: bytes) -> bytes:
    """Fixed HTTPS endpoints only; data never goes anywhere else."""
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    if not url.startswith(
        ("https://generativelanguage.googleapis.com/", "https://api.anthropic.com/")
    ):
        raise AIProviderError("The analysis provider endpoint is not the configured one.")

    http_request = Request(url, data=body, headers=dict(headers), method="POST")  # noqa: S310
    # S310: the URL is always one of the fixed, allow-listed HTTPS endpoints above.
    try:
        with urlopen(http_request, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
            return response.read()
    except (HTTPError, URLError, OSError) as error:
        raise AIProviderError(f"The analysis provider could not be reached: {error}") from error


def _answer_text(provider: ProviderName, payload: dict) -> str:
    """Join the provider's text parts; both schemas are fixed endpoints."""
    if provider == "gemini":
        parts = payload.get("candidates", [])[0].get("content", {}).get("parts", [])
        return "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    blocks = payload.get("content", [])
    return "".join(
        block.get("text", "") for block in blocks if isinstance(block, dict) and "text" in block
    )


def _provider_draft_from(answer_text: str, recording_id: str) -> ProviderDraft:
    """Untrusted JSON -> strict, versioned workflow -> local draft object."""
    parsed = _parse_model_json(answer_text)
    goal = parsed.get("goal")
    workflow_data = parsed.get("workflow")
    if not isinstance(goal, str) or not goal.strip() or not isinstance(workflow_data, dict):
        raise AIProviderError("The provider answer is missing goal or workflow.")
    normalized = _normalize_workflow(recording_id, workflow_data)
    workflow = workflow_from_dict(normalized)
    if len(workflow.steps) > MAX_DRAFT_STEPS:
        raise AIProviderError("The provider proposed too many steps.")
    disallowed = sorted(
        step.kind.value
        for step in workflow.steps
        if isinstance(step.kind, StepKind)
        and step.kind not in DESKTOP_INTERACTION_POLICY.allowed_kinds
    )
    if disallowed:
        raise AIProviderError(f"The provider proposed step kinds outside the policy: {disallowed}.")
    return ProviderDraft(goal, workflow)


def _parse_model_json(text: str) -> dict:
    """Parse the answer's JSON object, tolerating one code fence."""
    trimmed = text.strip()
    if trimmed.startswith("```"):
        lines = trimmed.splitlines()
        trimmed = "\n".join(line for line in lines if not line.strip().startswith("```"))
    try:
        parsed = json.loads(trimmed)
    except json.JSONDecodeError:
        start, end = trimmed.find("{"), trimmed.rfind("}")
        if start < 0 or end <= start:
            raise AIProviderError("The provider answer was not a JSON object.") from None
        try:
            parsed = json.loads(trimmed[start : end + 1])
        except json.JSONDecodeError as error:
            raise AIProviderError("The provider answer was not a JSON object.") from error
    if not isinstance(parsed, dict):
        raise AIProviderError("The provider answer was not a JSON object.")
    return parsed


def _normalize_workflow(recording_id: str, workflow_data: dict) -> dict:
    """Reshape the untrusted draft onto v3 with defaults; validator stays strict."""
    steps = workflow_data.get("steps")
    if not isinstance(steps, list):
        raise AIProviderError("The provider's workflow has no step list.")
    normalized_steps: list[dict] = []
    for index, raw in enumerate(steps, start=1):
        if not isinstance(raw, dict):
            raise AIProviderError("Every proposed step must be an object.")
        kind = raw.get("kind")
        target = raw.get("target")
        normalized_steps.append(
            {
                "step_id": raw.get("step_id") or f"step-{index}",
                "name": raw.get("name") or f"Step {index}",
                "kind": kind,
                "message": raw.get("message") or "",
                "target": target if isinstance(target, str) or target is None else None,
                "max_attempts": raw.get("max_attempts", 1),
                "postcondition": None,
                "timeout_seconds": raw.get("timeout_seconds", 10.0),
            }
        )
    workflow_id = workflow_data.get("workflow_id")
    name = workflow_data.get("name")
    return {
        "schema_version": SCHEMA_VERSION,
        "workflow_id": (
            workflow_id
            if isinstance(workflow_id, str) and workflow_id.strip()
            else f"recording-{recording_id}"
        ),
        "name": name if isinstance(name, str) and name.strip() else "Recorded task draft",
        "steps": normalized_steps,
    }


def _action_metadata_tag(action: object) -> str:
    parts: list[str] = []
    exe = getattr(action, "executable_path", None)
    if exe:
        parts.append(f"executable={exe}")
    win = getattr(action, "window_title", None)
    if win:
        parts.append(f"window={win}")
    elem = getattr(action, "element", None)
    if elem is not None:
        elem_dict = {
            k: v
            for k, v in (
                ("control_type", getattr(elem, "control_type", None)),
                ("name", getattr(elem, "name", None)),
                ("automation_id", getattr(elem, "automation_id", None)),
                ("class_name", getattr(elem, "class_name", None)),
            )
            if v
        }
        if elem_dict:
            parts.append(f"element={json.dumps(elem_dict, sort_keys=True)}")
    key = getattr(action, "key", None)
    if key:
        parts.append(f"key={key}")
    text = getattr(action, "text", None)
    if text:
        parts.append(f"text={json.dumps(text)}")
    return f" [{' ; '.join(parts)}]" if parts else ""


def _build_prompt(draft: RawDraft) -> str:
    """Event-first analysis brief over the redacted observation list only."""
    event_lines = [
        f"{action.sequence}. {action.source_event.value}: {action.description}"
        + _action_metadata_tag(action)
        for action in list(draft.actions)[:MAX_PROMPT_ACTIONS]
    ]
    while len("\n".join(event_lines)) > MAX_PROMPT_CHARS and len(event_lines) > 1:
        event_lines.pop()
    events_block = "\n".join(event_lines) if event_lines else "(no actions were captured)"
    return ANALYSIS_PROMPT.format(events_block=events_block)


ANALYSIS_PROMPT = """You reconstruct what a user did during a short desktop
recording session and turn it into a draft automation. Work only from the
event list below; do not speculate about anything else on the screen.

Method:
1. Read the event list and form the overall intent in one sentence (the goal).
2. Ground every step in the events; rewrite actions in past tense ("Opened",
   "Clicked", "Typed", "Pressed", "Closed"). Never invent applications, paths,
   or buttons that are not in the events.
3. Choose step kinds ONLY from this allowlist, with the exact target shapes:
   - LAUNCH_APPLICATION: target JSON
     {{"executable": "<exact executable path from WINDOW_OPEN event>"}}
   - CLICK_UI_ELEMENT: target JSON
     {{"window": {{"title": "<window title>"}},
       "element": {{"class_name": "<class>", "control_type": "<type>", "name": "<name>"}},
       "interaction": "invoke"}}
     (use "toggle" when control_type is CheckBox, and include automation_id when
      shown in [element=...]).
   - TYPE_TEXT: target JSON
     {{"window": {{"title": "<window title>"}},
       "element": {{"class_name": "<class>", "control_type": "<type>"}},
       "text": "<typed text>"}}
   - PRESS_SHORTCUT: target JSON
     {{"window": {{"title": "<window title>"}}, "keys": "<key name>"}}
   - CLOSE_APPLICATION: target JSON {{"executable": "<exact executable path>"}};
     only for an application that an earlier step in this workflow launched.
   - REPORT: plain observation or note; no target.
4. Every step needs step_id, name, kind, message, target (message is a plain
   sentence). Keep the number of steps SMALL: launch once, not per window.

Say nothing outside the JSON. Answer with exactly one JSON object:
{{
  "goal": "<one sentence>",
  "workflow": {{
    "workflow_id": "<short-id>",
    "name": "<short title in Title Case>",
    "steps": [
      {{"step_id": "s1", "name": "Open application", "kind": "LAUNCH_APPLICATION",
        "message": "Launch application.",
        "target": "{{\\"executable\\": \\"<exact executable path>\\"}}"}}
    ]
  }}
}}

Recorded events (sequence, kind, description):
{events_block}
"""
