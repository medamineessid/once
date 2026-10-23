# Once progress

- Last completed step: Headless acceptance-case verifier slice
- Last commit: d2f9d60
- Next action: persist verification runs in history, then stop; do not start
  the loop controller or coding-agent adapter in this step
- Currently failing tests or known breakage: none
- Open items: live Gemini use is opt-in and unverified; screenshots are
  supported as references but are not automatically captured for every event;
  external desktop/browser/agent integrations are not implemented; replay
  supports read-only path checks, exact-identity window inspection, and
  exact-identity UI element inspection; no mutating UI action is implemented;
  headless verifier is implemented and verification runs are persisted in the
  SQLite history
- Environment: Windows 11 x64; Python 3.14.3; virtual environment `.venv`
