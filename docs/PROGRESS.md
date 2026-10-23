# Once progress

- Last completed step: Verifier run persistence and bounded test-and-fix loop
- Last commit: 940d905
- Next action: implement the coding-agent proposer integration (separate
  branch, diff review, approval gate per D14/O6) or a user-requested
  different scope; the GUI does not yet surface loop or verifier history
- Currently failing tests or known breakage: none
- Open items: live Gemini use is opt-in and unverified; screenshots are
  supported as references but are not automatically captured for every event;
  external desktop/browser/agent integrations are not implemented; replay
  supports read-only path checks, exact-identity window inspection, and
  exact-identity UI element inspection; no mutating UI action is implemented;
  headless verifier is implemented and both verification runs and loop
  decisions are persisted in the SQLite history; no real coding-agent
  proposer exists, so the loop stops with `STOPPED_NO_PROPOSER` until one is
  explicitly configured
- Environment: Windows 11 x64; Python 3.14.3; virtual environment `.venv`
