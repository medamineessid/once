# UX audit — the current shell (P1/f)

Date: 2026-10-30. Scope: `ui/shell.py`, `ui/pages/*.py` as merged at e638e5e→85a5893
(the audit reads exactly these revisions). Fixes are scheduled per queue item; the
audit is re-checked at P8 hardening and before P9.

Method: code reading with file:line (below), the existing behavior tests in
tests/test_shell.py, and the user's own findings (docs/PROGRESS.md line 3: buttons
"do nothing", journeys reordered J2-first). I cannot judge pixel beauty; every visual
rule lands with a test (the prompt's rule), in P2/P3.

## 1. Cross-page defects

| # | Defect (evidence) | Where | Fix (owner) |
|---|---|---|---|
| C1 | Blocking modals inside the shell: `QMessageBox.information` in the create flow (ui/shell.py:240-245), `QMessageBox.question` before run (ui/pages/my_automations.py:185-191), two `QMessageBox.warning` (my_automations.py:246,250), `QMessageBox.information` in Settings (ui/pages/settings.py:125-130), `QMessageBox.warning` in Review (ui/pages/review.py:102), plus a modal `dialog.exec()` (settings.py:137) | shell.py, pages | Pre-decided shell rule = non-modal banners + inline two-step confirm; remove blocking modals from the shell. Replace the verifier `QDialog.exec()` with an inline configuration panel (P2; old window keeps the dialog) |
| C2 | The demo run executes synchronously on the GUI thread with no progress and no state anywhere (ui/shell.py:225-226 `service.run_demo()` inline) | shell.py | Run via `ui/workers.py WorkflowWorker`, footer status ("Running…"), banner on finish, Activity entry appears after refresh (P2/P6) |
| C3 | Sidebar footer is static text, never state ("Once Assistive Automation", ui/shell.py:104-106) although the queue needs real controller state ("Ready"/"Running…"/"Needs attention") | shell.py | Status-footer component driven by the service/controller state (P2) |
| C4 | No keyboard shortcuts at all in the shell (no QAction shortcuts anywhere in ui/pages/*, ui/shell.py); prompt requires Ctrl+N, Ctrl+1..4, Enter on primary | all | P2 shell shortcut set, tested |
| C5 | List rows show file names, not automations: My automations rows show `path.name` (ui/pages/my_automations.py:265-267) → `demo-local-workflow.json`; the friendly `workflow.name` is loaded only on selection | my_automations.py | Row shows the automation name + last run status; rename in row needs a default row label (P2) |
| C6 | No timestamps anywhere in Activity: rows are "1. {workflow_id}" with a tooltip repeating id/status/count (ui/pages/activity.py:91-95); `WorkflowRun.started_at` exists (engine/workflow.py:110) and is persisted | activity.py | Human-readable timestamps ("Today 14:22"), newest first with statuses (P2) |
| C7 | Unsaved state and destructive clicks: no undo, no confirm system; the only confirmations are modal (C1) | all | Inline two-step confirm on destructive actions; run cancel button (P4/P6) |

## 2. Per-page notes

### Home (ui/pages/home.py)
- Good: recent-activity block reads the real history (home.py:90-104); honest empty
  text (home.py:74-79).
- D1 Recent activity shows only SUCCEEDED runs (home.py:93-97): failed runs are
  invisible on Home; failed runs deserve a visible entry with plain status (P2).
- D2 Recent activity renders raw ids ("✓ demo-local-workflow completed",
  home.py:100): should say the automation name (id-mapping like C5) (P2).
- D3 The actions panel is a centered 260px column with vertically-centered content
  (home.py:36,52): violates the top-aligned page template (P2 redesign).

### My automations (ui/pages/my_automations.py)
- Good: preview is truly read-only (my_automations.py:149-171); run runs off-thread
  with correct queued connections (my_automations.py:197-227) and the pause for the
  earlier heap-corruption bug is commented (my_automations.py:218-222).
- D4 The "Run" confirmation is a modal question (C1) — converts to inline two-step
  confirm on the Run button (P2).
- D5 `_on_run_failed` and `_show_page_error` show raw `WorkflowValidationError` text
  (my_automations.py:244-250): validator messages are tested strings, but the page
  shows them as an ellipsis "Error: ..." without next-step guidance (P2 banner).
- D6 After a run finishes, Activity is not refreshed (page-local only) (P6 run flow).

### Activity (ui/pages/activity.py)
- Good: purely read-only (activity.py:66-79); selection shows per-step lines.
- D7 Steps shown as "{step_id} — {status} — {message}" (activity.py:73-75): user
  names instead of ids where available (P2).
- D8 No timestamps (C6) and no empty-state with a next step — it says only "Select
  a run to see details." even when there are zero runs ever (activity.py:96) (P2).

### Create automation (ui/pages/create_automation.py)
- D9 The page dead-ends: the description is stored nowhere, and the shell shows a
  blocking "Not available yet" modal (C1); the visual editor replaces this page
  (create-from-scratch becomes the editor; the typed-description path is dropped
  until the recording pipeline provides it — P4/P5). Until the editor lands, the
  page keeps working but stays the acknowledged "describe your task" step; the modal
  is replaced by a visible banner with a plain "what to do next" line (P2).

### Settings (ui/pages/settings.py)
- Good: only real configuration remains (authorized folder + verifier), placeholder
  groups already removed and asserted by tests/test_shell.py:132-146.
- D10 Modal information + modal exec (C1) (P2).
- D11 `verifier_configured` signal is emitted but connected to nothing
  (BUTTON_AUDIT §2; settings.py:140): either surface a real effect (status line +
  banner "Checker configuration saved") in the page itself or drop the signal (P2).

### Review (ui/pages/review.py)
- D12 **Latent crash**: `load_proposal` iterates `proposal.steps`
  (ui/pages/review.py:122) but `ProviderDraft` has only `goal`,`workflow`
  (ai/models.py:27-33). Guarded today only because nothing calls it with a real
  draft. Fix in P6 when the review journey wires this page.
- D13 The shell never injects the service into this page (ui/shell.py:157-160
  injects home/activity/my_automations/settings only), so approval can never work
  (matches the earlier ledger note) (P6).
- D14 Naming: a saved workflow opened from My automations lands on a screen titled
  "Review automation" (ui/pages/review.py:44): opening and reviewing are different
  intents; P2 relabels the opened-workflow mode ("Automation details").

## 3. Heuristics checklist (applied at P2; baseline now)

| Heuristic | Baseline verdict (evidence) | P2/P3 target |
|---|---|---|
| Visible system status | Partial: footer static (C3), run progress only as appended detail text (my_automations.py:229-237) | Footer status + run banner + node badges |
| Plain language | Mostly good (steps shown with kind+name+message); raw ids on Home/Activity (D2, D7); validator strings shown raw (D5) | Strings module ui/strings.py, no ids in default text |
| User control and undo | Weak: no undo of anything, no cancel control in the shell (old window had one, ui/main_window.py:82) | Editor undo/redo + run cancel |
| Consistency | OK tokens; inconsistent layout alignment (D3; pages center content or vary) | One page template |
| Error prevention | Run confirm modal exists (C1); editor will validate before save (engine validator) | Inline confirm, whole-definition validation panel |
| Recognition over recall | Weak: ids instead of names (C5/D2/D7) | Friendly names everywhere |
| Minimal clutter | Current pages are sparse; settings OK after B3 removals | Keep; editor tray hides unsupported kinds |
| Helpful empty states | Home/My automations have them; Activity lacks the "no runs yet" case (D8); create page is a dead end (D9) | One next step per empty page |

## 4. What I could not evaluate

- Visual quality of the current shell (I can't judge images; screenshots exist at
  docs/screenshots/layout-foundation/ and latest/, "captured, not reviewed").
- French-language needs beyond centralising strings (QUESTIONS.md Q1).
