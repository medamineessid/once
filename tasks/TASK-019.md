# TASK-019 — A person runs the real-PC checklist on their own PC

Lane: `tests` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/tests` · Size: `M`

## Goal

Turn "real desktop" from a claim into a written record: one checklist a person
works through on their own Windows machine, filled in by hand, with the result
of every line. The checklist covers launching the packaged or source app,
recording a short task, replaying it, approving one mutating step, stopping a
run, and confirming the app-data folder was left usable. No automated run can
produce this evidence, so the deliverable is the document plus one genuinely
completed copy.

## Files allowed

- `docs/evidence/REAL_PC_RUN.md` (new)
- `docs/evidence/REAL_PC_RUN_completed.md` (new, one real filled-in run)

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`, `ui/`
- `.github/`, `scripts/`, `docs/ai_engineering_log.md`, `docs/STATE.md`,
  `docs/PLAN.md`, `docs/COLLABORATOR.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_docs_truth.py
ruff check .
ruff format --check .
```

Every line of the checklist names the observable result to write down (window
title, banner text, exit code). "It worked" is not a line. Paste the real
summary lines in the PR, and say plainly which lines the person has not run yet.

## Screenshots

App window only, one sentence per image, opened and described by the person who
ran the checklist: the app at first launch, the approval panel before approving,
and the run result after Stop. Full-desktop captures stay on the person's
machine and are never committed.

## Out of scope

Automating the checklist, claiming a real-PC pass from CI, or changing what the
app does when a line fails. A failing line is reported, not fixed here.

## Issues

- Only a person at a real Windows desktop can fill this in; an agent cannot.
- The completed copy records one machine and one Windows build, not "Windows".
- A packaged build and a source run must be recorded separately, not merged.

## Notes

A line may say "not run". That is a real result and is worth more than a tick
nobody earned. Link the evidence level in `docs/PLAN.md` to this document.
