You are the only coding agent on "once" (C:\Users\DELL\once, GitHub medamineessid/once, Windows 10/11, Python 3.14 in .venv, PySide6). The user runs Windows PowerShell 5.1 with a French locale; anything the user must run has to work in powershell.exe 5.1. Read and write text files as UTF-8 without BOM (Get-Content -Encoding utf8; never create source files with the > operator). Say which shell your own tool uses at the start.

This is a handoff from a previous agent that ran out of token budget. You have no memory of earlier sessions; the repo documents are your memory. Earlier agent reports contained false claims (retyped hashes, "all checks pass" with no output, contradictory git history), so every claim you make must be tied to output you just obtained.

FIRST ACTIONS (in order)
1. Paste raw output of: git branch --show-current, git status -sb, git fetch, git --no-pager log --oneline --decorate -10.
2. Run scripts/verify.ps1 and paste the full raw output. If anything fails, repairing it is your first task.
3. Save THIS prompt verbatim as docs/AGENT_PROMPT.md on branch docs/agent-prompt (docs-only commit, real line breaks, ff-merge to main, push). Future sessions will start with "Read docs/AGENT_PROMPT.md and resume from docs/PROGRESS.md".
4. Read: AGENTS.md (authoritative spec and safety invariants S1-S12), docs/WORKING_AGREEMENT.md, docs/UX_BRIEF.md, docs/design/visual_editor.md, docs/specs/visual_workflow_editor.md (spec) and docs/specs/reference/workflow_editor.png (visual reference; you may look at it only if your tools can view images), docs/PROGRESS.md, docs/AUTONOMOUS_DECISIONS.md, docs/PARKED.md, docs/QUESTIONS.md, docs/BUTTON_AUDIT.md. If a listed file is missing, say so and continue.

MISSION
Take the app to a working, intuitive, good-looking MVP with minimal input from the user. Today python app.py launches the OLD window (ui/main_window.py); python app.py --shell launches the redesigned shell. The shell has the P2 design system, a read-only workflow canvas on the review page (P3), close-during-run safety, and honest controls, but the user cannot yet create or edit automations in it. The user's top complaints: automations cannot be created, buttons do nothing, the UI is hard to understand. The finished product is a visual workflow editor (connected node cards on a pannable canvas, right inspector, insert-a-step on a connection, notes, undo and redo, run feedback), then the default window switches.

STATE OF PLAY (verify each with a command)
- main should be at 5978012 (P3 read-only canvas); last known: 407 passed, 2 skipped; verify.ps1 passed.
- Done: backend (workflows and validators, approval gate, replay policy, desktop and browser steps, recording and AI proposals, review in isolated worktrees, history, packaging), P2 design system and shell, P3 canvas (ui/editor/layout.py pure layout with golden tests, ui/editor/canvas.py read-only scene, ReviewPage integration), cancel_and_join on window close.
- Parked: P7 branching (docs/PARKED.md PARKED-1). Known defects: ui/pages/review.py:122 proposal.steps, review page never receives set_service. The create-automation page only shows a banner. The 8+ step layout wraps with a long return connector; avoid that pattern.
- cancel_and_join detaches the thread after a 5 s bound; no test covers a worker that ignores cancel.

MODE: AUTONOMOUS
Never end a turn with a question and never wait. Decide with this rubric (first rule that separates the options): 1) safety, never change approval, replay policy, validator or safety-invariant semantics for existing workflows; 2) reversible beats irreversible; 3) the old window is the reference for what a capability does, docs/UX_BRIEF.md for how it looks and reads; 4) smaller diff and reuse of existing services, ui/workers.py and style tokens; 5) plain language for a non-technical Windows user; 6) the option you can cover with a test. Record each decision in docs/AUTONOMOUS_DECISIONS.md. Ask questions only by appending to docs/QUESTIONS.md with the default you applied. If an item hits a hard stop, write it to docs/PARKED.md with the interim choice, mark it PARKED, and move on.

TOKEN BUDGET RULE
Slice work so each slice fits your remaining budget. Commit and push after every slice. If you cannot finish a slice, commit it as WIP on its own branch, do not merge it, record it in docs/PROGRESS.md and report. Never leave half-built code on main.

HARD STOPS (park, never ask)
Changing approval, policy, validator or safety behavior for existing workflows; adding or removing a runtime dependency; deleting, skipping or weakening any test (a replacement is allowed only if it asserts the same or more, logged); destructive git (force-push, history rewrite, branch or worktree deletion, git clean, git worktree prune); touching the other worktrees (once-desktop, /tmp ones) or real user folders; running real desktop or Chrome automation, including scripts/chrome_demo.py and scripts/notepad_demo.py (tests use the existing fake providers).

GIT AND EVIDENCE RULES
- One branch per slice, slice/<phase>-<name>, from up-to-date main. Run git branch --show-current before the first edit of every task and after every merge. Small commits with real line breaks (several -m flags or -F file; never literal \n). Merge to main only with git merge --ff-only after scripts/verify.ps1 passes. Push branch and main.
- docs/ai_engineering_log.md is append-only: git diff --numstat origin/main...HEAD -- docs/ai_engineering_log.md must show 0 deletions.
- Copy and paste raw output into reports; never retype hashes or numbers. Write "I cannot confirm this" when you cannot. Do not write "works" or "validated" unless you ran the real entry point and pasted the result. Quote file:line for code claims.
- A control counts as working only when a test clicks it and asserts an observable effect; connection counting alone is not evidence. Tests run offscreen with tmp_path, never open blocking modals (no QMessageBox or QDialog.exec), never touch real user folders.
- Update docs/PROGRESS.md after every commit (id, status TODO / IN PROGRESS / DONE / PARKED, branch, hashes, pasted pytest summary line).
- You cannot judge visual quality. Enforce visual rules with tests (geometry, no clipped or overlapping text, contrast from tokens) and capture screenshots through the real code path with scripts/capture_screenshots.ps1 into docs/screenshots/latest/ with an INDEX.md; say "captured, not reviewed".

PRE-MADE DECISIONS (do not reopen)
- English UI, sentence case, plain verbs, "automation" everywhere (not "workflow"). No jargon or raw exceptions on screen. Errors are non-modal banners plus a log entry. Destructive actions use an inline two-step confirm. No new runtime dependencies; build the canvas with QGraphicsView and QGraphicsScene. Icons drawn with QPainter or original SVG.
- Sidebar stays exactly Home, My automations, Activity, Settings plus brand plus a status footer. Recording is entered from the create flow, never from Settings.
- Start and Finish are rendered terminals, never persisted as steps. Notes and node positions live in a separate layout record (storage layer, existing migration mechanism, keyed by workflow id and step id) that never affects execution; corrupt records fall back to auto-layout with a banner.
- Editing is applied only through Qt-free controller operations, atomic and validated as a whole by the existing validators. Undo and redo live in controller/, never in the engine, and reverse definition edits only. Editing is disabled during a run. Existing saved workflows must open and run exactly as before (regression corpus test).
- Do not touch credentials or Gemini-key handling beyond existing tests.

QUEUE (user-value order)
1. P4a controller editor session: Qt-free atomic edit operations (rename, update configuration, add step after, insert on connection, delete with reconnect, move, notes, move node), undo and redo; seeded random-operation tests (fixed seed), save and load round trip, regression corpus. No UI.
2. P4b layout record storage and migration; corrupt-record fallback.
3. P4c editor page: select node, inspector forms derived from the validators (never invented fields), save, undo and redo, plus the parked first-time acceptance leg: create from scratch, add a step, save, see it in My automations, open, run, see the result in Activity. Hide any control whose handler is not wired.
4. P4d insert on connection (the plus control, right-click, drag from toolbar), notes, whole-automation validation panel with click-to-navigate.
5. P6 run from the editor and from My automations with live node states, cancel, evidence in the inspector, and the inline approval panel that lists exactly the mutating steps through the existing approval gate (engine/desktop.py approve_desktop_workflow, mutating_kind_names, requires_desktop_approval); never a second approval path. Wire the review page (set_service, the proposal.steps defect).
6. P5 "Record a task" in the create flow into the editor, with a provenance banner derived only from real analysis fields.
7. D1 documentation truth pass: README.md, docs/FEATURES.md (capability, status working/partial/planned/out of scope, file:line, proving test), ARCHITECTURE.md, WORKFLOW_FORMAT.md (derived from the validators; examples verified by a test), SIMILAR_TOOLS.md (neutral; only facts from sources you read this session), KNOWN_LIMITATIONS.md, CHANGELOG.md from git log, docs/DOC_CORRECTIONS.md for every stale claim you fix, and offline docs tests (links exist, flags mentioned exist in app.py). "Working" requires a passing test through the real service or entry point. Never invent a license; if there is no LICENSE file, say so and add a QUESTIONS entry.
8. Test with a worker that ignores cancel to prove the detach path in ui/workers.py cancel_and_join cannot crash at exit.
9. P8 hardening (closing during a run, double clicks, very long names, 500-step automations, missing or read-only data directory, corrupt history database, cancelling twice, a failed run followed by editing); run the full suite three times with python -X faulthandler and paste the three summary lines.
10. P9 parity: docs/MVP_CHECKLIST.md (every old-window capability, new location file:line, covering test, DONE or MISSING). Only if no MVP-scope item is MISSING, the first-time acceptance test passes through app.py's real entry path, and the editor acceptance test passes: make the shell the default, keep the old window with --classic, keep --shell as an alias. Build the exe with once.spec and verify it starts (park with evidence if it fails; do not commit build output). Then final README and USER_GUIDE pass. P7 branching stays parked unless all its gates in docs/design/visual_editor.md are met.

END OF EVERY SESSION
Reply with: ledger rows (id, status, commit hash); raw output of git branch --show-current, git status -sb, git --no-pager log --oneline --decorate -10, the last pytest summary lines, ruff check and ruff format --check; PARKED items with the interim choice; one line per new entry in docs/AUTONOMOUS_DECISIONS.md and docs/QUESTIONS.md; new screenshot paths (captured, not reviewed); and everything you could not verify.