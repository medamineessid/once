# Context

Once is a local-first desktop app on Windows for describing, running and
reviewing bounded workflows. It is offline by default; every real run starts on
the machine, and nothing reaches a network service unless the user configures
one.

## What it does, in one page

A user either describes a task, opens a saved workflow, or opens a recorded
session. Once runs only allowlisted, typed actions against explicit targets,
with every step returning an observable outcome (SUCCEEDED, FAILED, SKIPPED,
OBSERVED, etc.) that is persisted and shown in plain language. The inference,
recording and smart-replay pieces feed the verifier with candidates or context;
they never execute anything themselves. The deterministic engine owns the only file
touches.

## One-page architecture

- `engine/` — the core: workflow model, validation, planner, executor, recovery.
- `storage/` — SQLite history and the workflow JSON store.
- `controller/` — Qt-free services the UI calls.
- `ui/` — PySide6 widgets and pages only; no file-system mutation.
- `integrations/` — desktop, browser and coding-agent boundaries.
- `recorder/` — event capture and redaction.
- `tests/` — mirrors the package layout.
- `scripts/` — verification gate, fixtures and audit tooling.
- `docs/` — decisions, specs, status, the append-only log and the governance
  guides.

## Glossary

- **Workflow** — an ordered list of steps with explicit intent fields and, when
  recorded, a descriptor.
- **Descriptor** — the recorded element's evidence, stored in the step schema only
  when smart replay is on.
- **Verifier / orchestrator** — the older name for the decision-and-test loop;
  today's code no longer runs a separate voting engineer. See the LEGACY note
  below.
- **Approval gate** — the point where a human confirms an action that could
  mutate the desktop or an agent's branch.
- **Evidence** — untrusted output (logs, verifier output, monitoring events) kept
  delimited and redacted until review.

## Folder map

| folder | what lives there |
| --- | --- |
| `engine/` | core domain and the only file mutations |
| `storage/` | SQLite history and workflow JSON |
| `controller/` | Qt-free application services |
| `ui/` | PySide6 widgets and pages only |
| `integrations/` | desktop, browser and coding-agent boundaries |
| `recorder/` | event capture and redaction |
| `tests/` | mirrors the package layout |
| `scripts/` | verification gate, fixtures, audit tooling |
| `docs/` | decisions, specs, status, the append-only log and governance guides |

## Legacy modules

These modules already exist. Until they are reimplemented in the current line,
they are historical for this document's purposes only. No current smart-replay,
approval or verifier flow in the app reaches them; do not delete or edit them
from this PR.

- `engine/verifier.py`
- `engine/acceptance.py`
- `engine/agent_change.py`
- `engine/loop.py`
- `engine/scanner.py`
- `engine/filters.py`
- `integrations/coding_agent.py`

## Notes

- This page is owned by the owner PR that changes what works; a doc-only task
  keeps it honest only against the listed line limits, not the whole picture.
- History that predates the current line lives in `docs/archive/`.
