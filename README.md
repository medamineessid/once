# Once: record a task once, replay it on Windows

Record a task once, read every step in plain English, approve what may touch your
desktop, and let a deterministic engine replay it. Once is a local-first Windows
app written in Python and PySide6 (Qt Widgets), and it never lets a model decide
what to click: when a recorded step cannot be resolved safely it asks you or
stops, instead of guessing.

Status: current
Last verified: 2026-11-26 · `main f2e6ca3`
Owner: owner (all lanes)

## Start here

- `docs/STATE.md` — what works now, with an evidence level per capability.
- `docs/CONTEXT.md` — one page on what Once is and how the code is laid out.
- `docs/decisions.md` — decisions that are not re-litigated.
- `AGENTS.md` — boundaries and the non-negotiable rules.
- `docs/WORKFLOW.md` — branch, pull-request and append-only log rules.
- `docs/COLLABORATOR.md` — how your work reaches `main`.
- `docs/PLAN.md` — the three-lane plan and the task status table.

## Status and evidence

Evidence has three levels and a doc never invents a fourth: **real desktop**
(a person ran it on a real PC), **tests only** (green pytest, no real run), and
**not verified**.

**Proven on a real desktop.** The Notepad flow — record, approve the application
once, run it twice — ended `SUCCEEDED` both times with no window left behind
(`scripts/prove_notepad_flow.py`, `shots/after/notepad-flow.json`). The kill
switch `Ctrl+Alt+Q` stopped a live run (`shots/after/kill-switch.json`).

**Tests only.** Workflow validation and persistence, the approval gate, the
shell and its pages, run outcomes, the file-verification primitives, and the
button, sidebar and dialog fixes in PR #27 and #29.

**Not wired yet.** Smart replay resolves a recorded step by its clues and is
covered by tests, but the flag `ONCE_SMART_REPLAY` is read only in
`engine/smart_replay.py` — nothing in `app.py`, `controller/` or `ui/` reads it,
so the app path does not use it yet. The Chrome tab case is not built. The UI
audit harness is an open draft (PR #12).

## What it does

- **Record** — window launches and closes, UI Automation control clicks, text
  entry and allowlisted shortcuts are captured locally, with password fields
  redacted.
- **Review** — the draft shows each step as replayable or observation-only, and
  the application is approved once by path and SHA-256.
- **Replay** — only steps that carry a target are performed; a step that cannot
  find its window or control fails with a plain reason, and the run says what
  actually happened (`Succeeded`, `Partly performed`, `Observation only —
  nothing was performed`, `Failed`, `Cancelled`).

## Quick start

Requirements: Windows 10 or 11 (x64) and Python 3.12 or newer.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe app.py
```

The app opens on **Home** with two entry points: **Record** (perform the task
once) and **Build** (place the steps yourself). `app.py --classic` opens the
older diagnostic window; `docs/first_run.md` walks the same path with the places
people actually get stuck.

## Run the tests

```powershell
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\python.exe -m pytest -q
.\scripts\verify.ps1        # what CI runs
```

The suite is offscreen (`QT_QPA_PLATFORM=offscreen`) and every test works inside
pytest's `tmp_path`. Two opt-in groups need a real desktop:
`ONCE_REAL_DESKTOP=1` runs the Notepad end-to-end test, and
`docs/REAL_DESKTOP_CHECKLIST.md` is a checklist a person runs by hand.

## Documentation map

- [`docs/README.md`](docs/README.md) — the index of every living document.
- [`docs/STATE.md`](docs/STATE.md) — capabilities and their evidence level.
- [`docs/PLAN.md`](docs/PLAN.md) — the three lanes, the tasks and their status.
- [`docs/REAL_DESKTOP_CHECKLIST.md`](docs/REAL_DESKTOP_CHECKLIST.md) — the
  person-run checklist.
- [`CHANGELOG.md`](CHANGELOG.md) — what changed, including defects found while
  verifying it.
- [`docs/decisions.md`](docs/decisions.md) — architectural decision records.
- [`docs/ai_engineering_log.md`](docs/ai_engineering_log.md) — append-only
  engineering log.

## Contributing

Work happens on `feat/<lane>-<task>` branches described by a brief in
[`tasks/`](tasks/TEMPLATE.md). Read [`docs/COLLABORATOR.md`](docs/COLLABORATOR.md)
first: it has the run commands, the folder map, the hard rules and how a change
reaches `main`. `scripts/check_pr_guards.py` rejects a pull request that deletes
a test, adds an unexplained skip, changes dependencies without the
`dependency-approved` label, or touches files outside its brief.

## License

No license file yet. Until one is added, treat the repository as
all-rights-reserved and ask the owner before reusing it.

## Legacy: verifier and orchestrator

Before this line, Once was described as a supervised test-and-fix orchestrator:
bounded invoice verification, redacted evidence bundles and coding-agent
proposals on separate branches. That code still exists (`engine/verifier.py`,
`engine/acceptance.py`, `engine/agent_change.py`, `integrations/coding_agent.py`)
and the safety reasoning behind it still applies, but it is not the product
described above and nothing in the current record-review-replay path reaches it.
