# Once product vision

Once is a local-first supervised test-and-fix orchestrator. A user describes a
task such as “test these invoices and fix extraction bugs,” and Once runs a
bounded, allowlisted process rather than executing arbitrary instructions.

## Six-step flow

1. **Describe:** capture the task and explicit acceptance criteria.
2. **Run:** execute configured tools against controlled inputs.
3. **Verify:** compare observable outputs, logs, and monitoring evidence with
   expected results.
4. **Send evidence:** after explicit authorization, provide a redacted,
   delimited evidence bundle to an approved coding-agent integration.
5. **Propose and review:** receive a proposed diff on a separate branch and
   show the user the changes, risks, and test plan.
6. **Rerun:** apply only after human approval, rerun verification, and stop at
   the configured iteration, wall-time, or no-progress limit.

## First target

The first domain target is the Hotix invoice extractor
([medamineessid/hotix-invoice](https://github.com/medamineessid/hotix-invoice)):
a WPF C# client and Python FastAPI backend using Gemini, PaddleOCR, and Groq.
Precision matters more than recall. No real invoices are available, so the
initial ground truth is synthetic invoices with known values.

The first implementation slice is headless: a strictly validated acceptance
case, an allowlisted extractor command, JSON-output verification, and a
redacted evidence bundle. It does not call a coding agent or change Hotix.

## Deferred

- Mutating desktop UI actions such as clicks and typing.
- Browser automation.
- Unrestricted shell, Python, or AI-generated code execution.
- Automatic coding-agent merges or pushes.
- Live cloud transmission without explicit configuration and consent.
- Accuracy claims based on real invoices before representative ground truth is
  available.
