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
  `position_hint` only: it may never create a candidate, it adds a point only
  after an identity clue already matched, and it never contributes to the clear
  gap that permits acting.
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
3. `NAME` — accessible name or visible label, normalised (NFKC, casefold, spaces).
4. `LABEL_TEXT` — a *different* element labelling this one (`<label for>`, the
   static text beside it).
5. `CONTAINER_TEXT` — nearest meaningful ancestor's text (row, item, group).
6. `DOMAIN` / `PROCESS` — the site or the executable the run launched; another
   domain or process is not a candidate at all.
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
| different container text (another row/dialog) | candidate discarded |

**Clear-gap rule.** Act only when `top.score >= MIN_CONFIDENCE (30)` and
`top.score - second.score >= CLEAR_GAP (20)`. A lone exact name (35) clears the
confidence floor; a lone role (15) or contains-match (20) does not.

The gap is measured on **identity evidence only** (`identity_score`, i.e. id,
name, label, container, role). Ordinal and position still shape the displayed
score and are shown as evidence, but they never create the gap: two identical
rows that differ only by position always ask. Otherwise `ASK_USER`
(interactive) or `STOP` (unattended). The resolver never returns "best guess":
it returns `RESOLVED`, `ASK_USER` or `STOP` with the full scored table and a
one-sentence explanation.

## 6. Safety class

- `READ_ONLY` — inspect, focus, expand, scroll.
- `REVERSIBLE` — effect the user can undo or redo, or proven by postcondition.
- `DESTRUCTIVE` — delete, clear, send, pay, overwrite, close-without-save.

Policy: a `DESTRUCTIVE` step is **never auto-picked**, even with a perfect score
and a clear gap; a person always confirms the target. A tie, a weak winner or a
missing candidate on a destructive step is `STOP` when unattended, `ASK_USER`
when someone is present. The class comes from the approved workflow; no
provider may reclassify a step at replay time.

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
poll_interval_seconds)`. A fixed `sleep` is only ever retry back-off
(`engine/workflow.py:964`), never "the element will appear". Existing bounded
polls: `integrations/windows_desktop.py:659`, `chrome_devtools.py:454`, `:657`.

## 9. List rows, scrolling, next page

Rows are never addressed by index. A `SELECT` step carries a row rule
`RowRule(text, mode=EXACT|CONTAINS|WORD_BOUNDARY, domain)`; resolution order is
current page → next page (bounded `max_pages`) → scroll (bounded `max_scrolls`)
→ ask. "The third result" is unsupported: the k-th result changes meaning when
an advert is inserted.

## 10. Ambiguity policy

1. Refine with context first: container text, label text, domain, neighbouring roles.
2. Auto-pick only when the action is `READ_ONLY` or `REVERSIBLE` **and** one
   candidate clearly wins (clear-gap rule).
3. Otherwise ask, showing every candidate and its evidence.
4. Never auto-pick a `DESTRUCTIVE` step.
5. Unattended runs never ask: stop safely, mark the step `SAFE_FAILURE`, say why.
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
- Localisation is not guessed: recorded "Edit" and live "Bearbeiten" are not a
  name match, while a shared automation id still is; if the translated text is
  the only remaining evidence, ask.
- Coordinates are logical, converted through the window's DPI awareness
  (`integrations/windows_desktop.py:226`), and a position hint is trusted only
  after a semantic match, so 150 % scaling cannot turn a tie-break into a
  target choice.

## 13. Run-report explanations

One line per resolution, for the report and the Activity page, e.g. "Found
Edit for \"Open invoice 1042\" (score 145, next candidate 0)." RESOLVED, ASK_USER
and STOP each get their own sentence; internal ids and enum names stay in the
data ("details"), never in the user-facing sentence.

## 14. Self-heal, and slices that need other agents' files

Self-heal (rewriting stored clues after a successful resolution) is opt-in per
step and per run, shows an old → new diff, and is refused for `DESTRUCTIVE`
steps. No silent learning.

Not built here, in dependency order:

1. **Step schema**: `descriptor`, `expected`, `safety`, `wait` on `WorkflowStep`
   plus the JSON validator and a version bump (`storage/workflows.py`).
2. **Recorder context**: label/container text and the surrounding tree
   (`integrations/recorder.py`, `recorder/models.py`).
3. **Foreground guard** before desktop clicks, DPI-aware point conversion
   (`integrations/windows_desktop.py`).
4. **List paging/scroll** in the browser provider
   (`integrations/chrome_devtools.py`), using the tab APIs instead of refusing
   when more than one tab is open (`:344`).
5. **Persist resolutions** (`storage/history.py`) for the Activity page.
6. **UI**: ask-user panel, candidate list with evidence, self-heal dialog.

## 15. Scenario lab (Phase 1, headless)

`tests/scenarios/` proves the logic before any OS adapter exists:

- `web_app.py` — real local HTTP server (127.0.0.1, ephemeral port) with
  variants: adverts above the results, cookie banner, no `id`, changed label,
  re-rendered list, target on page 2.
- `qt_window.py` — real offscreen Qt window: a "+" that moves with the tab
  count, a list that reorders, a sometimes-missing dialog, a delayed control, a
  translated label, a destructive Delete beside a harmless one.
- `catalog.py` — steps recorded on variant A, replayed on B/C/D with an
  expected `SUCCESS`, `ASKS_USER` or `SAFE_FAILURE`.
- `lab.py` — drives the resolver through a small adapter (`snapshot`,
  `perform`, `observe`, `truth_id`), counts outcomes and **WRONG actions** (an
  action on the wrong element, or any action when the expectation was
  ask/stop). Wrong actions must be zero.
