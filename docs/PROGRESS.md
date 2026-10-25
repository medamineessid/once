# Once progress

- Last completed step: Release-hardening session — repository-recovery audit
  for failed agent runs (park-then-restore with a `--no-verify` fallback when
  project hooks veto parking, plain-language "left behind" explanations instead
  of silent claims, refusal of a deleted agent branch and of worktree paths
  inside the user's repository), corrupt-`once.db` startup now fails clearly
  with the data file left untouched (previously a raw traceback), a
  pre-migration database opens after an update and keeps its rows, README
  documents install/first-run/upgrade/uninstall for a packaged build,  and the roadmap integrations 6–9 are reconciled in `docs/decisions.md`
  (file-management rewrite deliberately deferred; coding-agent + recorder +
  workflow/history UI marked as implemented with automated tests). This session
  fixed the settings page so every button callback exists, replaced the
  blocking placeholder dialogs with a non-modal status label (this was the
  `tests/test_shell.py` hang), made sidebar buttons checkable so the
  active-page highlight actually shows, and disabled sidebar button
  auto-repeat so rapid clicks cannot queue repeated page transitions.

- Last commit: 1d367c2 — fix(shell): remove modal-test hang and restore sidebar active highlight
- Verified this session: full suite `211 passed, 2 skipped` offscreen; shell
  suite `8 passed`; `ruff check .` and `ruff format --check .` all clean;
  `app.py --smoke-test` exit 0 offscreen; an offscreen navigation driver
  confirmed workshop index and sidebar checked state for Home /
  My automations / Activity / Settings, the create-automation transition and
  review-cancel to Home; no WebView/QtWebEngine classes anywhere in `ui/`.
- Next action: human click-through of the packaged startup-failure dialog and
  one supervised interactive GUI session of the approve-apply cycle remain
  manual; live paid coding-agent and live Gemini runs stay unauthorized; the
  three untracked files (`app.spec`, `once-app.spec`,
  `ui/components/__init__.py`) need a human decision: land them deliberately or
  delete them.
- Currently failing tests or known breakage: none
- Open items: live Gemini analysis is opt-in and unverified against a real
  provider; live paid coding-agent runs are unauthorized in this environment;
  mutating desktop actions, browser automation, and the file-management
  planner/executor rebuild are deliberately deferred (see `docs/decisions.md`
  2026-10-24); the startup-failure modal is unit-tested with a stubbed message
  box and not clicked by automation; no real interactive GUI session with the
  full approve-apply cycle has been demonstrated by a human.
- Environment: Windows 11 x64; Python 3.14.3; virtual environment `.venv`
