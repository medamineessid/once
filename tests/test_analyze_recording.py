"""Tests for opt-in cloud recording analysis (fake transport, no network)."""

from __future__ import annotations

import json
import sys

from ai.analyze_recording import (
    GEMINI_MODEL,
    analyze_recording,
)
from ai.models import AnalysisRequest, ProviderDraft
from engine.workflow import StepKind
from recorder.drafts import RawDraft, RawDraftAction
from recorder.models import RecordedEventKind

APP_TARGET = json.dumps({"executable": str(sys.executable)})


VALID_ANSWER = json.dumps(
    {
        "goal": "Open and close Visual Studio Code.",
        "workflow": {
            "workflow_id": "ai-draft",
            "name": "VS Code Demo",
            "steps": [
                {
                    "step_id": "s1",
                    "name": "Open editor",
                    "kind": "LAUNCH_APPLICATION",
                    "message": "Launch vscode.",
                    "target": APP_TARGET,
                },
                {
                    "step_id": "s2",
                    "name": "Close editor",
                    "kind": "CLOSE_APPLICATION",
                    "message": "Close vscode.",
                    "target": APP_TARGET,
                },
            ],
        },
    }
)


def observation_draft() -> RawDraft:
    return RawDraft(
        "recording-1",
        (
            RawDraftAction(
                1,
                "A Code.exe window opened: Visual Studio Code.",
                RecordedEventKind.WINDOW_OPEN,
                process_name="Code.exe",
                window_title="Visual Studio Code",
            ),
            RawDraftAction(
                2,
                "The Code.exe window closed: Visual Studio Code.",
                RecordedEventKind.WINDOW_CLOSE,
                process_name="Code.exe",
                window_title="Visual Studio Code",
            ),
        ),
    )


def recording_poster(answer: object, calls: list) -> object:
    def poster(url: str, headers: dict[str, str], body: bytes) -> bytes:
        calls.append((url, headers, body))
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, bytes):
            return answer
        return json.dumps(answer).encode("utf-8")

    return poster


class FakeCredentials:
    def __init__(self, keys: dict[str, str | None]) -> None:
        self.keys = keys

    def get(self, name: str) -> str | None:
        return self.keys.get(name)


def gemini_api_envelope(text: str) -> bytes:
    """Shape a canned answer like the real Gemini HTTP response."""
    return json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]}).encode("utf-8")


def anthropic_api_envelope(text: str) -> bytes:
    """Shape a canned answer like the real Anthropic HTTP response."""
    return json.dumps({"content": [{"type": "text", "text": text}]}).encode("utf-8")


def test_valid_provider_answer_becomes_a_validated_draft() -> None:
    calls: list = []
    proposal = analyze_recording(
        AnalysisRequest(observation_draft()),
        provider="gemini",
        credentials=FakeCredentials({"GEMINI_API_KEY": "k-gemini"}),
        poster=recording_poster(gemini_api_envelope(VALID_ANSWER), calls),
    )

    assert isinstance(proposal, ProviderDraft)
    assert proposal.goal == "Open and close Visual Studio Code."
    assert [step.kind for step in proposal.workflow.steps] == [
        StepKind.LAUNCH_APPLICATION,
        StepKind.CLOSE_APPLICATION,
    ]
    assert proposal.workflow.workflow_id == "ai-draft"


def test_request_carries_the_pinned_model_and_only_the_event_list() -> None:
    calls: list = []
    draft = observation_draft()
    analyze_recording(
        AnalysisRequest(draft),
        provider="gemini",
        credentials=FakeCredentials({"GEMINI_API_KEY": "k-gemini"}),
        poster=recording_poster(gemini_api_envelope(VALID_ANSWER), calls),
    )

    url, headers, body = calls[0]
    assert url.endswith(f"/{GEMINI_MODEL}:generateContent")
    assert headers["x-goog-api-key"] == "k-gemini"
    text = body.decode("utf-8")
    assert "Code.exe" in text
    assert "screenshot" not in text
    assert "secret-password" not in text
    draft_by_id = draft.actions[0]
    assert draft_by_id.process_name == "Code.exe"


def test_missing_key_falls_back_to_the_local_mapping() -> None:
    calls: list = []
    proposal = analyze_recording(
        AnalysisRequest(observation_draft()),
        provider="gemini",
        credentials=FakeCredentials({"GEMINI_API_KEY": None}),
        poster=recording_poster(gemini_api_envelope(VALID_ANSWER), calls),
    )

    assert calls == []
    assert proposal.workflow.workflow_id == "recording-recording-1"
    assert [step.kind for step in proposal.workflow.steps] == [
        StepKind.LAUNCH_APPLICATION,
        StepKind.CLOSE_APPLICATION,
    ]


def test_disallowed_and_unknown_step_kinds_fall_back() -> None:
    bad_answer = json.dumps(
        {
            "goal": "Something unsafe.",
            "workflow": {
                "workflow_id": "ai-draft",
                "name": "Bad",
                "steps": [
                    {
                        "step_id": "s1",
                        "name": "Run shell",
                        "kind": "EXECUTE_ARBITRARY_CODE",
                        "message": "not a real kind",
                        "target": None,
                    }
                ],
            },
        }
    )
    calls: list = []
    proposal = analyze_recording(
        AnalysisRequest(observation_draft()),
        provider="gemini",
        credentials=FakeCredentials({"GEMINI_API_KEY": "k"}),
        poster=recording_poster(gemini_api_envelope(bad_answer), calls),
    )

    assert calls != []  # the call happened; the answer was refused
    # The fallback is the Phase 1 deterministic mapping of the same events.
    assert [step.kind for step in proposal.workflow.steps] == [
        StepKind.LAUNCH_APPLICATION,
        StepKind.CLOSE_APPLICATION,
    ]


def test_http_and_malformed_failures_fall_back_to_the_local_mapping() -> None:
    cases = [
        OSError("connection refused"),
        b"<html>nope</html>",
        b'{"candidates": []}',
        b"not json",
    ]
    for answer in cases:
        calls: list = []
        proposal = analyze_recording(
            AnalysisRequest(observation_draft()),
            provider="gemini",
            credentials=FakeCredentials({"GEMINI_API_KEY": "k"}),
            poster=recording_poster(answer, calls),
        )
        assert [step.kind for step in proposal.workflow.steps] == [
            StepKind.LAUNCH_APPLICATION,
            StepKind.CLOSE_APPLICATION,
        ]
        assert calls != []


def test_unknown_provider_name_falls_back_without_any_request() -> None:
    calls: list = []
    proposal = analyze_recording(
        AnalysisRequest(observation_draft()),
        provider="openai",
        credentials=FakeCredentials({"OPENAI_API_KEY": "k"}),
        poster=recording_poster(gemini_api_envelope(VALID_ANSWER), calls),
    )

    assert calls == []
    assert [step.kind for step in proposal.workflow.steps] == [
        StepKind.LAUNCH_APPLICATION,
        StepKind.CLOSE_APPLICATION,
    ]


def test_anthropic_provider_uses_its_endpoint_and_version_header() -> None:
    calls: list = []
    proposal = analyze_recording(
        AnalysisRequest(observation_draft()),
        provider="anthropic",
        credentials=FakeCredentials({"ANTHROPIC_API_KEY": "k-anthropic"}),
        poster=recording_poster(anthropic_api_envelope(VALID_ANSWER), calls),
    )

    url, headers, body = calls[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers["x-api-key"] == "k-anthropic"
    assert "anthropic-version" in headers
    payload = json.loads(body)
    assert payload["messages"][0]["role"] == "user"
    assert [step.kind for step in proposal.workflow.steps] == [
        StepKind.LAUNCH_APPLICATION,
        StepKind.CLOSE_APPLICATION,
    ]


def test_fenced_json_answers_are_accepted() -> None:
    fenced = f"```json\n{VALID_ANSWER}\n```"
    calls: list = []
    proposal = analyze_recording(
        AnalysisRequest(observation_draft()),
        provider="gemini",
        credentials=FakeCredentials({"GEMINI_API_KEY": "k"}),
        poster=recording_poster(gemini_api_envelope(fenced), calls),
    )

    assert proposal.goal == "Open and close Visual Studio Code."


def test_missing_key_with_default_credentials_source_falls_back(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ONCE_GEMINI_API_KEY", raising=False)
    calls: list = []
    proposal = analyze_recording(
        AnalysisRequest(observation_draft()),
        provider="gemini",
        poster=recording_poster(gemini_api_envelope(VALID_ANSWER), calls),
    )

    assert calls == []
    assert [step.kind for step in proposal.workflow.steps] == [
        StepKind.LAUNCH_APPLICATION,
        StepKind.CLOSE_APPLICATION,
    ]
