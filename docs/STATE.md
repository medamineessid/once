# State — once (as of the last owner PR)

Status: current
Last verified: 2026-11-26 · `main f2e6ca3`
Owner: owner


Owner-only. Updated by the owner in the PR that changes what works, so a fresh
session can continue from the repo alone.

## Last updated

2026-11-26 — `main 603a326`

## Capabilities

| capability | status | evidence level | notes |
| --- | --- | --- | --- |
| Bounded workflow model and validation | Done | tests only | `engine/workflow.py`, `storage/workflows.py`; schema 4 loads older files unchanged |
| Workflow persistence and history SQLite | Done | tests only | `storage/`; runs, step results, decisions |
| GUI: shell, Home, My automations, Activity, Settings, editor | Done | tests only | `ui/`, `app.py`; shell is the default, `--classic` is the escape hatch |
| Record → review → approve → run a desktop task | Done for launch/close | real desktop (Notepad) | `scripts/prove_notepad_flow.py`; typing and clicks replay only when the step carries a descriptor |
| Buttons and sidebar defects V5, V8 | Fixed | tests only | PR #27; `ui/components/buttons.py`, `ui/components/sidebar_item.py` |
| Delete confirmation defect V1 | Fixed | tests only | PR #29; `ui/components/delete_confirm.py` + `ui/components/dialog.py` |
| Smart replay (resolver, policy, adapters, lab) | Implemented, observation-only in the app | tests only | `ONCE_SMART_REPLAY` is read only in `engine/smart_replay.py`; nothing in `app.py`, `controller/` or `ui/` reads it (grep, 2026-11-26) |
| UI audit harness and spec | Not merged | not verified | draft PR #12 (`ui/audit-harness-wip`) |
| Team workflow: branch protection, merge settings | Done | GitHub API output | required CI check, 1 review, code-owner review; squash and rebase disabled; branches auto-deleted |
| File-management integration | Archived / historical | not verified | `docs/archive/`; not built in this line |

## Known defects

- V2, V3, V4, V6, V7, V9, V10 are open in `docs/UI_DEFECTS.md`.
- Smart replay is not wired into the app path; the desktop adapter is proven
  only for the Notepad launch/close flow, not for the approval → rerun loop.
- Remaining `QMessageBox` call sites are not yet on the tokenised dialog.

## Next five steps

1. Land the UI audit harness (draft PR #12) so the remaining V-defects can be
   enumerated and checked.
2. Close V2 and V3 on My automations (approval panel, toolbar row).
3. Wire the smart-replay flag into the run path (A1), then prove the adapter
   and the approval → rerun loop (A3).
4. Take the Chrome tab case (A5) or record why it slips.
5. Run `docs/REAL_DESKTOP_CHECKLIST.md` on a real PC and record the result in
   `docs/evidence/TEMPLATE.md`.

## How to read an evidence level

- **tests only** — green pytest for the relevant tests; no real desktop run.
- **tests + own real screen** — tests green **and** captures from the real
  `app.py` path that a person has looked at.
- **real desktop** — an approved, repeated run on a real Windows desktop with a
  completed `docs/evidence/TEMPLATE.md`.
- **not verified** — not done; claim only if you are prepared to run it.
