# Smart replay — design (2026-11-22)

Status: current
Last verified: 2026-11-26 · `main f2e6ca3`
Owner: lane A (replay core)


Status: **slices 1–3 implemented on `feat/smart-replay-core`.** The resolver
(`engine/resolve/`), the flag-gated integration (`engine/smart_replay.py`), the
schema-4 step fields (`engine/workflow.py`, `storage/workflows.py`) and the UI
Automation capture/replay adapter (`integrations/uia_adapter.py`) are written
and tested, and the headless scenario lab in `tests/scenarios/` runs both through
the resolver and through the integration. The Chrome adapter, self-heal and the
ask-the-user panel are **not** built (§14). Nothing here authorises unrestricted
replay: every mutating step still passes the existing approval gate, allowlist,
boundedness and cancellation checks, and the layer is off unless
`ONCE_SMART_REPLAY=1`.

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
| Schema 4: descriptor (independent clues), expected outcome, safety class, bounded wait | `engine/workflow.py:149`, `storage/workflows.py` |
| Scored resolver with a clear-gap rule and three-way decision (act / ask / stop) | `engine/resolve/resolver.py`, `engine/resolve/policy.py` |
| Flag-gated integration: per-step resolution evidence, bounded waits, no unattended ask | `engine/smart_replay.py` |
| Desktop capture: clues from recorded metadata; password and position-only refused | `integrations/uia_adapter.py:descriptor_from_element` |
| Desktop replay: re-resolve per attempt, pattern → keyboard → mouse centre | `integrations/uia_adapter.py:UiaTargetAdapter` |
| Foreground check before keys, DPI-converted click point | `integrations/uia_adapter.py:_focus_and_verify`, `PywinautoSurface.physical_point` |

Fake-only or absent (later slices, §14):

- `FakeAnalysisProvider` and `deterministic_recording_provider` are offline
  stand-ins (`ai/provider.py:57`, `:119`). They map a recording to one
  candidate workflow; they do **not** resolve targets at replay time.
- A recorded point is only observation text in a draft
  (`recorder/drafts.py:_describe`); a coordinate is never a step target today.
- No Chrome adapter: a `descriptor` on a browser step is still resolved by the
  engine's scoring layer, but no CDP-backed adapter supplies candidates or
  performs the action, so the lab's web variants use a fake adapter.
- No self-heal, no "row by text rule + next page", no ask-the-user panel: an
  `ASK_USER` decision is reported as a stop until the panel exists.
- Desktop postconditions are observed at window-title level (or the last value
  read back), not by reading arbitrary element text.
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
- **Foreground check — implemented in the adapter.** Before any key is sent,
  `UiaTargetAdapter._focus_and_verify` focuses the target and compares
  `GetForegroundWindow()` with the window's own handle; if they differ the
  attempt is refused and no key is sent. The mouse-centre fallback may still
  run, because it names an exact point instead of relying on focus. Verified
  against a fake surface only; the real Win32 path is **NOT VERIFIED**.

## 12. Locale and DPI tolerance

- Text comparison normalises NFKC, casefolds and strips accents for *matching
  only*, and keeps the original for reporting.
- Localisation is not guessed: recorded "Edit" and live "Bearbeiten" are not a
  name match, while a shared automation id still is; if the translated text is
  the only remaining evidence, ask.
- UI Automation rectangles are already physical pixels; a point that came from
  a screenshot or a scaled window is not. `PywinautoSurface.physical_point`
  scales by `GetDpiForWindow`, and the adapter asks for the converted point
  right before it clicks, so 150 % scaling cannot move a click off the element.
- A position hint is trusted only after a semantic match, so scaling can never
  turn a tie-break into a target choice — the resolver gives position weight
  only to a candidate that already matched an identity clue.

## 13. Run-report explanations

One line per resolution, for the report and the Activity page, e.g. "Found
Edit for \"Open invoice 1042\" (score 145, next candidate 0)." RESOLVED, ASK_USER
and STOP each get their own sentence; internal ids and enum names stay in the
data ("details"), never in the user-facing sentence.

## 14. Self-heal, and slices that need other agents' files

Self-heal (rewriting stored clues after a successful resolution) is opt-in per
step and per run, shows an old → new diff, and is refused for `DESTRUCTIVE`
steps. No silent learning.

Slices, in dependency order — the first three are merged-ready on this branch:

1. **Step schema** — done: `descriptor`, `expected`, `safety`, `wait` on
   `WorkflowStep`, strict v4 read/write, v1–v3 files still load
   (`engine/workflow.py`, `storage/workflows.py`).
2. **Recorder context** — partly done: `descriptor_from_element` and
   `descriptor_from_event` capture clues from what the recorder already stores;
   label/container text and the surrounding tree are still missing, and events
   do not persist a descriptor yet (`integrations/uia_adapter.py`).
3. **Foreground guard and DPI points** — done in the new adapter
   (`integrations/uia_adapter.py`); the older `PywinautoDesktopActions` path is
   unchanged.
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

Since slice 2 the same matrix also runs through the real integration
(`lab.run_scenario_through_smart_replay`), so a passing lab result means the
flag-gated layer makes the same decision the design specifies, not just that the
resolver does. Last measured run (2026-11-22, both paths):

```
web  pass rate: 100% (6/6 variants), prompts: 1, WRONG actions: 0
Qt   pass rate: 100% (13/13 variants), prompts: 5, WRONG actions: 0
```

The lab is headless and fake-adapter based. It is not a claim about a real
Windows desktop, a real browser, or a real application: those remain **NOT
VERIFIED** until the Chrome adapter and the opt-in real-desktop test
(`ONCE_REAL_DESKTOP=1`) are actually run on a machine with a desktop.
