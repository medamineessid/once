## 2026-10-24 — Step: redesigned shell UI and smoke-test alignment

- Task: make the redesigned shell screens and smoke test consistent with the MainWindow/sidebar object shape, keep the suite green, and land the shell on its own branch without touching main yet.
- AI contribution: rewrote the shell-side assertions to match the sidebar API, replaced a brittle `is`-comparison pattern with stable attribute checks, and trimmed an unused import backport that made the smoke run harder to verify.
- Defect found: the smoke test asserted against a `Sidebar.is_on()` method that did not exist yet, and one assertion relied on `is` between two Python bools produced through Qt signal timing; the latter masked a real Qt check-state timing issue. The sidebar was fixed to retain the initial checked page, and the test was rewritten to stay green across page switches.
- Verification: ran `pytest tests/test_shell.py tests/test_app_entry.py tests/test_smoke.py`; final line `17 passed`; ran full suite `206 passed, 2 skipped`; ran `ruff check . --unsafe-fixes` after auto-fixes; ran `git status` and confirmed only the shell package files and one untracked `ui/components/__init__.py` are in play.
- Outcome: PASSED
- Human review: left blank for the human to confirm the branch merge plan in `docs/decisions.md` before pulling redesigned shell onto main.
