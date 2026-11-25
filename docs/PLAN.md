# Once — three-lane team plan (3 weeks)

## Finish line

The demo is the finish line: record once; change the screen (more tabs, wanted
result lower in the list); replay finds the right thing or asks, and never
clicks wrong. Lane A owns replay semantics; lane B owns what the user sees; lane
C owns proof and delivery. A task is DONE only when its brief's acceptance
commands have been run and their real output is pasted. No capability is claimed
at `real desktop` level without an approved real-PC run.

## Lanes, tasks and sizes

| lane | scope | tasks | sizes |
| --- | --- | --- | --- |
| A — replay core (owner) | `engine/`, `integrations/`, `recorder/`, `storage/`, `controller/`, step schema, `docs/ai_engineering_log.md`, `docs/STATE.md` | A1 wire the smart-replay flag into the app path; A3 prove the desktop adapter and the approval → rerun loop; A5 Chrome case: new tab, search, choose the result by its site even when order changes, using Chrome DevTools tab and page APIs and the existing resolver; A4 standing duty: keep the schema and architecture tests green | A1 M, A3 L, A5 L |
| B — app experience | `ui/`, UI tests, UI screenshots | B1 TASK-007 M; B2 TASK-008 M; B3 TASK-009 M; B4 TASK-010 M; B5 TASK-011 S; B6 TASK-012 M; B7 TASK-013 M | S–M |
| C — proof and delivery | `tests/`, packaging scripts, `docs/DEMO.md`, `docs/evidence/` | C1 TASK-014 M; C2 TASK-015 S; C3 TASK-016 M; C4 TASK-017 S; C5 TASK-018 S; C6 TASK-019 M; C7 TASK-020 M | S–M |

A2 (bounded, postcondition-checked typing) is a **stretch goal**, not part of
the finish line. A4 is a **standing duty**, not a task to schedule. Lane A has
no collaborator brief in this PR: it is owner-only and lands in its own PRs.
Lane B and C briefs live in `tasks/`; each names exact files and the commands
the owner has run on this base.

## Week 0 — setup before Week 1

- Merge this PR; protect `main`; auto-delete merged branches; remove SonarCloud.
- Kickoff call: each person gets the app running locally.

## Three-week order

- **Week 1 — unblock the surface.** Owner settles draft PR #12 and lands B1
  (TASK-007). In parallel C1 (TASK-014) adds the Chrome-style tab and
  result-lower scenarios, and C2 (TASK-015) writes the real-PC evidence
  template. Owner starts A1 and carries out A4.
- **Week 2 — fix what the audit found.** B2–B5 (TASK-008..011) take V1–V10 in
  small groups, then B6 (TASK-012) adds the pick-one dialog and sample-fed run
  report. C3 (TASK-016) runs the PyInstaller spike only after
  `dependency-approved` is granted. Owner lands A5 and works A2 if time allows.
- **Week 3 — prove and hand over.** B7 (TASK-013) adds the Settings switch
  screen. C4 (TASK-017) builds the demo kit from C1+C2; C5 (TASK-018) adds the
  privacy checklist from C2. C6 (TASK-019) is a person running the real-PC
  checklist on their own PC; C7 (TASK-020) records and rehearses the demo.
  Owner lands A3, reruns the full gate, records the
  evidence level of every claim and runs the finish-line demo. Report anything
  left unfinished; do not quietly close it.

## Daily and weekly rhythm

- **Session rule:** re-read repo state before acting — `git.exe branch
  --show-current`, `git.exe status --short`, fetch and `gh.exe` state; work only
  on `feat/<lane>-<task>` from up-to-date `main`, with absolute paths.
- **Daily 3-line update:** done, next, stuck. Post it every day in the team
  channel.
- **Friday integration:** merge, run the demo script on a clean copy, list what
  failed.
- **Explain-back:** the author explains each big PR in 5 lines. In week 3,
  practise the explanation out loud.
- **Peer review:** lane B and C read each other's PRs for clarity; the owner
  merges.
- **Screenshot rule:** a person looks at every screenshot and writes one
  sentence per image. A capture nobody has opened is not evidence, whatever its
  file name or size says.
- Run the brief's acceptance commands, paste the real last lines and never
  write DONE from an unrun command. Open one PR per brief using
  `.github/pull_request_template.md`, then ask for review with
  `docs/REVIEW_PROMPT.md`.
- **Docs-versus-code rule:** if `docs/STATE.md`, a brief or an old doc disagrees
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
- Smart replay is observation-only in the app until A1/A3 land; UI work must not
  imply typing or replay that does not exist.
- Real-PC evidence cannot be produced by CI; C2 must leave gaps explicit.
- PyInstaller may need a new dependency; C3 waits for owner approval.
- UI edits can drift from `docs/UI_SPEC.md`; B tasks must re-run the audit.
- Chrome result order and site identity come from DevTools APIs; A5 fails closed
  and asks instead of guessing if those APIs are unavailable.
- Docs can drift from code; apply the docs-versus-code rule above.
