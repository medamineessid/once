"""Isolated Chrome automation through the Chrome DevTools Protocol.

Architecture decision (documented in docs/desktop_automation.md):

- The provider only ever automates a browser instance that it launched itself
  with an isolated temporary user profile and --remote-debugging-port=0.
  It never attaches to the user's ordinary Chrome session, cookies, history,
  passwords, or profiles.
- Target discovery and tab creation use plain HTTP to 127.0.0.1 (the /json
  endpoints); in-page commands run over the WebSocket DevTools protocol with a
  tiny stdlib client (integrations/devtools_ws.py). No new dependency.
- Every in-page operation is an engine-owned fixed expression. The workflow
  contributes only data (a URL, a CSS selector, text); no user- or AI-supplied
  JavaScript is ever evaluated.
- Ambiguity, missing targets, unsupported elements, and timeouts fail closed
  with structured StepResults instead of improvising.
"""

from __future__ import annotations

import http.client
import json
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from engine.workflow import StepResult, StepStatus
from integrations.devtools_ws import (
    WebSocketClient,
    WebSocketClosed,
)

POLL_INTERVAL_SECONDS = 0.25
DEFAULT_COMMAND_TIMEOUT = 10.0
LAUNCH_WAIT_SECONDS = 20.0
PAGE_SETTLE_SECONDS = 30.0

# Fixed, engine-owned expressions. The placeholders (selectors, text) are
# inserted as JSON string literals only; no workflow data can break out.
EXPR_PAGE_STATE = "({href: location.href, title: document.title, readyState: document.readyState})"
PAGE_TEXT_LIMIT = 20_000
ELEMENT_TEXT_LIMIT = 2_000

# Fixed, engine-owned expressions. The placeholders (selectors, text) are
# inserted as JSON string literals only; no workflow data can break out.
EXPR_PAGE_STATE = "({href: location.href, title: document.title, readyState: document.readyState})"
EXPR_PAGE_TEXT = f"document.body ? document.body.innerText.slice(0, {PAGE_TEXT_LIMIT + 1}) : ''"
EXPR_ELEMENT_INFO = (
    "(function(sel){"
    "var els = document.querySelectorAll(sel);"
    "if (els.length !== 1) { return {count: els.length}; }"
    "var el = els[0];"
    "return {count: 1, tag: el.tagName.toLowerCase(),"
    " name: el.getAttribute('name'),"
    f" text: (el.textContent || '').slice(0, {ELEMENT_TEXT_LIMIT + 1}),"
    " editable: (el.tagName === 'TEXTAREA' || el.isContentEditable ||"
    " (el.tagName === 'INPUT' && !el.disabled && el.type !== 'password')),"
    " disabled: !!el.disabled || !!el.readOnly};"
    "})"
)
EXPR_CLICK = (
    "(function(sel){"
    "var els = document.querySelectorAll(sel);"
    "if (els.length !== 1) { return {count: els.length}; }"
    "els[0].click();"
    "return {count: 1, clicked: true};"
    "})"
)
EXPR_TYPE = (
    "(function(sel, text){"
    "var els = document.querySelectorAll(sel);"
    "if (els.length !== 1) { return {count: els.length}; }"
    "var el = els[0];"
    "if (el.type === 'password') { return {count: 1, refused: 'password'}; }"
    "var proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype"
    " : (el instanceof HTMLInputElement ? HTMLInputElement.prototype : null);"
    "if (proto === null && !el.isContentEditable) {"
    "  return {count: 1, refused: 'not editable'};"
    "}"
    "if (proto !== null) {"
    "  var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;"
    "  setter.call(el, text);"
    "}"
    "if (el.isContentEditable) { el.textContent = text; }"
    "el.dispatchEvent(new Event('input', {bubbles: true}));"
    "el.dispatchEvent(new Event('change', {bubbles: true}));"
    "return {count: 1, typed: true, readback: el.value === undefined ? el.textContent : el.value};"
    "})"
)


class BrowserError(Exception):
    """A structured DevTools or browser failure (converted to StepResult)."""


class DevtoolsHttp:
    """Plain-HTTP access to Chrome's local DevTools /json endpoints."""

    def __init__(self, port: int, timeout: float = DEFAULT_COMMAND_TIMEOUT) -> None:
        self._port = port
        self._timeout = timeout

    def _request(self, method: str, path: str):
        connection = http.client.HTTPConnection("127.0.0.1", self._port, timeout=self._timeout)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            return json.loads(response.read().decode("utf-8", errors="replace"))
        finally:
            connection.close()

    def version(self) -> dict:
        return self._request("GET", "/json/version")

    def list_targets(self) -> list:
        return self._request("GET", "/json/list")

    def new_tab(self, url: str) -> dict:
        from urllib.parse import quote

        return self._request("PUT", "/json/new?" + quote(url, safe=""))


class ChromeApplicationRegistry:
    """Resolves the registered browser name to its installed executable."""

    CANDIDATES = (
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    )

    def resolve(self, name: str) -> Path:
        lowered = name.strip().lower()
        if lowered != "chrome":
            raise BrowserError(
                f"The browser registry does not contain {name}. Only Chrome is supported."
            )
        for candidate in self.CANDIDATES:
            if candidate.is_file():
                return candidate
        raise BrowserError("Google Chrome was not found at its registered installation paths.")


class BrowserSession:
    """One browser instance launched and owned by this engine."""

    def __init__(
        self,
        process: subprocess.Popen,
        port: int,
        profile_dir: Path,
    ) -> None:
        self.process = process
        self.port = port
        self.profile_dir = profile_dir


class ChromeDevtoolsActions:
    """BrowserActions implementation backed by an isolated Chrome instance."""

    def __init__(
        self,
        registry: ChromeApplicationRegistry | None = None,
        popen: Callable[..., subprocess.Popen] | None = None,
        http_factory: Callable[[int], DevtoolsHttp] | None = None,
        ws_factory: Callable[[str], WebSocketClient] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        launch_wait_seconds: float = LAUNCH_WAIT_SECONDS,
        command_timeout: float = DEFAULT_COMMAND_TIMEOUT,
    ) -> None:
        self._registry = registry or ChromeApplicationRegistry()
        self._popen = popen or self._default_popen
        self._http_factory = http_factory or (lambda port: DevtoolsHttp(port))
        self._ws_factory = ws_factory or (lambda url: WebSocketClient(url))
        self._clock = clock
        self._sleep = sleep
        self._poll_interval = poll_interval
        self._launch_wait_seconds = launch_wait_seconds
        self._command_timeout = command_timeout
        self._sessions: dict[int, BrowserSession] = {}
        self._first_page_url = "about:blank"

    # ------------------------------------------------------------ launch

    @staticmethod
    def _default_popen(argv: list[str]):
        return subprocess.Popen(  # noqa: S603 - exact argv list, shell disabled
            argv,
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def launch_browser(self, target_json: str) -> StepResult:
        """Start an isolated Chrome with an own profile and a random DevTools port."""
        from engine.errors import ExecutionError

        target = self._load_target(target_json, "launch browser")
        if isinstance(target.get("application"), str):
            executable = self._registry.resolve(target["application"])
        else:
            executable = Path(str(target["executable"]))
        if "chrome.exe" not in executable.name.lower():
            raise ExecutionError("Only the registered Chrome executable may be launched.")
        profile_dir = Path(tempfile.mkdtemp(prefix="once-chrome-profile-"))
        argv = [
            str(executable),
            "--remote-debugging-port=0",
            "--user-data-dir=" + str(profile_dir / "profile"),
            "--no-first-run",
            "--no-default-browser-check",
        ]
        if not target.get("headed"):
            argv.append("--headless=new")
        try:
            process = self._popen(argv)
        except OSError as error:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=f"The browser could not be launched: {error}",
                evidence=(f"executable={executable}",),
            )
        port = self._wait_for_debug_port(process)
        if port is None:
            if process.poll() is None:
                process.kill()
            self._safe_rmtree(profile_dir)
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=(
                    "The browser did not report a DevTools endpoint, so it was "
                    "closed again and nothing was automated."
                ),
                evidence=(f"executable={executable}",),
            )
        http = self._http_factory(port)
        try:
            browser_name = str(http.version().get("Browser", ""))
        except (OSError, ValueError) as error:
            process.kill()
            self._safe_rmtree(profile_dir)
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=f"The browser endpoint could not be verified: {error}",
                evidence=(f"port={port}",),
            )
        if "Chrome" not in browser_name:
            process.kill()
            self._safe_rmtree(profile_dir)
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=("The endpoint does not belong to Chrome, so it was refused."),
                evidence=(f"port={port}", f"browser={browser_name}"),
            )
        if not self._wait_for_first_page(http):
            process.kill()
            self._safe_rmtree(profile_dir)
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=("The browser page did not become available in time."),
                evidence=(f"port={port}",),
            )
        self._sessions[port] = BrowserSession(process, port, profile_dir)
        return StepResult(
            step_id="",
            status=StepStatus.SUCCEEDED,
            message="An isolated Chrome instance was launched for this workflow.",
            evidence=(
                f"cdp_port={port}",
                f"process_id={process.pid}",
                f"browser={browser_name}",
                "profile=isolated temporary profile",
            ),
        )

    def _wait_for_debug_port(self, process: subprocess.Popen) -> int | None:
        """Poll stderr for Chrome's 'DevTools listening on ws://...' line."""
        captured: dict[str, int] = {}

        def reader() -> None:
            stderr = getattr(process, "stderr", None)
            if stderr is None:
                return
            for line in stderr:
                text = line.decode("utf-8", errors="replace")
                if "DevTools listening on ws://127.0.0.1:" in text:
                    token = text.split("ws://127.0.0.1:")[1].split("/")[0]
                    if token.isdigit():
                        captured["port"] = int(token)

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        deadline = self._clock() + self._launch_wait_seconds
        while "port" not in captured:
            if process.poll() is not None:
                return None
            if self._clock() >= deadline:
                return None
            self._sleep(self._poll_interval)
        return captured["port"]

    def _wait_for_first_page(self, http: DevtoolsHttp) -> bool:
        deadline = self._clock() + self._launch_wait_seconds
        while self._clock() < deadline:
            try:
                pages = [t for t in http.list_targets() if t.get("type") == "page"]
            except OSError, ValueError:
                pages = []
            if pages:
                return True
            self._sleep(self._poll_interval)
        return False

    # -------------------------------------------------------- session access

    def _session(self, target: dict) -> BrowserSession:
        from engine.errors import ExecutionError

        port = target["cdp_port"]
        session = self._sessions.get(port)
        if session is None:
            raise ExecutionError(
                "No browser was launched by this workflow with that DevTools port, "
                "so the step was refused."
            )
        if session.process.poll() is not None:
            raise ExecutionError(
                "The browser has exited, so the step was refused instead of "
                "reattaching to something else."
            )
        return session

    def _single_page(self, session: BrowserSession, http: DevtoolsHttp) -> dict:
        from engine.errors import ExecutionError

        pages = self._page_targets(session, http)
        if not pages:
            raise ExecutionError("No page is open in the isolated browser.")
        if len(pages) > 1:
            raise ExecutionError(
                "More than one page is open in the isolated browser, so the step "
                "was refused instead of choosing a tab."
            )
        return pages[0]

    @staticmethod
    def _page_targets(session: BrowserSession, http: DevtoolsHttp) -> list[dict]:
        targets = [t for t in http.list_targets() if t.get("type") == "page"]
        return [t for t in targets if bool(t.get("webSocketDebuggerUrl"))]

    def _command(self, page_ws_url: str, method: str, params: dict) -> dict:
        """One DevTools command; the client's socket timeout bounds the wait."""
        client = self._ws_factory(page_ws_url)
        try:
            client.send_json({"id": 1, "method": method, "params": params})
            while True:
                message = client.receive_json()
                if message.get("id") == 1:
                    return message
        finally:
            client.close()

    @staticmethod
    def _runtime_expression(client: WebSocketClient, expression: str) -> Any:
        client.send_json(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expression, "returnByValue": True},
            }
        )
        while True:
            message = client.receive_json()
            if message.get("id") == 1:
                break
        result_payload = message.get("result", {})
        if "exceptionDetails" in result_payload:
            raise BrowserError("The page rejected the evaluation (exception).")
        inner = result_payload.get("result", {})
        if isinstance(inner, dict):
            if inner.get("type") == "undefined" or inner.get("subtype") == "error":
                return None
            if "value" in inner:
                return inner["value"]
        return inner

    # ------------------------------------------------------------- navigate

    def navigate(self, target_json: str) -> StepResult:
        """Navigate the single page to the validated URL and check load state."""
        target = self._load_target(target_json, "navigation")
        session = self._session(target["browser"])
        http = self._http_factory(session.port)
        page = self._single_page(session, http)
        ws_url = page.get("webSocketDebuggerUrl")
        if not ws_url:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message="The page did not expose a DevTools connection.",
            )
        url = target["url"]
        try:
            reply = self._command(ws_url, "Page.navigate", {"url": url})
        except (WebSocketClosed, BrowserError, OSError, ValueError) as error:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=f"The navigation command failed: {error}",
                evidence=(f"url={self._redact_url(url)}",),
            )
        result_payload = reply.get("result") or {}
        command_error = reply.get("error") or result_payload.get("errorText")
        if not command_error and isinstance(result_payload.get("result"), dict):
            command_error = result_payload["result"].get("errorText")
        if command_error:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=f"The browser refused the navigation: {command_error}",
                evidence=(f"url={self._redact_url(url)}",),
            )
        final = self._wait_for_load(ws_url)
        if final is None:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message="The page did not finish loading in time.",
                evidence=(f"url={self._redact_url(url)}",),
            )
        return StepResult(
            step_id="",
            status=StepStatus.SUCCEEDED,
            message="The page loaded.",
            evidence=(
                f"requested_url={self._redact_url(url)}",
                f"final_url={self._redact_url(str(final.get('href', '')))}",
                f"title={final.get('title', '')}",
                f"readyState={final.get('readyState', '')}",
            ),
        )

    def _wait_for_load(self, ws_url: str) -> dict | None:
        deadline = self._clock() + PAGE_SETTLE_SECONDS
        while self._clock() < deadline:
            client = self._ws_factory(ws_url)
            try:
                state = self._runtime_expression(client, EXPR_PAGE_STATE)
            except BrowserError, OSError, ValueError, WebSocketClosed:
                state = None
            finally:
                client.close()
            if isinstance(state, dict) and state.get("readyState") == "complete":
                return state
            self._sleep(self._poll_interval)
        return None

    # ---------------------------------------------------------- inspect page

    def inspect_page(self, target_json: str) -> StepResult:
        """Return the bounded title, URL and (optional) visible text."""
        target = self._load_target(target_json, "page inspection")
        session = self._session(target["browser"])
        http = self._http_factory(session.port)
        page = self._single_page(session, http)
        evidence = [
            f"title={page.get('title', '')}",
            f"url={self._redact_url(page.get('url', ''))}",
        ]
        if target.get("include_text"):
            ws_url = page.get("webSocketDebuggerUrl")
            client = self._ws_factory(str(ws_url))
            try:
                text = self._runtime_expression(client, EXPR_PAGE_TEXT)
            except (BrowserError, OSError, ValueError, WebSocketClosed) as error:
                return StepResult(
                    step_id="",
                    status=StepStatus.FAILED,
                    message=f"The page text could not be read: {error}",
                )
            finally:
                client.close()
            if not isinstance(text, str):
                return StepResult(
                    step_id="",
                    status=StepStatus.FAILED,
                    message="The page did not expose readable text.",
                )
            truncated = len(text) > 20_000
            body = text[:20_000]
            evidence.append(f"text_length={len(body)}")
            evidence.append(f"text_truncated={str(truncated).lower()}")
            evidence.append("text_begin=" + body[:200].replace("\n", " | "))
        return StepResult(
            step_id="",
            status=StepStatus.SUCCEEDED,
            message="The current page was inspected.",
            evidence=tuple(evidence),
        )

    # ------------------------------------------------------- find + interact

    def find_page_element(self, target_json: str) -> StepResult:
        """Locate exactly one element by CSS selector; refuse ambiguity."""
        target = self._load_target(target_json, "element lookup")
        session = self._session(target["browser"])
        http = self._http_factory(session.port)
        page = self._single_page(session, http)
        ws_url = page.get("webSocketDebuggerUrl")
        expression = f"{EXPR_ELEMENT_INFO}({json.dumps(target['selector'])})"
        client = self._ws_factory(str(ws_url))
        try:
            found = self._runtime_expression(client, expression)
        except (BrowserError, OSError, ValueError, WebSocketClosed) as error:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=f"The element lookup failed: {error}",
            )
        finally:
            client.close()
        if not isinstance(found, dict):
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message="The lookup returned no result.",
            )
        count = found.get("count", 0)
        if count == 0:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message="The element was not found on the page.",
                evidence=(f"selector={target['selector']}", "matches=0"),
            )
        if count != 1:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=(
                    f"The selector matched {count} elements, so the step was "
                    "refused instead of choosing one."
                ),
                evidence=(f"selector={target['selector']}", f"matches={count}"),
            )
        return StepResult(
            step_id="",
            status=StepStatus.SUCCEEDED,
            message="The element was uniquely identified.",
            evidence=(
                f"selector={target['selector']}",
                f"tag={found.get('tag', '')}",
                f"disabled={str(bool(found.get('disabled'))).lower()}",
                "matches=1",
                f"element_text={str(found.get('text') or '')[:120]}",
            ),
        )

    def interact_page_element(self, target_json: str) -> StepResult:
        """Click or type into exactly one element; both read back their effect."""
        target = self._load_target(target_json, "page interaction")
        interaction = target.get("interaction", "click")
        session = self._session(target["browser"])
        http = self._http_factory(session.port)
        page = self._single_page(session, http)
        ws_url = page.get("webSocketDebuggerUrl")
        selector_json = json.dumps(target["selector"])
        if interaction == "click":
            expression = f"{EXPR_CLICK}({selector_json})"
        else:
            expression = f"{EXPR_TYPE}({selector_json}, {json.dumps(target.get('text', ''))})"
        client = self._ws_factory(str(ws_url))
        try:
            outcome = self._runtime_expression(client, expression)
        except (BrowserError, OSError, ValueError, WebSocketClosed) as error:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=f"The page interaction failed: {error}",
            )
        finally:
            client.close()
        if not isinstance(outcome, dict):
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message="The interaction returned no result.",
            )
        count = outcome.get("count", 0)
        if count == 0:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message="The element was not found, so nothing was interacted with.",
            )
        if count != 1:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=f"The selector matched {count} elements, so the interaction was refused.",
            )
        refused = outcome.get("refused")
        if refused == "password":
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message="The element is a password field; entering text was refused.",
            )
        if refused == "not editable":
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message="The element is not a text input, so typing was refused.",
            )
        if interaction == "click":
            return StepResult(
                step_id="",
                status=StepStatus.SUCCEEDED,
                message="The element was clicked.",
                evidence=(f"selector={target['selector']}", "clicked=true"),
            )
        readback_ok = outcome.get("readback") == target.get("text")
        if not readback_ok:
            return StepResult(
                step_id="",
                status=StepStatus.FAILED,
                message=(
                    "The element did not retain the entered text, so the step "
                    "failed instead of trusting the write."
                ),
                evidence=("readback_confirmed=false",),
            )
        return StepResult(
            step_id="",
            status=StepStatus.SUCCEEDED,
            message="The text was entered and read back from the element.",
            evidence=(
                f"selector={target['selector']}",
                f"chars={len(target.get('text', ''))}",
                "readback_confirmed=true",
            ),
        )

    # ------------------------------------------------------------- wait page

    def wait_page(self, target_json: str, timeout_seconds: float) -> StepResult:
        """Bounded wait for page conditions (title/url/selector/text)."""
        target = self._load_target(target_json, "page wait")
        session = self._session(target["browser"])
        http = self._http_factory(session.port)
        conditions = target["conditions"]
        deadline = self._clock() + timeout_seconds
        last_reason = "the page was not inspected"
        while True:
            try:
                page = self._single_page(session, http)
            except Exception as error:
                last_reason = str(error)
                if self._clock() >= deadline:
                    break
                self._sleep(self._poll_interval)
                continue
            ws_url = page.get("webSocketDebuggerUrl")
            client = self._ws_factory(str(ws_url))
            try:
                state = self._runtime_expression(client, EXPR_PAGE_STATE)
                text: Any = None
                if conditions.get("text") is not None:
                    text = self._runtime_expression(client, EXPR_PAGE_TEXT)
            except (BrowserError, OSError, ValueError, WebSocketClosed) as error:
                state, text = None, None
                last_reason = f"the page state was unreadable: {error}"
            finally:
                client.close()
            reason = self._conditions_missing(state, text, conditions)
            if reason is None:
                return StepResult(
                    step_id="",
                    status=StepStatus.SUCCEEDED,
                    message="The page matched all waited-for conditions.",
                    evidence=(
                        f"title={str(state.get('title', ''))[:160]}",
                        f"url={self._redact_url(str(state.get('href', '')))}",
                    ),
                )
            last_reason = reason
            if self._clock() >= deadline:
                break
            self._sleep(self._poll_interval)
        return StepResult(
            step_id="",
            status=StepStatus.FAILED,
            message=(
                f"The page did not match the waited-for conditions within "
                f"{timeout_seconds} seconds ({last_reason})."
            ),
            evidence=("conditions=" + json.dumps(conditions),),
        )

    @staticmethod
    def _conditions_missing(state: Any, text: Any, conditions: dict) -> str | None:
        """Return the first unmet condition as a reason, or None when all hold."""
        if not isinstance(state, dict):
            return "the page state was not readable yet"
        expected_title = conditions.get("title")
        if expected_title is not None and state.get("title") != expected_title:
            return f"the title is {str(state.get('title'))[:80]!r}"
        expected_url = conditions.get("url")
        if expected_url is not None and state.get("href") != expected_url:
            return "the URL has not changed yet"
        expected_text = conditions.get("text")
        if expected_text is not None and (not isinstance(text, str) or expected_text not in text):
            return "the expected text is not on the page yet"
        return None

    # -------------------------------------------------------------- shutdown

    def shutdown(self) -> None:
        """Close every browser this provider launched (used by tests/demo)."""
        for session in list(self._sessions.values()):
            if session.process.poll() is None:
                session.process.kill()
            self._safe_rmtree(session.profile_dir)
        self._sessions.clear()

    @staticmethod
    def _safe_rmtree(directory: Path) -> None:
        """Remove the provider's own temporary profile directory if possible."""
        import contextlib
        import shutil

        with contextlib.suppress(OSError):
            shutil.rmtree(directory, ignore_errors=True)

    # ----------------------------------------------------------------- utils

    @staticmethod
    def _redact_url(url: str) -> str:
        """Keep URLs short in evidence; nothing else about the page is recorded."""
        return url[:300].strip()

    @staticmethod
    def _load_target(target_json: str, what: str) -> dict:
        try:
            target = json.loads(target_json)
        except json.JSONDecodeError as error:
            raise BrowserError(f"The {what} target is not valid JSON.") from error
        if not isinstance(target, dict):
            raise BrowserError(f"The {what} target must be a JSON object.")
        return target
