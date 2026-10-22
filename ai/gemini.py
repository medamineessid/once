"""Opt-in Gemini adapter using the provider's JSON REST endpoint."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from engine.errors import AIProviderError, WorkflowValidationError
from storage.workflows import workflow_from_dict

from .models import AnalysisRequest, ProviderDraft, ProviderQuestion, ProviderResponse
from .provider import MAX_INTERVIEW_TURNS

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
)


class GeminiProvider:
    """Call Gemini only when explicitly enabled by the caller."""

    def __init__(self, api_key: str, *, enabled: bool = False, timeout: float = 20.0) -> None:
        self._api_key = api_key
        self._enabled = enabled
        self._timeout = timeout

    def analyze(self, request: AnalysisRequest) -> ProviderResponse:
        if not self._enabled:
            raise AIProviderError("Gemini is disabled. Enable cloud analysis explicitly first.")
        if len(request.conversation) > MAX_INTERVIEW_TURNS:
            raise AIProviderError("The AI interview reached its question limit.")
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Return JSON only with either "
                                '{"type":"question","text":"..."} or '
                                '{"type":"draft","goal":"...","workflow":{...}}. '
                                f"Recording draft: {request.draft!r}. "
                                f"Conversation: {request.conversation!r}."
                            )
                        }
                    ]
                }
            ]
        }
        http_request = Request(
            GEMINI_ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._api_key},
            method="POST",
        )
        try:
            with urlopen(  # noqa: S310 - endpoint is the fixed HTTPS Gemini API.
                http_request, timeout=self._timeout
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, OSError, UnicodeError, json.JSONDecodeError) as error:
            raise AIProviderError("Gemini analysis failed; no workflow was produced.") from error
        try:
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(text)
            if result.get("type") == "question" and isinstance(result.get("text"), str):
                return ProviderQuestion(result["text"])
            if result.get("type") == "draft":
                return ProviderDraft(result["goal"], workflow_from_dict(result["workflow"]))
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise AIProviderError("Gemini returned malformed proposal data.") from error
        except WorkflowValidationError as error:
            raise AIProviderError("Gemini returned an invalid workflow draft.") from error
        raise AIProviderError("Gemini returned an unsupported proposal type.")
