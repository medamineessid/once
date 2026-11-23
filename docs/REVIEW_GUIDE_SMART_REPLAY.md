# Review guide: one step through smart replay

A one-page walkthrough for explaining this code in a demo. Every claim below is
about code that is in the repository now. Where something is not finished, the
guide says so instead of pretending.

The design document is `docs/SMART_REPLAY.md`; this guide is the tour of the
code that implements it.

## The path of one step, in order

1. **The step was recorded.** The recorder writes events; saving a recording
   builds a draft (`ui/shell.py`, `build_raw_draft`) and turns each event into a
   step. The step keeps a *descriptor*: a bag of independent clues about what
   was clicked, not a coordinate.

2. **The descriptor is made** — `integrations/uia_adapter.py`,
   `descriptor_from_element(...)` (live element) and `descriptor_from_event(...)`
   (recorded event), both filling `element_clues(...)`. The result is a
   `StepDescriptor` (`engine/workflow.py`) holding `surface` (`DESKTOP`/`WEB`),
   `clues`, and an optional `position_hint`.

3. **The descriptor is saved and validated.** `storage/workflows.py`,
   `_descriptor_to_dict` / `_descriptor_from_dict`, under
   `schema_version: 4` on the step\'s `descriptor` key. Loading rejects unknown
   or missing fields with `WorkflowValidationError`; `WorkflowRunner.validate`
   (`engine/workflow.py`) runs before anything executes. Old files (schema 1–3)
   still load and are rewritten in the new shape only when the user saves.

4. **The step reaches the runner.** `ReplayExecutor.execute`
   (`engine/replay.py`) → `WorkflowRunner.run` (`engine/workflow.py`) → the
   per-step dispatch, which asks first:
   `if smart_replay is not None and smart_replay.handles(step)` →
   `SmartReplay.run_step` (`engine/smart_replay.py`).

5. **The gate: does smart replay apply at all?** `SmartReplay.handles` returns
   true only when all three hold — the feature switch is on, the step has a
   descriptor, and the adapter claims the step kind. Otherwise the step runs
   through the same code it always ran through.

6. **The target is looked for, with a bounded wait.** `SmartReplay._wait_for_candidates`
   polls `adapter.candidates(step)` while `_condition_met` is false, sleeping
   `poll_interval_seconds` and stopping at `timeout_seconds`. It checks
   `cancel_check()` before every poll, so Stop and the kill switch work while
   waiting. A cancelled step is `SKIPPED`, never half-done.

7. **The decision is made in two pure steps.** `resolve(...)`
   (`engine/resolve/resolver.py`) calls `score_candidates` (`engine/resolve/scoring.py`)
   and then `decide` (`engine/resolve/policy.py`). Scoring is integer weights
   (`EXACT_WEIGHTS`, `CONTAINS_WEIGHTS`, `AGREEMENT_BONUS`) with
   `normalise_text` folding case, accents and whitespace. Only the best clue per
   group counts, so five clues copied from one node cannot add up. Position
   (`ORDINAL`, `POSITION`) may *order* candidates but never decides a target.

8. **Act, ask, or stop.** `decide` returns exactly one of three:
   - `RESOLVED` only for a read-only or reversible step with a single clear
     winner: identity score ≥ `MIN_CONFIDENCE` (30) and a lead of at least
     `CLEAR_GAP` (20) over the runner-up;
   - `ASK_USER` when it is ambiguous, low-confidence, or the step is
     `DESTRUCTIVE` (deleting or changing data is never the engine's own choice);
   - `STOP` when nothing usable was found, or when the run is unattended and a
     question would have been needed. An unattended run never asks.
   `SmartReplay._handle_non_automatic` turns a non-automatic decision into
   either a question (`ask_user`) or a `FAILED` step whose message says
   "Nothing was clicked."

9. **The action happens.** `SmartReplay._act` → `UiaTargetAdapter.perform`
   (`integrations/uia_adapter.py`). `_attempts_for` tries in order: the UI
   Automation pattern, then the keyboard, then a click at the element centre
   (`_click_at_centre`, after `_focus_and_verify` and a foreground-window check
   with `foreground_handle`/`window_handle`, and a DPI conversion in
   `physical_point`). A person who approved an ambiguous candidate is recorded
   in the message: "You confirmed this step."

10. **The postcondition is checked.** `SmartReplay._act` calls
    `adapter.observe(step)` and `_expected_met(...)`: `TEXT_APPEARS`,
    `TEXT_DISAPPEARS`, `VALUE_EQUALS`, `ELEMENT_ENABLED`, or the title/URL kinds
    containing the expected value. A mismatch turns the step into `FAILED` with
    `_mismatch_message` — plain words, what it used, what it wanted, what the
    screen shows.

11. **The run report gets the account.** `_evidence(...)` builds a
    `StepResolution` (decision, strategy = which clue kinds matched, confidence,
    up to four alternatives, up to four `differed` lines, and the resolver\'s own
    explanation). It travels on `StepResult.resolution` and is copied into the
    workflow run\'s results (`engine/workflow.py`). **Not finished:**
    `StepResolution` is not yet written to the history database or drawn on the
    Activity page — today the run report shows the step *message* only.

## What is on by default

Nothing. And "nothing" has three layers, which is the honest answer for a demo:

- the switch is off: `SmartReplayOptions(enabled=False)`, and
  `options_from_environment` reads `ONCE_SMART_REPLAY` and enables it only for
  the exact string `"1"`;
- even with the switch on, the app does not pass a `SmartReplay` into the
  executor: `controller/service.py` builds `ReplayExecutor()` and
  `ReplayExecutor(DESKTOP_EXECUTION_POLICY)` without `smart_replay=`, so
  `WorkflowRunner` sees `None` and every step takes the old path;
- there is no UI toggle anywhere (`ui/` never mentions smart replay).

So a user who simply runs Once gets the deterministic behaviour they had before
the feature existed.

## How to turn it on

Smart replay is currently exercised by code and by tests, not by the app:

```powershell
$env:ONCE_SMART_REPLAY = "1"      # off unless this is exactly "1"
```

and then, in code, build the pair and hand it to the executor:

```python
from engine.smart_replay import SmartReplay, options_from_environment
from integrations.uia_adapter import PywinautoSurface, UiaTargetAdapter

options = options_from_environment()          # enabled=True, unattended=False
target_json = '{"application": "notepad"}'     # the workflow's desktop target
surface = PywinautoSurface(target_json)        # pywinauto imported lazily
adapter = UiaTargetAdapter(surface, target_json)
smart = SmartReplay(adapter, options)          # pass as smart_replay=...
```

The working example of that wiring lives in `tests/test_smart_replay.py` and in
the scenario lab, `tests/scenarios/lab.py` (its fake surface never touches a
real desktop). Automated tests never call a live application; a real desktop run
needs `ONCE_REAL_DESKTOP=1` and is skipped everywhere else.

## What a wrong click would have to get past

Five independent walls, in the order they are hit:

1. **It must look like the recording, on purpose.** The descriptor carries
   independent clues (automation id, role, name, label text, container text,
   process/domain), so a lookalike button in a different dialog fails the
   app-scope clue and is disqualified. A coordinate alone can never select it.
2. **It must score decisively.** At least 30 identity points, and 20 points
   clear of the runner-up, or the resolver refuses to act. Two identical "Delete"
   buttons score the same, so the gap is zero — that becomes a question, not a
   click.
3. **It must not be destructive.** A `DESTRUCTIVE` step is never chosen
   automatically, even with a perfect score: it asks a person, or stops.
4. **It must be watched or it must stop.** An unattended run cannot ask, so any
   ambiguity becomes `STOP`, described in plain words, with nothing clicked.
5. **Its result must be visible.** After acting, the expected outcome is read
   back through `adapter.observe` and compared; if the screen does not show what
   the step promised, the step is `FAILED` and the run reports it.

A wrong click therefore needs a descriptor that matches the *wrong* element
better than the right one, a decisive score, a non-destructive step class, and an
observation that either accidentally matches or is not checked. That is the
residual risk to state out loud: title-level and text-level postconditions are
weaker than a semantic check, and weak clues (role, ordinal, position) can never
carry a decision alone but can add to a score built on a real clue.
