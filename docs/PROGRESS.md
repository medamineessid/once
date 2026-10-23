# Once progress

- Last completed step: Supervised loop hardening — recorded-proposal identity
  enforcement (verify/approve/apply compare presented review against the
  persisted record), session checker configuration via
  `%LOCALAPPDATA%/Once/verifier.json`, resized failure paths (missing
  branches become blockers instead of raised errors), and full MainWindow
  journey + restart/redaction/partial-cancellation/failed-post-merge tests
- Last commit: 13e327d (this work)
- Next action: optional GUI editor for verifier.json; live coding-agent
  integration and packaging remain future milestones
- Currently failing tests or known breakage: none
- Open items: live Gemini use is opt-in and unverified; screenshots are
  supported as references but are not automatically captured for every event;
  external desktop/browser/agent integrations are not implemented; replay
  supports read-only path checks, exact-identity window inspection, and
  exact-identity UI element inspection; no mutating UI action is implemented;
  headless verifier is implemented and verification runs, loop decisions,
  agent proposals, approval decisions, proposal verifications, and worktree
  lifecycle records are persisted in the SQLite history; pre-approval
  verification runs in a disposable git worktree and gates approval; a
  mismatched presented-vs-recorded review can no longer be approved/applied;
  the checker is user-configured through allowlist-validated verifier.json;
  no live coding-agent service has been exercised
- Environment: Windows 11 x64; Python 3.14.3; virtual environment `.venv`
