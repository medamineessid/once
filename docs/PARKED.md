# Parked work (PARK AND CONTINUE protocol)

The default is applied immediately; the item stays parked until someone answers it,
per the session prompt ("PARK AND CONTINUE").

## PARKED-1 — Branching / decision nodes in the editor (P7)

- **What:** a "decision" node with two outgoing branches (Yes/No) on the canvas,
  validated conditions, branch lanes.
- **Why parked:** implementing it requires engine-side execution semantics that do
  not exist. Evidence:
  - The model has no branch or condition construct:
    `Workflow` is a named tuple-list — engine/workflow.py:84-90; `WorkflowStep`
    (engine/workflow.py:70-81) has no successor field.
  - The runner executes the tuple strictly in order and stops the remaining steps on
    any non-success (engine/workflow.py:832-869) — a decision cannot change that
    without changing the runner/validation semantics, which the working agreement's
    hard rule 1 and the prompt's HARD STOPS forbid changing for existing policies
    (a DECISION kind would have to enter the replay allowlists —
    engine/replay.py:30-39, 67-80 — which ARE the approval-gate policy; adding a kind
    there changes approval semantics).
  - No existing test corpus knows decision nodes; the regression corpus and golden
    execution traces have nothing to compare a branching execution against.
- **Gates check (prompt P7):**
  | Gate | Verdict |
  |---|---|
  | 1. Backward-compatible additive schema | Formally possible (new optional fields + new schema version) BUT the executor must evaluate conditions, which does not exist; "existing validators and executor behavior unchanged" can hold only for old workflows, while new branching workflows have no defined execution semantics at all |
  | 2. Structured, validated conditions on recorded outcomes | Designable (step status / verification result) — not implementable without (1) |
  | 3. A decision runs exactly one branch; no synchronization, no parallelism | Consistent design, gated on (1) |
  | 4. Approval covers every branch step through the existing gate | The per-workflow approval (engine/desktop.py:34-40) approves the whole definition, so it could cover branches — but the gate's underlying policy allowlist must accept the new kind (conflict with HARD STOP) |
  | 5. Explicit fallback for unevaluable conditions | Consistent design, gated on (1) |
  | 6. Cycles rejected | Consistent design (tuple order cannot cycle) — but cycle detection only becomes meaningful with branch fields |
  | 7. S1–S12 stay green | Presumed achievable |
- **Conclusion:** the feature is parked, because implementing it means changing the
  replay/approval policy semantics — the prompt's own HARD STOP — and no gate
  combination can satisfy "existing gate, unchanged policy" with a new executable
  kind. Keeping "Add decision" hidden is the honest default.
- **Interim choice in force:** the editor renders a strictly linear chain (see
  docs/design/visual_editor.md §2.1); no decision UI exists.
- **How to un-park:** a human decision that explicitly lifts the working-agreement
  hard rule 1 for a documented branch policy, a new engine milestone (schema v4,
  condition evaluation, approval spanning branches, golden traces), and a green
  plan at that point.
- **Evidence of verification:** none — this is a design-phase park recorded in P1
  (the engine facts above are cites, re-checked at P7 before the verdict is final).
