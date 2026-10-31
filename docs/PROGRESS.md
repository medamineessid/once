# Once progress

**Active session piece:** 2026-10-31 production request — visual workflow editor,
full shell refresh, MVP moves to P9 (prompt queue P0–P9 in session prompt). The
spec files (`docs/specs/visual_workflow_editor.md`, reference PNG) are MISSING
(AD-008); work proceeds from the session prompt.

- Current branch: `slice/p4-editor` (fork of main at d40f741).
- main = origin/main = d40f741 ("docs: preserve agent handoff prompt") — the
  prompt handoff was saved verbatim, ff-merged and pushed on 2026-10-31.
- P4a verification on `slice/p4-editor`: "412 passed, 2 skipped in 116.61s",
  `ruff check .` "All checks passed!", `ruff format --check .` "140 files
  already formatted", both smoke tests PASS, and `scripts/verify.ps1`
  "ALL CHECKS PASSED".
- Append-only-guard repair detail: the amendments commit stored
  docs/ai_engineering_log.md as a CRLF blob (main is LF), so the numstat guard read
  "994 added, 980 deleted" while the ignore-CR diff was exactly "14 added,
  0 deleted" (pure append, no lines lost). Commit 85a5893 re-stores the file LF.
- Previous finished state (kept for reference): PHASE A repairs merged (1685475),
  PHASE B layout foundation (eae542d), PHASE P1 truth-and-foundations (e638e5e),
  2026-10-29 amendments + strengthened unwired-button guard (ccfd61b, eb3773c).
  Full suite green at 352 passed, 2 skipped on branch tip.

## Active queue (this session)

| id | Item | Status | Notes |
|---|---|---|---|
| P0.1 | Paste branch/status/log/verify output; repair failures | DONE | verify#1 failed only the append-only guard (CRLF/LF blob); repaired by 85a5893; verify#2 ALL CHECKS PASSED |
| P0.2 | Commit untracked spec files if any; merge slice/j2-create-automation | DONE | specs missing → AD-008; branch ff-merged + pushed |
| P0.3 | Read digest docs; fix stale ledger entries | DONE | ledger rewritten this commit (this file); docs read: WORKING_AGREEMENT, UX_BRIEF, PROGRESS, AUTONOMOUS_DECISIONS, BUTTON_AUDIT, ui_migration_plan, AGENTS (in prompt) |
| P1 | docs/design/visual_editor.md + docs/UX_AUDIT.md | DONE | 5c17e42 on slice/p1-editor-discovery, ff-merged + pushed |
| P2 | Design system + shell refresh (slice/p2-design-system) | DONE | components + page template + rewrite; verify ALL CHECKS PASSED, pytest 386 passed/2 skipped in 140.25s |
| P3 | Canvas read-only (slice/p3-canvas) | DONE | ui/editor/layout.py pure goldens + ui/editor/canvas.py read-only view; integrated on ReviewPage; added close-cancel/join task, screenshot refresh, swap ledger |
| P4a | Qt-free editing (slice/p4-editor) | DONE | bb9c07b; coverage completed on slice/p4a-coverage |
| P4b | Layout record storage | DONE | slice/p4b-layouts; SQLite migration, strict records, corrupt fallback |
| P4c | Editor page and acceptance flow | DONE | slice/p4c-editor-page; create/add/save/open/run/activity acceptance |
| P5 | Recording → editor (slice/p5-recording-editor) | TODO | |
| P6 | Run + review (slice/p6-run-review) | TODO | includes review.py defects D12/D13 |
| P7 | Branching (slice/p7-branching) | PARKED | PARKED.md PARKED-1; Add-decision hidden |
| P8 | Hardening (slice/p8-hardening) | TODO | |
| P9 | Parity, default switch, release (slice/p9-release) | TODO | gate conditions in prompt |

## Legacy journey queue (PHASE C) — superseded by the prompt queue above

J2..J9 journeys are reordered by this session's prompt: creation lives in the
visual editor (J2+J5+J7 merge into P4/P5/P6), J3/J4 land inside P2, J6 lands in P6,
J9's checklist and default-window gate are P9. Keep the notes below as parity
requirements (each moved into its owning item above):

- [ ] (P6) review approval wires through the ONE existing approval path
      (engine/desktop.py approve_desktop_workflow; mutating_kind_names,
      requires_desktop_approval) — never a second path.
- [ ] (P6) review page service injection (audit D13) and load_proposal defect fix
      (audit D12) before its buttons reappear.
- [ ] (P4) existing saved workflows open/run unchanged + regression corpus.
- [ ] (P9) docs/MVP_CHECKLIST.md with per-capability file:line and covering test;
      default window switches ONLY if no MVP item is MISSING and both acceptance
      paths (app.py real entry) pass.
- [x] Honest-controls rule enforced by the strengthened unwired test
      (chain-following, AST-checked); Review Edit/Approve currently hidden (P6
      unwires them when the journey lands).

## Standing environment facts

- Windows 11 x64; Python 3.14.3 in `.venv` (Windows venv); PySide6 6.12.0;
  Windows PowerShell 5.1 (French locale). App default window: OLD (app.py:78;
  `--shell` selects ui.shell.MainWindow). Minimum window 960×620 (ui/shell.py:136).
- Verify = `scripts/verify.ps1` (pytest + ruff + 2 smoke tests + append-only
  guard). Smoke-test the real windows rather than crafting fake ones.
- engine/workflow.py:759-763 unreachable duplicate raise and :800-801 duplicated
  `step_ids.add` — documented, leave alone. engine/workflow.py: TESTS AND DOCS
  EXCEPTIONS: tests/test_shell.py monkeypatches blockers per working agreement.
- Browser sessions closed after approved runs/exit (atexit); orphan Chrome on hard
  crash is a documented limitation. do not work on it.
- Other worktrees exist (once-desktop, /tmp ones) - do not touch/prune/remove.
- Git line-endings policy (this repo, learned 2026-10-29): all git commands from
  Windows-side git (`powershell.exe`) with `core.autocrlf=true`; the repo commits
  LF blobs; editing sources from WSL tools is fine (append/edit preserves CRLF in
  Windows-checked-out files, new files write LF), but never `git add` from WSL git
  (its autocrlf=false would store CRLF blobs — the bug the 85a5893 repair fixes).

## Status tracking (carried over)

Each item: id, status (TODO/IN PROGRESS/DONE/BLOCKED), branch, commit hashes, raw
test summary line. Screenshots captured only through app.py's real path; see
docs/screenshots/ folders and their README files.
