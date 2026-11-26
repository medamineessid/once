# Documentation index

Status: current
Last verified: 2026-11-26 · `main 6724552`
Owner: owner

Every living document is listed here with what it is for, whether it is current
or historical, and which lane owns it. A document that is not in this table is
not a living document: it is history under `docs/archive/`, or it is one of the
conventional root files (`README.md`, `CHANGELOG.md`, `AGENTS.md`, and the
notices).

## Naming

- New documents use **lowercase-with-hyphens**: `real-desktop-checklist.md`,
  `run-outcomes.md`.
- **UPPERCASE** names are reserved for conventional root files: `README`,
  `CHANGELOG`, `AGENTS`, `LICENSE`.
- Older files that predate the rule keep their names; renaming them would break
  links that this index exists to keep honest.

## Living documents

| Doc | Purpose | Status | Owner |
| --- | --- | --- | --- |
| `README.md` | Entry point: pitch, status and evidence, quick start, tests | current | owner |
| `CHANGELOG.md` | What changed, and the real defects found while verifying it | current | owner |
| `AGENTS.md` | Architecture boundaries and the non-negotiable safety rules | current | owner |
| `DESIGN.md` | Native Qt design system, tokens and typography | current | lane B (app experience) |
| `docs/CONTEXT.md` | One page: what Once is, folder map, glossary, legacy modules | current | owner |
| `docs/STATE.md` | Capabilities with an evidence level, known defects, next steps | current | owner |
| `docs/PLAN.md` | Lanes, tasks, the status table and evidence levels | current | owner |
| `docs/WORKFLOW.md` | Branch, pull-request and append-only log notes and exceptions | current | owner |
| `docs/WORKING_AGREEMENT.md` | Hard rules, evidence rules, stop protocol | current | owner |
| `docs/COLLABORATOR.md` | How your work reaches `main` | current | owner |
| `docs/REVIEW_PROMPT.md` | How to review a PR, with three verdicts | current | owner |
| `docs/REVIEW_GUIDE_SMART_REPLAY.md` | One page for reviewing a smart-replay step | current | lane A (replay core) |
| `docs/SMART_REPLAY.md` | How smart replay resolves a recorded step | current | lane A (replay core) |
| `docs/desktop_automation.md` | Desktop and browser engine: what exists, target rules, limits | current | lane A (replay core) |
| `docs/known_limits.md` | What Once cannot do, in plain words | current | lane A (replay core) |
| `docs/product_vision.md` | Record, review, approve, replay; smart replay; non-goals | current | owner |
| `docs/UI_DEFECTS.md` | V1–V10, each with a capture and its fix state | current | lane B (app experience) |
| `docs/acceptance_checklist.md` | The 20-minute manual pass before a release | current | lane C (proof and delivery) |
| `docs/MVP_CHECKLIST.md` | The MVP gate, with the proof for each row | current | lane C (proof and delivery) |
| `docs/demo_checklist.md` | The demo script and its fallback | current | lane C (proof and delivery) |
| `docs/REAL_DESKTOP_CHECKLIST.md` | The checklist a person runs on their own PC | current | lane C (proof and delivery) |
| `docs/first_run.md` | The first-run walkthrough and the places people get stuck | current | lane B (app experience) |
| `docs/PERMISSIONS.md` | What past sessions were allowed to do | current (ledger) | owner |
| `docs/TEMPLATE.md` | The task-brief template | current | owner |
| `docs/contracts/run-outcomes.md` | Step and run status contract | current | lane B (app experience) |
| `docs/contracts/run_events.md` | Run event stream contract | current | lane B (app experience) |
| `docs/design/visual_editor.md` | Editor design record, with a status note | current | lane B (app experience) |
| `docs/specs/visual_workflow_editor.md` | Editor specification | current | lane B (app experience) |
| `docs/ui-reference/README.md` | What a UI capture must be to count | current | lane B (app experience) |
| `docs/screenshots/latest/INDEX.md` | The screenshot index | current | lane B (app experience) |
| `docs/ai-assisted-development.md` | A collaborator's write-up, kept as a reference | current | collaborator |

### Append-only files (no header, by rule)

Two living files deliberately carry no header, because editing their top matter
is itself an edit to an append-only record:

- `docs/decisions.md` — dated decision blocks; new decisions are appended.
- `docs/ai_engineering_log.md` — the engineering log; entries are never edited.

Everything in the table above must keep its header.

## Historical

`docs/archive/` holds the rest, in full and unedited apart from a note at the top
saying it is historical: the agent prompts (`AGENT_PROMPT`, `LANE_B_PROMPT`,
`SOLO_PROMPT`), the blocked/parked/questions notes, the autonomous decisions, the
UX and button audits, the older progress files (`PROGRESS`, `PROGRESS-DESKTOP`,
`PROGRESS-UI`), the lane B notes (`docs/archive/lane_b/`) and
`ui_migration_plan.md`.

## The rule this index enforces

`tests/test_docs_index.py` fails when a document listed above is missing or has
lost its three-line header (Status, Last verified, Owner), when a local link in
`README.md` does not resolve, or when `docs/STATE.md` or `docs/CONTEXT.md` grow
past their limits. A stale page should fail a test rather than mislead a reader.
