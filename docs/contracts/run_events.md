# Run events contract

Status: implemented (controller/run_events.py, ui/workers.py). Version: 1.
Owner: lane B (docs/contracts). Consumers: shell pages, editor live node
states (task B7), Activity evidence (task B5), approval panel (task B2).

## What the engine really produces

`WorkflowRunner.run` (engine/workflow.py) executes steps strictly in
workflow order. For every step that actually ran it appends one final
`StepResult` to `WorkflowRun.results` and calls `progress_callback` with
that same result. Remaining steps receive a `StepResult(status=SKIPPED)`
after a failure or a cancellation, and the run records two canonical skip
messages ("Skipped because an earlier step failed." / "Skipped because the
workflow was cancelled."). A step retried through `max_attempts` produces
exactly one final `StepResult`; its message carries "(attempt N)" and its
evidence contains the recorded earlier attempts. Intermediate attempts are
never reported separately.

## Events

`controller.run_events.RunEventStream` turns one engine run into the
following immutable, ordered events (`RunEvent`, dataclass, frozen):

| kind | step_id | status | message | evidence |
|---|---|---|---|---|
| RUN_STARTED | None | None | "The run started." | empty |
| STEP_STARTED | step id | None | empty | empty |
| STEP_SUCCEEDED | step id | real StepStatus value ("SUCCEEDED"/"VERIFIED") | real result message | real result evidence |
| STEP_FAILED | step id | real value ("FAILED"/"INCONCLUSIVE") | real result message | real result evidence |
| STEP_SKIPPED | step id | "SKIPPED" | real skip message (failure phrase) | real evidence |
| STEP_CANCELLED | step id | "SKIPPED" | real skip message (cancelled phrase) | real evidence |
| RUN_FINISHED | None | real final WorkflowStatus, or "FAILED" for a failed run call | plain-language finish message | engine error text when the call itself failed |

Common fields of every event: `run_id` (the id of this event stream),
`sequence` (dense, unique, monotonic per stream), `workflow_id`,
`created_at` (UTC aware), `engine_run_id` (only set on RUN_FINISHED from a
real `WorkflowRun`; it matches the value persisted by the history store).

## Honesty rules

1. Events are created from real engine data only. Nothing is simulated,
   interpolated, or invented; `STEP_STARTED` is derived, at completion
   time, from the same real result that produced the final event (a result
   proves the step ran; skipped steps get no started event).
2. Skipped/cancelled classification keys off the engine's exact skip
   phrases (engineering constant `_CANCELLED_SKIP_PHRASE`).
3. A closed stream (run finished, or the run call failed) never produces
   further events; every observation made after finishing returns an
   empty tuple. Any unexpected step status is recorded as a failure event
   and logged; nothing is silently dropped.
4. Evidence strings are engine data (file paths, recorded attempts). The
   local UI may display them; nothing in the pipeline re-executes them
   (O5).

## Thread safety

- `RunEventStream` methods take a lock; events are immutable, so they can
  cross threads freely.
- `ui.workers.WorkflowWorker` owns the stream during its own `run()` (on
  the worker thread) and emits each event through the additive Qt signal
  `run_event(object)` from that thread. Receivers must connect with
  `Qt.ConnectionType.QueuedConnection` (same rule as the existing
  `progress`/`finished` signals on the pages).
- Delivery order per run: RUN_STARTED, then (STEP_STARTED, STEP_*) pairs
  in engine order (a retried step appears once), then skip reconciliations
  in `WorkflowRun.results` order, then exactly one RUN_FINISHED. The
  worker emits `finished` after RUN_FINISHED, never before.

## Test doubles

`FakeRunEventSource` (same module) hands out scripted event batches for UI
tests and previews only; the product never constructs it. Tests
demonstrating the contract with the real engine and fake providers live in
`tests/test_b1_run_events.py` (order for success, failure, cancellation,
retry, post-finish silence, and worker delivery).
