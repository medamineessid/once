"""Deterministic tests for the Chrome DevTools provider (fake HTTP + fake WS)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.errors import ExecutionError
from engine.workflow import StepStatus
from integrations.chrome_devtools import (
    BrowserError,
    ChromeApplicationRegistry,
    ChromeDevtoolsActions,
    DevtoolsHttp,
)

TEST_PORT = 51922
PAGE_WS = f"ws://127.0.0.1:{TEST_PORT}/devtools/page/abcdef"


def page_response(value):
    return {"id": 1, "result": {"result": value}}


class FakePageWs:
    """Scripted DevTools page connection: value per command name.

    Script values may be a list, which is consumed in order (one entry per
    command of that method), or a plain value / callable that is reused on
    every matching command.
    """

    def __init__(self, script: dict[str, object]) -> None:
        self.script = script
        self.sent_methods: list[str] = []

    def send_json(self, message: dict) -> None:
        self.sent_methods.append(message.get("method", ""))

    def receive_json(self) -> dict:
        try:
            method = self.sent_methods.pop(0)
        except IndexError as error:
            raise RuntimeError("no scripted response left") from error
        value = self.script.get(method)
        if isinstance(value, list):
            if not value:
                raise RuntimeError("script list exhausted for " + method)
            value = value.pop(0)
        value = value() if callable(value) else value
        if isinstance(value, dict) and "id" in value and "result" in value:
            return value  # already a full CDP response
        if method == "Page.navigate":
            # Real navigate replies carry result fields (not a result.result value).
            return {"id": 1, "result": value if isinstance(value, dict) else {"frameId": "f1"}}
        return page_response(value)

    def close(self) -> None:
        return None


class FakeHttp(DevtoolsHttp):
    """Scripted /json endpoints (no sockets involved)."""

    def __init__(self, targets: dict, version: dict | None = None) -> None:
        super().__init__(port=TEST_PORT)
        self.targets = targets
        self.version_data = version or {"Browser": "Chrome/141.0"}

    def version(self) -> dict:
        return self.version_data

    def list_targets(self) -> list:
        return self.targets


class FakeProcess:
    pid = 12345

    def poll(self):
        return None

    def kill(self):
        self.killed = getattr(self, "killed", 0) + 1


def single_page_target(url="http://127.0.0.1:8000/demo.html", title="Demo"):
    return {"type": "page", "title": title, "url": url, "webSocketDebuggerUrl": PAGE_WS}


class BrowserSessionStub:
    def __init__(self, process, port) -> None:
        self.process = process
        self.port = port
        self.profile_dir = Path()


def make_actions(targets, ws_script=None, ws_factory=None, *, version=None):
    actions = ChromeDevtoolsActions(
        http_factory=lambda port: FakeHttp(targets, version=version),
        ws_factory=ws_factory or (lambda url: FakePageWs(ws_script or {})),
    )
    actions._sessions[TEST_PORT] = BrowserSessionStub(FakeProcess(), TEST_PORT)
    return actions


def navigate_target(url="http://127.0.0.1:8000/demo.html"):
    return json.dumps({"browser": {"cdp_port": TEST_PORT}, "url": url})


# ------------------------------------------------------------------- navigate


def test_navigate_reports_final_url_and_load_state() -> None:
    script = {
        "Page.navigate": {"frameId": "f1"},
        "Runtime.evaluate": {
            "href": "http://127.0.0.1:8000/demo.html",
            "title": "Demo",
            "readyState": "complete",
        },
    }
    result = make_actions([single_page_target()], script).navigate(navigate_target())
    assert result.status is StepStatus.SUCCEEDED
    joined = " ".join(result.evidence)
    assert "readyState=complete" in joined
    assert "final_url=http://127.0.0.1:8000/demo.html" in joined


def test_navigate_refuses_when_the_command_errors() -> None:
    script = {"Page.navigate": {"errorText": "ERR_NAME_NOT_RESOLVED"}}
    result = make_actions([single_page_target()], script).navigate(navigate_target("http://nope/"))
    assert result.status is StepStatus.FAILED
    assert "refused the navigation" in result.message


def test_navigate_times_out_when_the_page_never_loads() -> None:
    class Clock:
        value = 0.0

    def sleep(seconds: float) -> None:
        Clock.value += seconds

    script = {
        "Page.navigate": {"frameId": "f1"},
        "Runtime.evaluate": lambda: {
            "href": "about:blank",
            "title": "",
            "readyState": "loading",
        },
    }
    actions = make_actions([single_page_target()], script)
    actions._clock = lambda: Clock.value
    actions._sleep = sleep
    result = actions.navigate(navigate_target("http://slow-host/"))
    assert result.status is StepStatus.FAILED
    assert "did not finish loading" in result.message


# --------------------------------------------------------------------- inspect


def test_inspect_page_reports_title_url_and_text() -> None:
    script = {"Runtime.evaluate": page_response("hello " * 6)}
    result = make_actions([single_page_target()], script).inspect_page(
        json.dumps({"browser": {"cdp_port": TEST_PORT}, "include_text": True})
    )
    assert result.status is StepStatus.SUCCEEDED
    joined = " ".join(result.evidence)
    assert "text_length=36" in joined
    assert "text_truncated=false" in joined
    assert "title=Demo" in joined


def test_inspect_page_truncates_beyond_the_content_bound() -> None:
    script = {"Runtime.evaluate": page_response("x" * 20_050)}
    result = make_actions([single_page_target()], script).inspect_page(
        json.dumps({"browser": {"cdp_port": TEST_PORT}, "include_text": True})
    )
    joined = " ".join(result.evidence)
    assert "text_truncated=true" in joined
    assert "text_length=20000" in joined


def test_inspect_page_without_text_records_no_page_content() -> None:
    result = make_actions([single_page_target()], {}).inspect_page(
        json.dumps({"browser": {"cdp_port": TEST_PORT}})
    )
    assert result.status is StepStatus.SUCCEEDED
    assert not any("text_length" in line for line in result.evidence)


# ------------------------------------------------------------- find + interact


def test_find_element_reports_ambiguity_and_uniqueness() -> None:
    actions = make_actions(
        [single_page_target()], {"Runtime.evaluate": page_response({"count": 2})}
    )
    ambiguous = actions.find_page_element(
        json.dumps({"browser": {"cdp_port": TEST_PORT}, "selector": "button"})
    )
    assert ambiguous.status is StepStatus.FAILED
    assert "matched 2 elements" in ambiguous.message

    unique = make_actions(
        [single_page_target()],
        {
            "Runtime.evaluate": page_response(
                {"count": 1, "tag": "h1", "text": "Demo title", "disabled": False, "name": None}
            )
        },
    ).find_page_element(json.dumps({"browser": {"cdp_port": TEST_PORT}, "selector": "h1"}))
    assert unique.status is StepStatus.SUCCEEDED
    assert "tag=h1" in unique.evidence

    missing = make_actions(
        [single_page_target()], {"Runtime.evaluate": page_response({"count": 0})}
    ).find_page_element(json.dumps({"browser": {"cdp_port": TEST_PORT}, "selector": "h9"}))
    assert missing.status is StepStatus.FAILED
    assert "not found" in missing.message


def test_interact_click_confirms_the_click() -> None:
    script = {"Runtime.evaluate": page_response({"count": 1, "clicked": True})}
    result = make_actions([single_page_target()], script).interact_page_element(
        json.dumps(
            {"browser": {"cdp_port": TEST_PORT}, "selector": "button", "interaction": "click"}
        )
    )
    assert result.status is StepStatus.SUCCEEDED
    assert "clicked=true" in result.evidence


def test_interact_typing_refuses_password_fields_and_failed_readbacks() -> None:
    password = make_actions(
        [single_page_target()],
        {"Runtime.evaluate": page_response({"count": 1, "refused": "password"})},
    ).interact_page_element(
        json.dumps(
            {
                "browser": {"cdp_port": TEST_PORT},
                "selector": "input",
                "interaction": "type",
                "text": "secret",
            }
        )
    )
    assert password.status is StepStatus.FAILED
    assert "password field" in password.message

    not_editable = make_actions(
        [single_page_target()],
        {"Runtime.evaluate": page_response({"count": 1, "refused": "not editable"})},
    ).interact_page_element(
        json.dumps(
            {
                "browser": {"cdp_port": TEST_PORT},
                "selector": "div",
                "interaction": "type",
                "text": "x",
            }
        )
    )
    assert not_editable.status is StepStatus.FAILED
    assert "not a text input" in not_editable.message

    failed_readback = make_actions(
        [single_page_target()],
        {"Runtime.evaluate": page_response({"count": 1, "typed": True, "readback": "other"})},
    ).interact_page_element(
        json.dumps(
            {
                "browser": {"cdp_port": TEST_PORT},
                "selector": "input",
                "interaction": "type",
                "text": "hello",
            }
        )
    )
    assert failed_readback.status is StepStatus.FAILED
    assert "readback_confirmed=false" in failed_readback.evidence

    confirmed = make_actions(
        [single_page_target()],
        {"Runtime.evaluate": page_response({"count": 1, "typed": True, "readback": "hello"})},
    ).interact_page_element(
        json.dumps(
            {
                "browser": {"cdp_port": TEST_PORT},
                "selector": "input",
                "interaction": "type",
                "text": "hello",
            }
        )
    )
    assert confirmed.status is StepStatus.SUCCEEDED
    assert "readback_confirmed=true" in confirmed.evidence


def test_interact_ambiguity_is_refused() -> None:
    result = make_actions(
        [single_page_target()], {"Runtime.evaluate": page_response({"count": 3})}
    ).interact_page_element(
        json.dumps({"browser": {"cdp_port": TEST_PORT}, "selector": "div", "interaction": "click"})
    )
    assert result.status is StepStatus.FAILED
    assert "matched 3 elements" in result.message


# ------------------------------------------------------------------ wait page


def test_wait_page_succeeds_when_all_conditions_hold() -> None:
    script = {
        "Runtime.evaluate": [
            {"href": "http://127.0.0.1:8000/demo.html", "title": "Demo", "readyState": "complete"},
            "done ok",
        ]
    }
    result = make_actions([single_page_target()], script).wait_page(
        json.dumps(
            {
                "browser": {"cdp_port": TEST_PORT},
                "conditions": {"title": "Demo", "text": "done"},
            }
        ),
        2.0,
    )
    assert result.status is StepStatus.SUCCEEDED
    assert "matched all waited-for conditions" in result.message


def test_wait_page_times_out_with_the_reason() -> None:
    class Clock:
        value = 0.0

    def sleep(seconds: float) -> None:
        Clock.value += seconds

    script = {
        "Runtime.evaluate": lambda: {
            "href": "http://127.0.0.1:8000/other.html",
            "title": "Other",
            "readyState": "complete",
        }
    }
    actions = make_actions([single_page_target()], script)
    actions._clock = lambda: Clock.value
    actions._sleep = sleep
    result = actions.wait_page(
        json.dumps({"browser": {"cdp_port": TEST_PORT}, "conditions": {"title": "Demo"}}),
        1.0,
    )
    assert result.status is StepStatus.FAILED
    assert "the title is" in result.message


# ------------------------------------------------- session identity / refusal


def test_unknown_port_is_refused() -> None:
    with pytest.raises(ExecutionError, match="No browser was launched"):
        make_actions([single_page_target()], {}).navigate(
            json.dumps({"browser": {"cdp_port": 4242}, "url": "http://h/"})
        )


def test_dead_browser_is_refused() -> None:
    class DeadProcess:
        pid = 1

        def poll(self):
            return 1

        def kill(self):
            pass

    actions = make_actions([single_page_target()], {})
    actions._sessions[TEST_PORT] = BrowserSessionStub(DeadProcess(), TEST_PORT)
    with pytest.raises(ExecutionError, match="has exited"):
        actions.navigate(navigate_target())


def test_ambiguous_pages_are_refused() -> None:
    with pytest.raises(ExecutionError, match="More than one page"):
        make_actions([single_page_target(), single_page_target()], {}).inspect_page(
            json.dumps({"browser": {"cdp_port": TEST_PORT}})
        )


def test_missing_pages_are_refused() -> None:
    with pytest.raises(ExecutionError, match="No page is open"):
        make_actions([], {}).inspect_page(json.dumps({"browser": {"cdp_port": TEST_PORT}}))


# ------------------------------------------------------------------- launch


def test_registry_resolves_registered_chrome_only() -> None:
    registry = ChromeApplicationRegistry()
    resolved = registry.resolve("chrome")
    assert resolved.name.lower() == "chrome.exe"
    with pytest.raises(BrowserError, match="does not contain"):
        registry.resolve("edge")


def test_launch_refuses_a_non_chrome_endpoint() -> None:
    holder = {"stderr": [b"DevTools listening on ws://127.0.0.1:51922/devtools/browser/x\r\n"]}

    class StderrProcess:
        pid = 7
        stderr = iter(holder["stderr"])

        def poll(self):
            return None

        def kill(self):
            pass

    actions = ChromeDevtoolsActions(
        registry=ChromeApplicationRegistry(),
        popen=lambda argv: StderrProcess(),
        http_factory=lambda port: FakeHttp(
            [],  # no usable target list yet, version check runs first
            version={"Browser": "Edg/1.0"},
        ),
        ws_factory=lambda url: FakePageWs({}),
        launch_wait_seconds=5.0,
    )
    result = actions.launch_browser(json.dumps({"application": "chrome"}))
    assert result.status is StepStatus.FAILED
    assert "does not belong to Chrome" in result.message


def test_launch_succeeds_and_registers_the_session() -> None:
    stderr_data = [
        b"other line\r\n",
        b"DevTools listening on ws://127.0.0.1:51922/devtools/browser/xyz\r\n",
    ]

    class StderrProcess:
        pid = 8
        stderr = iter(stderr_data)

        def poll(self):
            return None

        def kill(self):
            pass

    actions = ChromeDevtoolsActions(
        registry=ChromeApplicationRegistry(),
        popen=lambda argv: StderrProcess(),
        http_factory=lambda port: FakeHttp(
            [single_page_target()],
            version={"Browser": "Chrome/141.0.7390.122"},
        ),
        ws_factory=lambda url: FakePageWs({}),
    )
    result = actions.launch_browser(json.dumps({"application": "chrome"}))
    assert result.status is StepStatus.SUCCEEDED
    assert "cdp_port=51922" in result.evidence
    assert "process_id=8" in result.evidence
    assert TEST_PORT in actions._sessions


def test_launch_fails_closed_without_a_endpoint_line() -> None:
    class StderrProcess:
        pid = 9
        stderr = iter([b"some unrelated log\r\n"])

        def poll(self):
            return None  # still running but no endpoint in time

        def kill(self):
            pass

    killed = {"count": 0}

    class KillableProcess(StderrProcess):
        def kill(self):
            killed["count"] += 1

    class Clock:
        value = 0.0

    def advance(_seconds: float) -> None:
        Clock.value += 0.25

    removed: dict[str, int] = {}
    import integrations.chrome_devtools as module

    def fake_rmtree(_directory):
        removed["dirs"] = removed.get("dirs", 0) + 1

    module.original = module.ChromeDevtoolsActions._safe_rmtree
    module.ChromeDevtoolsActions._safe_rmtree = staticmethod(fake_rmtree)
    try:
        actions = ChromeDevtoolsActions(
            registry=ChromeApplicationRegistry(),
            popen=lambda argv: KillableProcess(),
            http_factory=lambda port: FakeHttp([single_page_target()]),
            ws_factory=lambda url: FakePageWs({}),
            clock=lambda: Clock.value,
            sleep=advance,
            launch_wait_seconds=1.0,
        )
        result = actions.launch_browser(json.dumps({"application": "chrome"}))
        assert result.status is StepStatus.FAILED
        assert "did not report a DevTools endpoint" in result.message
        assert killed["count"] == 1
        assert removed.get("dirs") == 1
    finally:
        module.ChromeDevtoolsActions._safe_rmtree = module.original


def test_shutdown_closes_sessions_and_cleans_profiles() -> None:
    removed: list[Path] = []

    class KillableProcess(FakeProcess):
        def kill(self):
            FakeProcess.kill(self)

    actions = make_actions([single_page_target()], {})
    session = actions._sessions[TEST_PORT]
    session.profile_dir = Path("fake-profile-dir")
    import integrations.chrome_devtools as module

    def fake_rmtree(directory):
        removed.append(directory)

    module.original = module.ChromeDevtoolsActions._safe_rmtree
    module.ChromeDevtoolsActions._safe_rmtree = staticmethod(fake_rmtree)
    try:
        actions.shutdown()
        assert TEST_PORT not in actions._sessions
        assert removed == [Path("fake-profile-dir")]
    finally:
        module.ChromeDevtoolsActions._safe_rmtree = module.original
