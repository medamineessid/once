# Smart replay — design (2026-11-22)

Status: **proposal + first implementation slice.** `engine/resolve/` is
implemented on branch `feat/smart-replay-core` and exercised by the headless
scenario lab in `tests/scenarios/`. Nothing here authorises unrestricted
replay: every mutating step still passes the existing approval gate, allowlist,
boundedness and cancellation checks.

## 1. The problem

Today a recorded step identifies its target by **resource identity captured at
recording time**: window title, process id, automation id, CSS selector
(`engine/workflow.py:298`, `:330`, `:552`). That is exact when the application
is byte-identical and useless when it is not: a search result moves down
because an advert was inserted, a button loses its `id`, a dialog appears late,
a label is translated, a tab strip grows by one. The recorded selector then
either fails (safe but brittle) or matches a *different* element (unsafe).

Smart replay replaces "one exact identifier" with "the intent of the step plus
a bundle of independent clues", and replaces "match or fail" with "score the
candidates, act only when one candidate clearly wins and the action is
reversible".

## 2. What exists today (evidence, not aspiration)

Real, implemented and tested:

| Capability | Where |
| --- | --- |
| Declarative step schema (id, name, kind, message, JSON target, retries, postcondition, timeout) | `engine/workflow.py:92` |
| Strict validation of targets (unknown keys rejected, bounded lengths) | `engine/workflow.py:714` |
| Deterministic runner, bounded retries, cancellation between steps | `engine/workflow.py:823`, `:906` |
| Postcondition mechanism (currently `PATH_EXISTS` only) | `engine/workflow.py:46`, `:1153` |
| Replay allowlist, dry-run, preview | `engine/replay.py:27`, `:93` |
| Desktop approval gate (approval object is the only executor input) | `engine/desktop.py:36` |
| UIA identity resolution, fails closed on ambiguity | `integrations/uia_targeting.py:50`, `integrations/windows_automation.py:12` |
| Desktop click/type/shortcut, UIA pattern first | `integrations/windows_desktop.py:181`, `:761` |
| Mouse-at-centre fallback, only after pattern refusal | `integrations/windows_desktop.py:226`, `:799` |
| Bounded window wait (poll, not fixed sleep) | `integrations/windows_desktop.py:611`, `:659` |
| Chrome DevTools DOM queries, click/type with read-back, page waits | `integrations/chrome_devtools.py:514`, `:570`, `:657` |
| Chrome tab APIs (`/json/list`, `/json/new`) | `integrations/chrome_devtools.py:119`, `:122` |
| Recording with UIA metadata and password redaction | `integrations/recorder.py:190`, `recorder/models.py:38` |
| Fault-stop hotkey (Ctrl+Alt+Q), absent from the shortcut allowlist | `integrations/kill_switch.py:112`, `engine/workflow.py:166` |
| Run-report events with plain-language step messages | `controller/run_events.py:89` |

Fake-only or absent (later slices, §14):

- `FakeAnalysisProvider` and `deterministic_recording_provider` are offline
  stand-ins (`ai/provider.py:57`, `:119`). They map a recording to one
  candidate workflow; they do **not** resolve targets at replay time.
- A recorded point is only observation text in a draft
  (`recorder/drafts.py:_describe`); a coordinate is never a step target today.
- No scored resolver, no confidence gap, no ambiguity policy, no safety class,
  no locale/DPI tolerance, no foreground-window check before a click, no "row
  by text rule + next page", no self-heal.
- `controller/run_events.py:240 FakeRunEventSource` is test-only.
- Real-desktop replay is **NOT VERIFIED** in this session (tests here are
  fake-adapter based).

## 3. Step model: intent, clues, outcome, safety class

```
StepIntent(
  step_id,                  # stable id, unchanged across variants
  intent: str,              # what the user meant, in words, used in reports
  action: ActionKind,       # CLICK | TYPE | SELECT | NAVIGATE | INVOKE
  descriptor: TargetDescriptor,
  value: str | None,        # text to type / row rule to select
  expected: ExpectedOutcome,
  safety: SafetyClass,
  wait: WaitBudget,
)
```

- **Intent first.** Report text comes from `intent`, never from the resolved
  selector: "Open invoice 1042", not "clicked div:nth-child(3)".
- **Coordinates are never the primary clue.** A recorded point is
  `position_hint` only: it may break a tie between candidates that already
  matched on a semantic clue, it may never create a candidate and never decides
  the clear gap on its own.
- **No executable content.** Everything stays declarative and JSON-safe, so the
  existing strict validator keeps applying; unknown keys are rejected, never
  silently repaired.

## 4. Target descriptor: independent clues

```
TargetDescriptor(surface: WEB|DESKTOP, app: AppIdentity,
                 clues: tuple[Clue, ...], position_hint: (x, y) | None)
Clue(kind, value, group)
```

Clue kinds, strongest first, each from an independent source:

1. `AUTOMATION_ID` / `DOM_ID` — implementation identity.
2. `ROLE` — control type / DOM role + tag.
3. `NAME` — accessible name or visible label, normalised (NFKC, casefold,
   collapsed whitespace).
4. `LABEL_TEXT` — a *different* element that labels this one (`<label for>`,
   `aria-labelledby`, the static text beside it).
5. `CONTAINER_TEXT` — nearest meaningful ancestor's text (row, item, group).
6. `DOMAIN` / `PROCESS` — registrable domain, or the executable the run
   launched. A clue from another domain or process is not a candidate at all.
7. `ORDINAL` — position among same-role siblings (tab index, row index).
8. `POSITION` — recorded point, tie-break only.

`group` records the *source* of a clue so scoring counts **independent
agreement**, not currency: five clues read from one node are one piece of
evidence.

## 5. Resolver: scored strategies, clear gap

`engine/resolve/` — pure Python, no OS, Qt, network or filesystem imports:

```
models.py    # SafetyClass, Clue, TargetDescriptor, Candidate,
             # EvaluatedCandidate, Resolution, ResolutionReason
scoring.py   # strategy weights + independence bonus
policy.py    # ambiguity + safety decision
resolver.py  # resolve(descriptor, candidates, context)
```

Each candidate sums only its **best clue per group**, plus an agreement bonus
per additional independent group. Integer weights keep the gap explainable:

| Strategy | Weight |
| --- | --- |
| id match (exact) | 50 |
| name match (exact, normalised) | 35 |
| label text match | 25 |
| name contains / word-boundary | 20 |
| role match | 15 |
| container text match | 15 |
| ordinal match | 10 |
| agreement bonus, per extra independent group | 10 |
| position hint within 50 px (tie-break only) | 5 |
| wrong domain / wrong executable | candidate discarded |

**Clear-gap rule.** Act only when `top.score >= MIN_CONFIDENCE (30)` and
`top.score - second.score >= CLEAR_GAP (20)`. A lone exact name (35) clears the
confidence floor; a lone role (15) or contains-match (20) does not. Otherwise `ASK_USER`
(interactive) or `STOP` (unattended). The resolver never returns "best guess":
it returns `RESOLVED`, `ASK_USER` or `STOP` with the full scored table and a
one-sentence explanation.

## 6. Safety class

- `READ_ONLY` — inspect, focus, expand, scroll.
- `REVERSIBLE` — effect the user can undo or redo, or proven by postcondition.
- `DESTRUCTIVE` — delete, clear, send, pay, overwrite, close-without-save.

Policy: a `DESTRUCTIVE` step is **never auto-picked**, even with a perfect
score and a clear gap; the user always confirms the resolved target. A tie, a
weak winner or a missing candidate on a destructive step is `STOP` when
unattended and `ASK_USER` when a person is present. The safety class comes from
the approved workflow; no provider may reclassify a step at replay time.

## 7. Expected outcome and postconditions

`ExpectedOutcome(kind, value)` is required on every mutating step:
`TEXT_APPEARS`, `TEXT_DISAPPEARS`, `VALUE_EQUALS`, `URL_MATCHES`,
`ELEMENT_ENABLED`, `COUNT_CHANGES`, `WINDOW_TITLE`, `FOCUSED_ELEMENT`.

After the action the engine re-observes and compares. A mismatch is a readable
failure ("Once clicked *Edit* on invoice 1042 but the editor did not open"),
never a silent success. No postcondition, no retry.

## 8. Waits instead of sleeps

Every wait is a bounded poll on an observable condition with an injected clock:
`WaitBudget(condition, timeout_seconds <= MAX_STEP_TIMEOUT_SECONDS,
poll_interval_seconds)`. Fixed `sleep` is allowed only as retry back-off
(`engine/workflow.py:964`), never as "the element will appear". Existing
bounded polls: `integrations/windows_desktop.py:659`,
`integrations/chrome_devtools.py:454`, `:657`.

## 9. List rows, scrolling, next page

Rows are never addressed by index. A `SELECT` step carries a row rule
`RowRule(text, mode=EXACT|CONTAINS|WORD_BOUNDARY, domain)`. Resolution order:
current page → next page (bounded `max_pages`) → scroll (bounded `max_scrolls`)
→ ask. "The third result" is expressly unsupported: the k-th result changes
meaning when an advert is inserted.

## 10. Ambiguity policy

1. Refine with context first: container text, label text, domain, neighbouring
   roles.
2. Auto-pick only when the action is `READ_ONLY` or `REVERSIBLE` **and** one
   candidate clearly wins (clear-gap rule).
3. Otherwise ask, showing every candidate and its evidence.
4. Never auto-pick a `DESTRUCTIVE` step.
5. Unattended runs never ask: stop safely, mark the step `SAFE_FAILURE`, say
   why.
6. Asking is bounded: one question per step, no re-asking loop.

## 11. Interruption, allowlist, foreground check

- The kill switch (`integrations/kill_switch.py:112`) sets a run flag checked
  before every step; resolution happens per step, so a stop lands at the next
  boundary.
- Only allowlisted step kinds replay (`engine/replay.py:48`); the hotkey
  combination is absent from `ALLOWED_SHORTCUTS` (`engine/workflow.py:166`).
- **Foreground check — not implemented.** Before a desktop click the engine must
  confirm the target window is the foreground window of the expected process,
  and abort otherwise. Today only the recorder reads the foreground window
  (`integrations/recorder.py:131`). Slice 3 in §14.

## 12. Locale and DPI tolerance

- Text comparison normalises NFKC, casefolds and strips accents for *matching
  only*, and keeps the original for reporting.
- Localisation is not guessed: if the only remaining clue is translated text,
  ask. Recorded "Edit" and live "Bearbeiten" do not count as a name match; a
  shared automation id does.
- Coordinates are logical, converted through the target window's DPI awareness
  before use (`integrations/windows_desktop.py:226`), and a position hint is
  trusted only after a semantic match, so 150 % scaling cannot turn a tie-break
  into a target choice.

## 13. Run-report explanations

One line per resolution, for the report and the Activity page:

- RESOLVED: "Found *Edit* in the results list (automation id + label, score 95,
  next candidate 45)."
- ASK_USER: "Two elements could be *Delete*. Which one should Once use?"
- STOP: "*Delete* was not found on this page or the next two pages. Nothing was
  clicked."

Internal ids and enum names stay in the data ("details"), never in the
user-facing sentence.

## 14. Self-heal, and slices that need other agents' files

Self-heal (rewriting stored clues from a successful resolution) is opt-in per
step and per run, shows an old → new diff, and is refused for `DESTRUCTIVE`
steps. No silent learning.

Not built here, in dependency order:

1. **Step schema** — `descriptor`, `expected`, `safety`, `wait` on
   `WorkflowStep` (`engine/workflow.py`) plus the JSON validator and a schema
   version bump (`storage/workflows.py`); needs a storage migration review.
2. **Recorder enrichment** — capture label/container text and surrounding
   context (`integrations/recorder.py`, `recorder/models.py`); today a
   recording stores one element, not its context.
3. **Foreground-window guard** before desktop clicks and DPI-aware point
   conversion (`integrations/windows_desktop.py`).
4. **List paging/scroll** for the browser provider
   (`integrations/chrome_devtools.py`), using the existing tab APIs instead of
   refusing when more than one tab is open (`:344`).
5. **Persist resolutions** to run history (`storage/history.py`) so the Activity
   page can explain a resolution after restart.
6. **UI** — ask-user panel, candidate list with evidence, self-heal dialog.

## 15. Scenario lab (Phase 1, headless)

`tests/scenarios/` proves the logic before any OS adapter exists:

- `web_app.py` — real local HTTP server (127.0.0.1, ephemeral port) serving
  variants: adverts above the results, cookie banner, target with no `id`,
  changed label, re-rendered list, target on page 2.
- `qt_window.py` — real offscreen Qt window: tab strip whose "+" moves with the
  tab count, list that reorders, sometimes-missing dialog, delayed control,
  translated label, destructive Delete next to a harmless one.
- `catalog.py` — scenarios recorded on variant A, replayed on B/C/D with an
  expected outcome of `SUCCESS`, `ASKS_USER` or `SAFE_FAILURE`.
- `lab.py` — drives the resolver through a fake adapter
  (`TargetAdapter: candidates(), perform(), observe()`), counts outcomes and
  **WRONG actions** (action on the wrong element, or any action when the
  expectation was ask/stop). Wrong actions must be zero.
