# Open questions (non-blocking)

The default is applied immediately; change it by answering here and re-touching the
answer in docs/AUTONOMOUS_DECISIONS.md. Nothing in this queue blocks work.

## Q1 — French UI translation timing

- Question: the user runs Windows in French locale; when should the UI text become
  French?
- Default chosen: English UI during the MVP; every shell/editor string goes through
  one module (`ui/strings.py`) so a later translation is mechanical. Translate after
  P9 with a language constant, not per-page edits.
- How to change: answer "now" and the translation becomes a dedicated slice.

## Q2 — "Describe a task in plain language" input

- Question: today's Create page asks the user to type a task description, but the
  controller has no builder that turns text into steps (ui/shell.py:233-245 says so
  in its own message), and the visual editor replaces the list-style create page.
- Default chosen: the typed-description entry point is REPLACED by "Create from
  scratch" (opens the visual editor with an empty chain) plus "Record a task" (P5).
  The description input is removed from the create surface until a real text→steps
  path exists (it never silently pretends to work).
- How to change: answer "keep the text box" and it returns as a note/template helper
  in the editor.

## Q3 — Run confirmation style

- Question: the old window confirms a run with a `QMessageBox.question`
  (ui/pages/my_automations.py:185-191); the shell must drop blocking modals.
- Default chosen: "Run" buttons become inline two-step confirm (first click shows
  "Confirm run?" on the button/inline area for 5 seconds, second click runs) —
  same intent, no modal. Mutating workflows still go through the separate approval
  gate before any run (P6).
- How to change: answer "no confirm for read-only runs" and read-only runs start on
  first click.

## Q4 — Timestamp style in Activity

- Question: which locale/format for run timestamps (today's date is locale-neutral)?
- Default chosen: local time, "Today 14:22", "Yesterday 09:05", otherwise
  "2026-10-30 09:05"; UTC rendering only inside evidence details.
- How to change: answer with a preferred format.
