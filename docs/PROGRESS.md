# Once progress

- Last completed step: Worktree-based pre-merge verification and GUI agent
  proposal review (isolated `{checkout}` verification worktree, persisted
  PRE_MERGE/POST_MERGE evidence blockers, approve/reject/apply lifecycle)
- Last commit: beed7e3
- Next action: let a real session supply an operator-configured acceptance
  checker to the new "Agent proposals" tab (the window currently accepts a
  VerifierConfig but app.py passes none), then remaining integrations list
- Currently failing tests or known breakage: none
- Open items: live Gemini use is opt-in and unverified; screenshots are
  supported as references but are not automatically captured for every event;
  external desktop/browser/agent integrations are not implemented; replay
  supports read-only path checks, exact-identity window inspection, and
  exact-identity UI element inspection; no mutating UI action is implemented;
  headless verifier is implemented and verification runs, loop decisions,
  agent proposals, approval decisions, proposal verifications, and worktree
  lifecycle records are persisted in the SQLite history; pre-approval
  verification now runs in a disposable git worktree and gates approval; the
  agent command is user-configured and allowlisted, and no live coding-agent
  service has been exercised
- Environment: Windows 11 x64; Python 3.14.3; virtual environment `.venv`
