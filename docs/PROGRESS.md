# Once progress

- Last completed step: Release-hardening session — repository-recovery audit
  for failed agent runs (park-then-restore with a `--no-verify` fallback when
  project hooks veto parking, plain-language "left behind" explanations instead
  of silent claims, refusal of a deleted agent branch and of worktree paths
  inside the user's repository), corrupt-`once.db` startup now fails clearly
  with the data file left untouched (previously a raw traceback), a
  pre-migration database opens after an update and keeps its rows, README
  documents install/first-run/upgrade/uninstall for a packaged build, and the
  roadmap integrations 6–9 are reconciled in `docs/decisions.md`
  (file-management rewrite deliberately deferred; coding-agent + recorder +
  workflow/history UI marked as implemented with automated tests).
- Last commit: 024b17b plus this session's storage/app/docs hardening
- Next action: packaged-exe isolated startup runs (clean, first-run, corrupt
  verifier.json, corrupt once.db) after the rebuilt exe finishes; real modal
  interaction of the startup-failure dialog remains manual-only.
- Currently failing tests or known breakage: none
- Open items: live Gemini analysis is opt-in and unverified against a real
  provider; live paid coding-agent runs are unauthorized in this environment;
  mutating desktop actions, browser automation, and the file-management
  planner/executor rebuild are deliberately deferred (see `docs/decisions.md`
  2026-10-24); the startup-failure modal is unit-tested with a stubbed message
  box and not clicked by automation; no real interactive GUI session with the
  full approve-apply cycle has been demonstrated by a human.
- Environment: Windows 11 x64; Python 3.14.3; virtual environment `.venv`
