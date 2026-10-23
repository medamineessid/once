# Once progress

- Last completed step: Coding-agent proposal integration (branches, diff
  review, approval gate, local ff-only merge)
- Last commit: effb71c
- Next action: GUI surfacing of agent proposals (diff review screen) and
  pre-approval sandboxed reruns via git worktree are the known follow-ups
- Currently failing tests or known breakage: none
- Open items: live Gemini use is opt-in and unverified; screenshots are
  supported as references but are not automatically captured for every event;
  external desktop/browser/agent integrations are not implemented; replay
  supports read-only path checks, exact-identity window inspection, and
  exact-identity UI element inspection; no mutating UI action is implemented;
  headless verifier is implemented and verification runs, loop decisions,
  agent proposals, and approval decisions are persisted in the SQLite
  history; the agent command is user-configured and allowlisted, and no live
  coding-agent service has been exercised
- Environment: Windows 11 x64; Python 3.14.3; virtual environment `.venv`
