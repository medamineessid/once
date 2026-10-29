# Visual workflow editor — design document (P1)

Date: 2026-10-31 (session date 2026-10-29/30). Branch: slice/p1-editor-discovery.
Status: evidence-based design, no code yet. Queue owner: this file governs P3–P6.

The session prompt is the governing spec: `docs/specs/visual_workflow_editor.md` and
`docs/specs/reference/workflow_editor.png` do NOT exist (docs/specs/reference/ is an
empty folder; verified with `find docs/specs -type f` → no output). Recorded as
AD-008 in docs/AUTONOMOUS_DECISIONS.md. Everything below is derived from this
prompt's DESIGN LANGUAGE section, the prompt's acceptance criteria, and the code.

## 1. Evidence (prompt items a–f, with file:line)

### (a) The workflow model

- Definition: `Workflow(workflow_id, name, steps: tuple[WorkflowStep, ...])` —
  engine/workflow.py:84-90. `WorkflowStep(step_id, name, kind, message, target=None,
  max_attempts=1, postcondition=None, timeout_seconds=30.0)` — engine/workflow.py:70-81.
- **Order is the tuple order. There is no next-step field, no condition object, and no
  branching wire anywhere in the model or the runner.** `WorkflowRunner.run` iterates
  `enumerate(workflow.steps)` sequentially (engine/workflow.py:832-871); when a step
  fails or the run is cancelled, all remaining steps are appended as SKIPPED and the
  run stops (engine/workflow.py:833-869).
- Step statuses: PENDING, RUNNING, SUCCEEDED, FAILED, SKIPPED, VERIFIED, INCONCLUSIVE
  (engine/workflow.py:48-57). Run statuses: PENDING, RUNNING, SUCCEEDED, FAILED,
  CANCELLED (engine/workflow.py:60-67). Successful outcomes are SUCCEEDED and VERIFIED
  (engine/workflow.py:856, 908).
- Postconditions: the only kind is `PATH_EXISTS` (engine/workflow.py:42-45); a
  postcondition is refused on any provider-backed kind (engine/workflow.py:736-763,
  see the harmless duplicated raise at 759-763 left alone per working agreement rule 9).
- Validators checked before any save or run (`WorkflowRunner.validate`,
  engine/workflow.py:696-801): non-empty workflow_id/name; ≤ MAX_WORKFLOW_STEPS = 100
  steps (engine/workflow.py:15); unique non-empty step ids; name/message ≤ 500 chars
  (MAX_TEXT_LENGTH, engine/workflow.py:16); max_attempts 1–3; timeout_seconds numeric
  in [0.5, 60] (engine/workflow.py:121-124); per-kind target validation described in
  (b); postcondition rules above.
- Results stored per step: `StepResult(step_id, status, message, evidence: tuple[str,...])`
  (engine/workflow.py:93-100), aggregated in `WorkflowRun` (engine/workflow.py:103-112);
  persisted by `ExecutionHistory.record` into `workflow_runs` and
  `workflow_step_results` with an evidence JSON column (storage/database.py:16-31).
- Duplicate unreachable raise at engine/workflow.py:759-763 — documented, untouched.

### (b) Step kinds → plain label, category, inspector fields, mutating?

Mutating membership is exactly `MUTATING_DESKTOP_KINDS` = LAUNCH_APPLICATION,
CLICK_UI_ELEMENT, TYPE_TEXT, PRESS_SHORTCUT, LAUNCH_BROWSER, NAVIGATE_BROWSER,
INTERACT_PAGE_ELEMENT (engine/replay.py:48-58); browser read-only kinds are
`BROWSER_READ_KINDS` = INSPECT_PAGE, FIND_PAGE_ELEMENT, WAIT_PAGE
(engine/replay.py:61-63). The run-time allowlist `DESKTOP_INTERACTION_POLICY.allowed_kinds`
= read-only kinds ∪ mutating ∪ browser-read (engine/replay.py:67-80); the approval gate
approves exactly that policy (engine/desktop.py:34-40). Read-only-only policy:
engine/replay.py:30-39.

Inspector fields are taken **only** from the validators' allowed keys (never invented):

| StepKind | Plain label (node subtitle) | Category → tint | Mutating? | Inspector fields (from validator) |
|---|---|---|---|---|
| REPORT | "Note a message" | progress → pale green | no | name, message |
| FAIL | "Stop with an error" | stop → pale red (AD-014) | no | name, message |
| INSPECT_PATH | "Look at a file" | verification → pale green | no | name, message, target (absolute path string), postcondition (PATH_EXISTS) |
| VERIFY_PATH_EXISTS | "Check a file exists" | verification → pale green | no | name, message, target (absolute path string), postcondition |
| INSPECT_WINDOW | "Read a window" | verification → pale green | no | name, message, target JSON `{title OR process_id OR class_name OR automation_id}` (any 1–4) |
| INSPECT_UI_ELEMENT | "Read a control" | verification → pale green | no | target JSON `{window: window-identity, element: {automation_id OR class_name, control_type?}}` |
| LAUNCH_APPLICATION | "Open an application" | action → peach | yes | target JSON `{application("notepad") XOR executable(abs .exe path), arguments?: str[≤16]×200ch}` |
| WAIT_WINDOW | "Wait for a window" | waiting → pale green | no | target JSON window identity, timeout_seconds |
| CLICK_UI_ELEMENT | "Click a control" | action → peach | yes | target JSON `{window, element, interaction: invoke OR toggle OR select}` |
| TYPE_TEXT | "Type text" | action → peach | yes | target JSON `{window, element, text}` |
| PRESS_SHORTCUT | "Press keys" | action → peach | yes | target JSON `{window, keys}` keys ∈ ALLOWED_SHORTCUTS (engine/workflow.py:129-140) |
| VERIFY_FILE_TEXT | "Check file text" | verification → pale green | no | target JSON `{path (abs, ≤260), contains}` |
| LAUNCH_BROWSER | "Open Chrome (isolated)" | action → peach | yes | target JSON `{application("chrome") XOR executable(Chrome .exe), headed?}` |
| NAVIGATE_BROWSER | "Open a web page" | action → peach | yes | target JSON `{browser:{cdp_port}, url}` url http(s), host required |
| INSPECT_PAGE | "Read a page" | verification → pale green | no | target JSON `{browser, include_text?}` |
| FIND_PAGE_ELEMENT | "Find an element on a page" | verification → pale green | no | target JSON `{browser, selector}` selector ≤256ch, no js/data/file scheme |
| INTERACT_PAGE_ELEMENT | "Click or type on a page" | action → peach | yes | target JSON `{browser, selector, interaction: click OR type, text?}` |
| WAIT_PAGE | "Wait for a page" | waiting → pale green | no | target JSON `{browser, conditions: {title OR url OR text}, timeout_seconds?}`; selector conditions refused here |

Validator functions for each row: window identity engine/workflow.py:242-271; UI
element 274-324; launch 346-404; browser port 407-426; launch-browser 429-474; URL
481-511; navigate 514-522; inspect page 525-534; selector 537-548; find element
551-559; interact 562-582; wait page 585-632; click 635-643; type 646-653; shortcut
656-669; verify-file-text 672-689.

Common fields for every kind: `name` (≤500), `message` (≤500), `max_attempts`
(1–3), `timeout_seconds` (0.5–60, only shown as an editor control for the kinds
whose runtime uses it: WAIT_WINDOW and WAIT_PAGE — engine/workflow.py:1019, 1042). All
step kinds are saveable; only the run-time policy restricts which are executable
(engine/replay.py:99-112), so the editor must ALSO warn when a saved kind would not be
runnable (whole-workflow validation panel, P4).

The `cdp_port` of browser steps is bound by the engine to a browser the workflow
itself launched (engine/workflow.py:216-226, 407-426); the editor deep-links none of
it — the port is filled by the user from a LAUNCH_BROWSER step or left for review.

### (c) Persistence format and the migration mechanism

- Workflow files: JSON, `schema_version` 3 (storage/workflows.py:19-20), root keys
  exactly `{schema_version, workflow_id, name, steps}` (storage/workflows.py:21, 60-61);
  v3 step keys exactly `{step_id, name, kind, message, target, max_attempts,
  postcondition, timeout_seconds}` (storage/workflows.py:25); versions 1–2 remain
  loadable with their older key sets (storage/workflows.py:73-77). Saved UTF-8 JSON
  (storage/workflows.py:122-130), loaded with full re-validation (storage/workflows.py:133-141).
- Database "migration mechanism": `storage/database.py connect()` creates every table
  with `CREATE TABLE IF NOT EXISTS` and adds columns via `PRAGMA table_info` +
  `ALTER TABLE ... ADD COLUMN` (storage/database.py:9-132). The editor layout record
  uses the same mechanism: a NEW table
  `workflow_layouts (workflow_id TEXT PRIMARY KEY, layout TEXT NOT NULL,
  updated_at TEXT NOT NULL)` added to `connect()` (P4).
- **Layout-record schema** (JSON in `layout`):
  `{"schema_version": 1, "node_positions": {"<step_id>": {"x": float, "y": float}},
  "notes": {"<step_id>": {"text": str}}, "updated_at": "<ISO-8601 UTC>"}`.
  - Keyed by workflow id (row) and step id (dict keys). Never executed; never part of
    the workflow JSON (which forbids unknown keys — storage/workflows.py:61, 77).
  - Missing entries: tolerated; nodes without a saved position are auto-placed by the
    pure layout algorithm.
  - Orphaned entries (positions/notes for step ids no longer in the workflow): dropped
    on the next save of the record.
  - Corrupt record (bad JSON, wrong schema_version, unparseable values): the run
    ignores it, uses auto-layout for everything, and shows a one-line banner; the
    corrupt row is left for a repair to decide (prompt: "Corruption falls back to
    auto-layout with a banner").
- Note text is bounded to 500 chars (same as message; enforced by the controller op).

### (d) Recording → analysis → draft pipeline, and where review flags may come from

- Chain: `RecordingService.start/stop` (controller/recording.py:37-65) persists a
  `Recording{recording_id, started_at_ns, events: tuple[RecordedEvent,...]}`
  (recorder/models.py:45-51) through `RecordingStore` (recorder/storage.py).
  `RecordedEvent` carries sequence, timestamp_ns, kind ∈ {MOUSE_CLICK, KEY_PRESS,
  TEXT_INPUT, WINDOW_FOCUS} (recorder/models.py:9-15), window_title, `UIElementInfo`
  (automation_id/control_type/name/class_name/is_password, recorder/models.py:18-27),
  x/y/key/text, screenshot_name. Redaction happens before save
  (controller/recording.py:48-60, recorder/redaction.py).
- Analysis input: `AnalysisRequest{draft, conversation, keyframe_paths}`
  (ai/models.py:11-17) built from `RawDraft{recording_id, actions}` with
  `RawDraftAction{sequence, description, source_event}` (recorder/drafts.py:10-25,
  27-37). The deterministic provider answers one question then one draft
  (ai/provider.py:46-67); the interview is bounded to 5 turns (ai/provider.py:13,
  ai/interview.py:47). Output: `ProviderQuestion{text}` or `ProviderDraft{goal,
  workflow}` (ai/models.py:20-33).
- **ProviderDraft exposes NO uncertainty fields.** The only legitimate review flags are:
  1. raw events whose kinds cannot become a validated step on their own
     (MOUSE_CLICK carries no target control — recorder/drafts.py:40-46; KEY_PRESS
     carries no window — every desktop step requires a window identity,
     engine/workflow.py:242-271);
  2. steps that fail `WorkflowRunner.validate` when the draft is loaded (the validator's
     message is shown verbatim as the review reason; engine/workflow.py:696-801);
  3. mutating steps that will require approval (from MUTATING_DESKTOP_KINDS);
  4. interview questions recorded in `conversation` (ambiguity the provider asked about).
  The editor must not invent flags; N in "N items need review" = count of the above.
- The old window's analyze path is the parity reference
  (ui/main_window.py:444 `_analyze_recording`).
- **Defect found during P1** (needs fixing in P6 before any editor wiring):
  `ui/pages/review.py:117-125 load_proposal` reads `proposal.steps`, but the
  `ProviderDraft` dataclass has fields `{goal, workflow}` only (ai/models.py:27-33) —
  an AttributeError if ever called with a real draft. Also `ReviewPage` is constructed
  but the shell never injects the service (ui/shell.py:149-159 injects it into home,
  activity, my_automations, settings only).

### (e) Execution events available for live node state

- The runner emits `StepResult` per step through `progress_callback`
  (engine/workflow.py:853-855) and cancels via `cancel_check` checked before every
  step (engine/workflow.py:832-842); `WorkflowService.run_workflow` forwards both
  (controller/service.py:151-167) and `run_desktop_approved` does the same
  (controller/service.py:208-249).
- `ui/workers.py WorkflowWorker` (workers.py:17-63) already wraps these into Qt
  signals (`progress`, `finished`, `failed`) with a QThread and queued connections —
  reuse it for editor runs (P6) instead of a new worker.
- Node state mapping: a node shows "Running…" from run start until its StepResult
  arrives; SUCCEEDED/VERIFIED → done badge; FAILED → failed badge (+ evidence in the
  inspector); SKIPPED → skipped badge; a CANCELLED run marks remaining steps skipped
  (engine/workflow.py:833-842, 862-869).
- History per step with evidence persists in `workflow_step_results`
  (storage/database.py:23-31) — the inspector "evidence" section reads the live
  `StepResult` first, and `history()` (controller/service.py:749-753) for past runs.

### (f) UX audit of the current shell

Written in full in docs/UX_AUDIT.md (created in this slice), including per-page
defects and the fixes each queue item applies.

## 2. Design decisions (prompt's list)

### 2.1 Graph semantics

- The editor renders the workflow definition as a **linear directed chain**:
  `Start → step[0] → … → step[n-1] → Finish`.
- Start and Finish are rendered terminals derived from the definition — never
  persisted, never executable (pre-decided in the prompt).
- A connection between two adjacent cards **is** the execution order edge of the
  tuple. There are no crossings, joins, or parallel wires, because the engine cannot
  express them (evidence (a)). Branching is parked (docs/PARKED.md P7) and "Add
  decision" stays hidden until the gates are met.
- Insert-on-connection = insert a step at the tuple index represented by that edge:
  edge(Start, step[0]) → index 0; edge(step[i], step[i+1]) → index i+1;
  edge(step[n-1], Finish) → index n (append). Downstream flow is preserved by the
  tuple shift; the editor and the engine therefore share one executable definition.
- Delete = remove from the tuple; neighbors reconnect automatically (there is exactly
  one chain). Duplicate = insert a copy after it with a fresh step id. These map 1:1
  to controller ops (2.2).
- Reading order on canvas: rows read left-to-right, wraps go to the row below and
  resume at its left edge, routed through an explicit return connector below the row
  (never a fragile serpentine). Row stays unambiguous: exactly one connector leaves a
  row-end card and it carries an arrowhead into the next row's first card.
- Editing during a run is disabled with a banner (pre-decided).

### 2.2 Controller edit-operation API and undo design (Qt-free)

New module `controller/editor.py` (P4), one class:

```python
class WorkflowEditorSession:
    def open(self, workflow: Workflow) -> None
    def workflow(self) -> Workflow          # current definition
    def is_dirty(self) -> bool
    # mutation ops (each validates the WHOLE result via WorkflowRunner.validate,
    # raises WorkflowValidationError on failure and changes nothing):
    def rename_workflow(self, name: str) -> None
    def rename_step(self, step_id: str, name: str) -> None
    def update_step(self, step_id: str, **fields) -> None   # kind-validated fields
    def insert_step(self, step: WorkflowStep, index: int) -> None   # on-connection
    def add_step_after(self, step_id: str | None) -> None   # None = after Start
    def delete_step(self, step_id: str) -> None
    def duplicate_step(self, step_id: str) -> None
    def move_step(self, step_id: str, delta: int) -> None   # bounded reorder
    def set_note(self, step_id: str, text: str) -> None     # layout record, not engine
    # undo/redo: immutable-snapshot stack (≤100), reverses definition edits only
    def undo(self) -> None / def redo(self) -> None / can_undo / can_redo / describe_undo()
```

- Steps are frozen dataclasses, so every op returns a new `Workflow` built with
  `dataclasses.replace` / tuple slicing (engine/workflow.py:70-90).
- Atomicity = "validate the rebuilt Workflow before assigning it as the current one;
  on error, the session keeps the previous definition untouched".
- Undo/redo never touch the layout record or external actions; moving a node is not
  an undoable definition op (it only rewrites the layout record — recorded decision
  AD-011).
- Storage writes go through `WorkflowService.save` (controller/service.py:169-175);
  the session only mutates the in-memory definition, and the page calls the service
  (ui→controller→storage).

### 2.3 Layout record Auto-layout algorithm (pure, in ui/editor/layout.py — no Qt imports)

- Input: ordered `tuple[WorkflowStep,...]` + optional saved positions dict.
- Geometry constants: CARD_W = 232, CARD_H = 88, H_GAP = 56, V_GAP = 96,
  TERMINAL_W = 88, TERMINAL_H = 44, ROW_LIMIT = 6, row direction left→right.
- Algorithm: walk the chain from Start; place each node in order in a row; when a row
  reaches ROW_LIMIT cards, the next card starts a new row below it; the row-wrap
  connector is routed from the row-end card's bottom port, down 20 px into the
  wrap channel, horizontally to the next row's first card's left port; terminals
  participate as chain members (Start lane slot 0, Finish at the end).
- Saved positions override the algorithm per node (the node keeps its spot); all other
  nodes take grid slots in chain order; overlaps between a saved position and a grid
  slot are resolved by nudging the grid slot down by V_GAP (deterministic).
- Output: `LayoutPlan{slots: dict[str, NodeSlot], edges: tuple[EdgeSpec,...],
  wrap_edges: frozenset[str]}` with exact float coordinates; golden tests pin exact
  numbers for: empty workflow, 1 step, 6 steps (single row incl. terminals), 8 steps
  (two rows: verify wrap channel), saved-position override, and a 100-node workflow
  (bounds only, in the performance test).

### 2.4 Keyboard model

- Canvas: Tab / Tab+Shift cycle the focus ring through nodes in chain order; Left and
  Right walk the chain; Up/Down jump to the first card of the row below/above (through
  the wrap connector); Enter opens the inspector; Esc clears selection; F fits to
  screen; `=` and `-` zoom in/out by 25% steps around 100%; Ctrl+wheel zooms
  continuously within [25%, 200%]; Space+drag or drag on empty space pans.
- Editor page: Ctrl+S save; Ctrl+Z undo; Ctrl+Y redo; Delete "remove step" with the
  inline two-step confirm; Ctrl+N New automation (Home primary); Ctrl+1..4 sidebar
  pages (P2 shell requirement).
- Text fields (inspector line edits): Ctrl+Z/Y/S are NOT global — the editor installs
  its shortcuts on the canvas viewport and marks the inspector field actions
  non-shortcut, so typing is never hijacked (tests assert a rename then Ctrl+Z while
  the field has focus does NOT undo the definition until the field commits).

### 2.5 Test strategy

- `tests/test_editor_layout.py`: golden layout tests (exact coordinates), pure Python.
- `tests/test_controller_editor.py`: per-op effects, atomicity (invalid edit leaves the
  workflow unchanged), undo/redo identity, seeded random op sequences
  (random.Random(42)) with invariant checks (unique ids, valid chain, no orphan
  edges), round-trip save/load equality.
- `tests/test_editor_canvas.py`: the REAL `ui/editor/` view driven from the scene
  (QTest mouse mapped from scene coords): selection, edge hit, insert-on-connection,
  zoom buttons, fit, minimap sync, keyboard navigation; no blocking dialogs anywhere.
- `tests/test_editor_run.py` (P6): run feedback from a real service with a fake
  desktop provider; cancel during run; post-failure editing.
- `tests/test_workflow_layouts.py` (P4): layout record save/load, orphan cleanup,
  corruption fallback banner.
- `tests/test_architecture.py` stays authoritative: ui/editor imports only PySide6 +
  controller/engine/storage APIs; `ui/editor/layout.py` must not import PySide6
  (extended check, P3).
- Performance: register marker `canvas_perf` in pyproject.toml; 100-node build+fit
  must finish under a ceiling ≥ 3× the measured median.
- Contrast: tokens computed in tests (WCAG relative luminance) — every text/background
  pair ≥ 4.5:1 (P2).
- Regression corpus (P4): every currently saved + crafted legacy workflow (schema 1/2/3
  files) opens in the editor and round-trips byte-equal after save.

### 2.6 Token set

Colors are Python constants in `ui/styles` (extended in P2/P3) — sampled-by-eye from
the reference mood, refined once in P3 with a QImage sample of the reference (NOT
POSSIBLE: the reference image file does not exist — AD-008; the tokens below come
from the prompt's DESIGN LANGUAGE only, marked as such):

| Token | Value | Used for |
|---|---|---|
| BG_APP | #F5F6F8 | app background |
| BG_CANVAS | #FBFCFE | canvas base |
| DOT_GRID | #DDE3EC | canvas dot grid |
| CARD_BG | #FFFFFF | node cards |
| CARD_BORDER | #E3E7EE | node borders |
| CARD_RADIUS | 12px | node/panel radius |
| ACCENT | #2563EB | selection, primary CTA |
| PRIMARY_BTN | #111827 | dark primary button |
| TEXT_STRONG | #1D2733 | titles |
| TEXT_BODY | #525A66 | body text (7.0:1 on white) |
| TEXT_FAINT | #6B7280 | captions (4.6:1 on white) |
| TINT_ACTION | #FDF0E2 | peach, mutating steps |
| TINT_VERIFY | #EAF6EE | pale green, resolve steps |
| TINT_PROGRESS | #EAF3F8 | progress-note steps |
| TINT_STOP | #FDECEC | FAIL steps |
| TINT_TERMINAL | #F2F4F7 | Start (pale yellow #FCF6E3) / Finish |
| TINT_NOTE | #FBF7DC | note cards |
| STATE_RUNNING / DONE / FAILED / SKIPPED | derived from the four above + icons | run badges |

Every state badge shows icon + word (never color alone). Contrast pairs are asserted
in a test computed from the tokens (≥4.5:1).

### 2.7 Node card anatomy (ui/editor)

- 232×88 card: 44×44 icon tile on the left (category tint + QPainter glyph),
  two-line text block: step name (`NAME_LABEL` 14px, 600 weight) and subtitle line
  (`KIND_LABEL` 12px: plain kind label + mutating marker "changes your computer"
  when mutating), right side 22px state badge zone (run feedback), and a note pin
  dot when the step carries a note.
- Ports: left in-port, right out-port circles (r=5) tinted by the accent when a run
  passes; ports are the only connection hit targets.
- Selected card: 2px ACCENT border + both adjacent edges highlighted (2px ACCENT).
- Overflow menu (chevron) per card: Rename, Edit configuration (opens inspector),
  Insert step after, Duplicate, Move earlier/later, Delete step (two-step confirm).
- Terminals: rounded pill ("Start", "Finish"), pale tint, no ports on the wrong side,
  non-deletable.

### 2.8 Toolbars and panels

- Canvas toolbar (top of the canvas): fit-to-screen, zoom out, "100%" display, zoom
  in, Tidy up (re-run auto-layout for the whole workflow), minimap toggle.
- Step tray (bottom strip): the offered step kinds (grouped: Actions / Check & wait /
  Notes) as draggable chips; drag onto a connection inserts between its endpoints;
  drag onto empty canvas does nothing (banner: "Connect a step to a neighbor: select
  the connector and press +" — no rule invented).
- Inspector (right dock, 300px): closable; shows workflow info when nothing is
  selected; shows step fields by kind (only validator-allowed controls), inline
  validation from the real validator messages, kind summary (read-only/mutating + what
  the kind does), note field, and (P6) live run feedback + evidence block.
- Validation panel (first run button context): warnings vs blocking errors list,
  click-to-navigate to the node.

## 3. Deferred to the queue items that own them

- Recording entry + provenance banner + draft review → P5.
- Run feedback, approval panel (mutating steps), review journey → P6.
- Branching/decision nodes → P7 (parked unless all gates hold — see PARKED.md).
