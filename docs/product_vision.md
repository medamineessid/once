# Once product vision

Status: current
Last verified: 2026-11-26 · `main f2e6ca3`
Owner: owner (all lanes)

Once records what you do on a Windows desktop once, shows it back as plain
steps, and replays it — but only after you approve, and only when every step can
name its target. When a step cannot be resolved safely, Once asks or stops. It
does not guess, and it does not let a model decide what to click.

## The loop

1. **Record** the task, or build it step by step.
2. **Review** every step in plain English and see which ones Once can replay.
3. **Approve** the application (path + SHA-256) and the actions that will run.
4. **Replay** deterministically, with an honest outcome: `Succeeded`,
   `Partly performed`, `Observation only — nothing was performed`, `Failed` or
   `Cancelled`.
5. **Read what happened** in Activity, with the first failure reason in plain
   words and per-step evidence.

## Smart replay

A recorded step keeps clues about what it targeted — window title, control name,
automation id, nearby text. Smart replay re-resolves the element from those clues
at run time, so a window that moved or a list that reordered still resolves to
the right control. When the clues match nothing, or match more than one thing,
Once asks a question or stops: a wrong click is worse than a stopped run.

The resolver and its policy layer are implemented and tested
(`engine/smart_replay.py`, `integrations/uia_adapter.py`). The app path does not
use them yet: `ONCE_SMART_REPLAY` is read only in `engine/smart_replay.py` (grep,
2026-11-26). Until that is wired, replay uses the recorded steps exactly as they
are.

## Local-first

Runs happen on your machine. Recordings, workflows, approvals and history live
under `%LOCALAPPDATA%\Once`. Nothing reaches the network unless you have
configured that integration and consented, and cloud analysis of a recording is
disabled by default.

## Non-goals

- **No AI at replay time.** A model may help draft a recording; it never decides
  what to click and never emits executable code.
- **Windows only.** Windows 10/11 x64, including its UI Automation API.
- **Not an agent that decides by itself.** No autonomous merges, pushes, shell
  commands or unapproved desktop actions.
- **No permanent deletion and no silent overwrite** of user files.
- **No universal coverage.** An application with no usable accessibility
  information is reported as such rather than poked at by coordinates.

## Legacy line

Before this line Once was a supervised test-and-fix orchestrator (invoice
verification, evidence bundles, coding-agent diffs); that code remains in the
repository, is not reached by the record-review-replay path, and is documented
as legacy in the README.
