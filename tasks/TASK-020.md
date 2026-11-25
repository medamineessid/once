# TASK-020 — Record and rehearse the demo

Lane: `tests` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/tests` · Size: `M`

## Goal

The demo is the finish line, so it must be written down and rehearsed until it
runs without improvising: the exact order of clicks, what to say for each
screen, how long each part takes, and what to do when a step fails live. The
deliverable is a script a second person could follow plus a rehearsal log with
the real timings from at least two run-throughs on one machine.

## Files allowed

- `docs/DEMO.md`
- `docs/evidence/DEMO_REHEARSAL.md` (new)
- `shots/demo/` (app-window captures only)

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

Paste the real summary lines, then paste the two rehearsal timings as they were
recorded, including any part that overran.

## Screenshots

App window only, one sentence per image, described by the person who rehearsed:
the four demo screens in the order the script names them, at 960x600 and
1920x1020. A capture that is not in the script's order is not demo evidence.

## Out of scope

Adding features to make the demo look better, changing the resolver or the
approval gate, or recording over a real desktop with personal data on screen.

## Issues

- The demo depends on A3 and A5 landing; until then the script must say which
  parts are observation-only.
- Rehearsal timings come from one machine and are not a performance claim.
- A live failure during the demo needs a stated fallback, not a retry loop.

## Notes

Write the fallback line for each risky step ("if the window is not found, say
this and move on"). Rehearse once alone and once with an audience question.
