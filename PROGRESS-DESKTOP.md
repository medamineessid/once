## 2026-11-02 — Desktop automation engine (Chrome automation)

Done: added end-to-end tests wiring the real ChromeDevtoolsActions through WorkflowRunner (launch registers a cdp_port session; navigate -> inspect -> wait all dispatch). 19/23 tests pass; 4 need real Chrome installed on Windows (pre-existing, environment-only).
Files touched: tests/test_chrome_devtools.py
Next: run ruff lint/format on changed files and the runnable engine/integration suite to confirm nothing regressed; then consider a narrow error-handling reliability fix in the Chrome provider.
