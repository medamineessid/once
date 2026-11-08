# Run outcome contract

Status: implemented (engine/workflow.py, controller/run_events.py,
ui/components/formatting.py). Version: 1.
Owner: lane B (docs/contracts). Consumers: Activity page, Home "recent
activity" list, run event stream (docs/contracts/run_events.md), saved
workflow history, approval panel.

## The problem this contract fixes

A `REPORT` step used to finish as `SUCCEEDED`, so a workflow that only
printed text reported *Succeeded* even though nothing on the machine was
touched. A run must never read as success just because it did not fail.

## Step statuses

Unchanged, all still persisted as their enum value string:

| status | meaning |
|---|---|
| `PENDING` | not started (in-memory only) |
| `RUNNING` | in progress (in-memory only) |
| `SUCCEEDED` | the step *did* its work and changed or drove something real |
| `VERIFIED` | a read-only inspection observed the state it was asked for |
| `OBSERVED` | **new.** The step recorded an observation only; nothing was performed |
| `FAILED` | the step tried and failed, with a reason |
| `INCONCLUSIVE` | the step ran but could not decide (e.g. no provider configured) |
| `SKIPPED` | the step did not run (earlier failure, or cancellation) |

`OBSERVED` is produced only by `StepKind.REPORT`. A `REPORT` step never
executes an action, so it cannot claim `SUCCEEDED` and must not claim
`FAILED` either — it is a first-class observation, not an error.

`OBSERVED` continues a run: it is treated like success for the purpose of
moving to the next step, and like a non-failure for the purpose of a
retry's success check. Cancellation and failure propagation are
unchanged.

## Run statuses

| status | rule |
|---|---|
| `SUCCEEDED` | the run finished, no step failed, at least one non-`REPORT` step actually succeeded (`SUCCEEDED` or `VERIFIED`), and zero steps were `OBSERVED` |
| `PARTIALLY_PERFORMED` | **new.** The run finished, no step failed, at least one non-`REPORT` step actually succeeded (`SUCCEEDED` or `VERIFIED`), and at least one step ended `OBSERVED` |
| `OBSERVATION_ONLY` | **new.** The run finished, no step failed, and no non-`REPORT` step performed or verified anything — every step was an observation (an all-`REPORT` workflow, or a workflow with no steps at all) |
| `FAILED` | any step ended `FAILED` (or `INCONCLUSIVE`) |
| `CANCELLED` | the run stopped because of cancellation |
| `PENDING` / `RUNNING` | in-memory only |

Decision order at the end of a run:

1. any `FAILED` result → `FAILED`;
2. otherwise, if no non-`REPORT` step ended `SUCCEEDED`/`VERIFIED` →
   `OBSERVATION_ONLY`;
3. otherwise, if any step ended `OBSERVED` → `PARTIALLY_PERFORMED`;
4. otherwise → `SUCCEEDED`.

A `REPORT` step with a postcondition still reports `OBSERVED`: the
postcondition *verifies* the observation, it does not turn a report into
an action. Such a run is `OBSERVATION_ONLY`.

Failures keep priority over observations: a workflow that reports and
then fails is `FAILED`, never `OBSERVATION_ONLY` or `PARTIALLY_PERFORMED`.

## User-facing wording

| run status | label | chip |
|---|---|---|
| `SUCCEEDED` | Succeeded | ok |
| `PARTIALLY_PERFORMED` | Partly performed | warn |
| `OBSERVATION_ONLY` | Observation only — nothing was performed | neutral |
| `FAILED` | Failed | fail |
| `CANCELLED` | Cancelled | neutral |

The label is defined once, in `ui/components/formatting.status_display`,
and every page (Activity details, Home recent activity) renders it from
there. No page may invent its own text for a status.

## Compatibility

- Saved workflows are untouched: `OBSERVED` and `OBSERVATION_ONLY` are
  step/run *outcomes*, not step kinds or workflow fields. No schema
  version change, no migration, no re-validation of existing files.
- History rows keep storing `status.value` as text (no CHECK
  constraint). Rows written before this contract still load and still
  mean exactly what they meant: an old `SUCCEEDED` row from an all-`REPORT`
  run is *not* re-labelled retroactively — the contract applies from the
  moment the engine produces the outcome. New runs write
  `OBSERVATION_ONLY`.
- `storage.history` reads statuses with `WorkflowStatus(row["status"])`;
  `OBSERVATION_ONLY` and `OBSERVED` are valid members, so no code change
  is needed to read new rows and none is needed to read old ones.

## Run events

`STEP_SUCCEEDED` now carries `OBSERVED` as well as `SUCCEEDED`/`VERIFIED`:
it is still a "the run continues" event, not a failure. `RUN_FINISHED`
carries the real final status, including `OBSERVATION_ONLY`. See
docs/contracts/run_events.md.

## Honesty rules

1. A run status is derived from the real step results only.
2. Nothing is upgraded: an observation never becomes a success, and a
   failure never becomes an observation.
3. `OBSERVATION_ONLY` is not an error state and must not be styled or
   worded as one; it says plainly that the run looked and reported, and
   that nothing on the machine was performed.
4. The engine never claims a capability the step kinds cannot perform.

## Tests

`tests/test_b1_run_outcomes.py`: `REPORT`-only run is `OBSERVATION_ONLY`
with `OBSERVED` steps; empty workflow is `OBSERVATION_ONLY`; a read-only
inspection is still `SUCCEEDED`; report-then-fail is `FAILED`; a report
step does not hide a later failure; history persists and reloads both new
outcomes; old `SUCCEEDED` rows still load; run events classify `OBSERVED`
as a success-continuation; `status_display` labels `OBSERVATION_ONLY`.
