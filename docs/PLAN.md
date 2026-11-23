# Once — three-lane team plan (3 weeks)

## Finish line

This line is finished when a first-time user can open Once, run an allowlisted
workflow, see an honest run report, and review the evidence without any claim
that outruns the checks in this repo. Lane A owns replay semantics; lane B owns
what the user sees; lane C owns proof and delivery. A task is DONE only when its
brief's acceptance commands have been run and their real output is pasted. No
capability is claimed at `real desktop` level without an approved real-PC run.

## Lanes, tasks and sizes

| lane | scope | tasks | sizes |
| --- | --- | --- | --- |
| A — replay core (owner) | `engine/`, `integrations/`, `recorder/`, `storage/`, `controller/`, step schema, `docs/ai_engineering_log.md`, `docs/STATE.md` | A1 wire the smart-replay flag into the app path; A2 add bounded, postcondition-checked typing; A3 prove the desktop adapter and the approval → rerun loop; A4 keep the schema and architecture tests green | A1 M, A2 L, A3 L, A4 S |
| B — app experience | `ui/`, UI tests, UI screenshots | B1 TASK-007 M; B2 TASK-008 S; B3 TASK-009 S; B4 TASK-010 S; B5 TASK-011 S; B6 TASK-012 M; B7 TASK-013 M | S–M |
| C — proof and delivery | `tests/`, packaging scripts, `docs/DEMO.md`, `docs/evidence/` | C1 TASK-014 M; C2 TASK-015 S; C3 TASK-016 M; C4 TASK-017 S; C5 TASK-018 S | S–M |

Lane A has no collaborator brief in this PR: it is owner-only and lands in its
own PRs. Lane B and C briefs live in `tasks/`; each names exact files and the
commands the owner has run on this base.

## Three-week order

- **Week 1 — unblock the surface.** Owner settles draft PR #12 and lands B1
  (TASK-007). In parallel C1 (TASK-014) adds the Chrome-style tab and
  result-lower scenarios, and C2 (TASK-015) writes the real-PC evidence
  template. Owner starts A1 and A4.
- **Week 2 — fix what the audit found.** B2–B5 (TASK-008..011) take D1–D10 in
  small groups, then B6 (TASK-012) adds the pick-one dialog and sample-fed run
  report. C3 (TASK-016) runs the PyInstaller spike only after
  `dependency-approved` is granted. Owner works A2.
- **Week 3 — prove and hand over.** B7 (TASK-013) adds the Settings switch
  screen. C4 (TASK-017) builds the demo kit from C1+C2; C5 (TASK-018) adds the
  privacy checklist from C2. Owner lands A3, reruns the full gate and records
  the evidence level of every claim. Anything still BLOCKED is reported, not
  quietly closed.

## Daily workflow

1. Run `git.exe branch --show-current` and `git.exe status --short`; work only
   on `feat/<lane>-<task>` from up-to-date `main`, with absolute paths.
2. Read the brief and this plan. If a dependency is BLOCKED, stop and say so.
3. Make the smallest change that satisfies the brief. No safety, schema or
   approval changes from lanes B/C.
4. Run the brief's acceptance commands: pytest, `ruff check .`,
   `ruff format --check .`. Paste the real last lines; never write DONE from an
   unrun command.
5. Open one PR per brief using `.github/pull_request_template.md`, then ask for
   review with `docs/REVIEW_PROMPT.md`. The owner merges; lanes never do.
6. **State drift rule:** if `docs/STATE.md`, a brief or an old doc disagrees
   with the code and pasted test output, the repo state wins. Report the drift
   to the owner and leave `docs/STATE.md` untouched.

## Evidence levels

Use exactly one of these in every PR and in `docs/STATE.md`:

- **tests only** — the named pytest checks are green; no real desktop run.
- **tests + own real screen** — tests are green and app-window captures came
  from the real `app.py` path; unread/unseen captures do not count.
- **real desktop** — an approved, repeated run on the real Windows desktop with
  the adapter and the full flow, plus a completed `docs/evidence/TEMPLATE.md`.

`not verified` is a status, not a level: use it when nothing above was run.

## Risks

- Draft PR #12's audit tests are red; B1 cannot be called done until they pass.
- Smart replay is observation-only in the app until A1/A2 land; UI work must not
  imply typing or replay that does not exist.
- Real-PC evidence cannot be produced by CI; C2 must leave gaps explicit.
- PyInstaller may need a new dependency; C3 waits for owner approval.
- UI edits can drift from `docs/UI_SPEC.md`; B tasks must re-run the audit.
- Docs can drift from code; apply the state drift rule above.
