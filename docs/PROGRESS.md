# Once progress

- Last completed step: Release-readiness pass — approved-proposal apply after
  a restart (`apply_recorded_approval` + panel "Apply previously approved
  proposal" button), verifier.json config editor (`ui/verifier_dialog.py`,
  atomic save reusing the exact restart validation), real `{checkout}`
  verification tests against the system interpreter (spaced paths, missing
  file, mid-verification interruption recovery), agent-crash parking of
  partial output on the agent branch before restore, branch-hijack refusal,
  app logging (rotating UTF-8 log) + plain-language startup-failure handler,
  and a repeatable PyInstaller Windows build (`once.spec`) whose exe passed
  isolated-app-data smoke runs (clean start, corrupt-config start, visible
  startup-failure dialog behavior)
- Last commit: 5df32b4 + packaging/docs follow-up (this work)
- Next action: real coding-agent run is authorized-only (paid cloud);
  remaining future work: broader integration milestones (roadmap 6-9),
  installer/shortcut polish, undo/recovery integration for file management
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
  the checker is user-configured through allowlist-validated verifier.json
  (with a GUI editor writing through the same validation); a recorded
  approval can be re-applied after a restart under the same gate checks;
  no live coding-agent service has been exercised (Claude Code is installed
  but a real run requires authorized paid cloud access)
- Environment: Windows 11 x64; Python 3.14.3; virtual environment `.venv`
