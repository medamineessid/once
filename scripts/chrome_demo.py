"""Live end-to-end isolated-Chrome demonstration for the browser engine.

This script runs against a REAL Chrome installation. It is not part of the
automated suite. Safety rules it follows:

- Chrome is launched by the engine itself with an isolated temporary profile
  and --remote-debugging-port=0; the user's ordinary profile, cookies, and
  history are never touched;
- the only web server involved is a local static test server on 127.0.0.1;
  no public website is contacted;
- launch/navigate/interact AND read-only steps all pass through
  approve_desktop_workflow and the desktop interaction policy before running;
- a deviation (step failure) stops the run and is reported, never improvised;
- the engine-launched browser is closed and its temp profile removed at the
  end via the provider's shutdown().

Run with:  C:\\Users\\DELL\\once\\.venv\\Scripts\\python.exe scripts\\chrome_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import http.server
import json
import socket
import tempfile
import threading

from engine.desktop import approve_desktop_workflow
from engine.replay import DESKTOP_INTERACTION_POLICY, ReplayExecutor
from engine.workflow import (
    StepKind,
    StepStatus,
    Workflow,
    WorkflowRunner,
    WorkflowStep,
)
from integrations.chrome_devtools import ChromeDevtoolsActions

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


DEMO_PAGE = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>Once Browser Demo</title></head>
<body>
  <h1>Once isolated-browser demo</h1>
  <p id="intro">This page is served locally and exists only for the demo.</p>
  <input id="demo-input" name="demo" type="text" />
  <button id="demo-button"
          onclick="setStatus()">Demo button</button>
  <p id="status">waiting</p>
  <script>
    function setStatus() {
      document.getElementById('status').textContent = 'button was clicked';
    }
  </script>
</body>
</html>
"""


class DemoServer:
    """A bounded static test server on 127.0.0.1 that serves one demo page."""

    def __init__(self) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.root = Path(tempfile.mkdtemp(prefix="once-demo-site-"))
        (self.root / "index.html").write_text(DEMO_PAGE, encoding="utf-8")
        handler = _handler_for(self.root)
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/index.html"

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def _handler_for(root: Path):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, *args):  # silence the request log
            return None

    return Handler


def show(run) -> None:
    for result in run.results:
        print(f"[{result.step_id}] {result.status.value}: {result.message}")
        for evidence in result.evidence:
            print(f"        {evidence}")


def main() -> int:
    server = DemoServer()
    print(f"local demo page: {server.url()}")
    actions = ChromeDevtoolsActions()
    executor = ReplayExecutor(DESKTOP_INTERACTION_POLICY)
    port: int | None = None

    try:
        # 1. Launch an isolated Chrome through the approval gate.
        launch = Workflow(
            "once-browser-launch",
            "Launch isolated Chrome",
            (
                WorkflowStep(
                    "launch",
                    "Launch",
                    StepKind.LAUNCH_BROWSER,
                    "An isolated Chrome instance is running for this workflow.",
                    target=json.dumps({"application": "chrome"}),
                ),
            ),
        )
        WorkflowRunner.validate(launch)
        approval = approve_desktop_workflow(launch)
        print(
            "approval recorded for exactly these steps:",
            [s.step_id for s in approval.workflow.steps],
        )
        run_launch = executor.execute(approval.workflow, allowed_root=None, browser_actions=actions)
        show(run_launch)
        if run_launch.status.value != "SUCCEEDED":
            print("DEMO STOPPED: the browser launch did not succeed.")
            return 1
        for evidence in run_launch.results[0].evidence:
            if evidence.startswith("cdp_port="):
                port = int(evidence.split("=", 1)[1])
        if port is None:
            print("DEMO STOPPED: no DevTools port was reported by the launch step.")
            return 1
        browser = {"cdp_port": port}
        print(f"isolated browser ready on DevTools port {port}")

        # 2. Navigate, inspect, find, interact, and verify — all approved.
        steps = (
            WorkflowStep(
                "navigate",
                "Navigate",
                StepKind.NAVIGATE_BROWSER,
                "The isolated browser shows the local demo page.",
                target=json.dumps({"browser": browser, "url": server.url()}),
            ),
            WorkflowStep(
                "wait-page",
                "WaitPage",
                StepKind.WAIT_PAGE,
                "The demo page title is present.",
                target=json.dumps(
                    {"browser": browser, "conditions": {"title": "Once Browser Demo"}}
                ),
            ),
            WorkflowStep(
                "inspect",
                "Inspect",
                StepKind.INSPECT_PAGE,
                "Title, URL, and bounded page text were recorded.",
                target=json.dumps({"browser": browser, "include_text": True}),
            ),
            WorkflowStep(
                "find",
                "Find",
                StepKind.FIND_PAGE_ELEMENT,
                "The demo button is uniquely identified.",
                target=json.dumps({"browser": browser, "selector": "#demo-button"}),
            ),
            WorkflowStep(
                "click",
                "Click",
                StepKind.INTERACT_PAGE_ELEMENT,
                "The demo button was clicked.",
                target=json.dumps(
                    {"browser": browser, "selector": "#demo-button", "interaction": "click"}
                ),
            ),
            WorkflowStep(
                "type",
                "Type",
                StepKind.INTERACT_PAGE_ELEMENT,
                "The demo text stayed within its bound.",
                target=json.dumps(
                    {
                        "browser": browser,
                        "selector": "#demo-input",
                        "interaction": "type",
                        "text": "demo input",
                    }
                ),
            ),
            WorkflowStep(
                "wait-status",
                "WaitStatus",
                StepKind.WAIT_PAGE,
                "The page reflects the click.",
                target=json.dumps(
                    {"browser": browser, "conditions": {"text": "button was clicked"}}
                ),
            ),
            WorkflowStep(
                "verify",
                "Verify",
                StepKind.FIND_PAGE_ELEMENT,
                "The status element shows the click effect.",
                target=json.dumps({"browser": browser, "selector": "#status"}),
            ),
        )
        workflow = Workflow("once-browser-demo", "Once browser demo", steps)
        WorkflowRunner.validate(workflow)
        approval2 = approve_desktop_workflow(workflow)
        print(
            "approval recorded for exactly these steps:",
            [s.step_id for s in approval2.workflow.steps],
        )
        run = executor.execute(approval2.workflow, allowed_root=None, browser_actions=actions)
        show(run)
        success = run.status.value == "SUCCEEDED" and all(
            result.status in (StepStatus.SUCCEEDED, StepStatus.VERIFIED) for result in run.results
        )
        if success:
            print("RESULT: PASS - live isolated-browser round trip verified.")
            return 0
        print("RESULT: FAIL - see the step messages above.")
        return 1
    finally:
        actions.shutdown()
        print("cleanup: the engine-launched browser was closed and its profile removed.")
        server.stop()
        print("cleanup: the local demo server was stopped.")


if __name__ == "__main__":
    raise SystemExit(main())
