# REUSE.md — desktop automation engine, once × microsoft/skill-recorder

Reference repo path on this machine:
`C:\Users\DELL\AppData\Local\SkillRecorder\versions\505c97ae47be5642c0e1b44ebb8d1c1530c298fa`
(that is the locally installed revision of `github:microsoft/skill-recorder`,
version `0.8.0`, MIT license; LICENSE + MIT text already verified in this file's
Phase 1 notes).

This file is only for the current desktop MVP: one unattended Chrome flow,
intent + ordered parameterized steps, approve/verify engine, single check command,
pytest coverage without Chrome, persisted runs, cold-start repeatability.

Rules applied:
- Reuse only what genuinely saves time for that MVP flow.
- Do NOT copy Microsoft branding, third_party/, bundled assets, Copilot CLI /
  Copilot sign-in, Whisper narration, or screen recording bits.
- Do NOT copy the Node/Electron runtime or its npm dependencies; once's desktop
  path is Python + pywinauto + Chrome DevTools Protocol.
- If a file's license or boundary is unclear, reimplement the idea, do not copy.

Reuse decision table
| MVP checklist item | Reference file | Decision | Reason |
|---|---|---|---|
| 1. Engine runs on Windows under a real Chrome from one command | `electron/describer/describer.ts`, `electron/describer/tools.ts`, `electron/recorder/*`, `common/events.ts`, `common/narration.ts`, `electron/sensitive/*` | **Skip** for engine code; **reimplement** the idea only where useful | Those files are Copilot-dependent capture/analysis of a user desktop session (screen video, narration, Copilot CLI auth, terminal logs, frame redaction). Once's MVP needs Chrome automation executed by Once itself, not a Copilot analysis of a recorded session. The recorder already exists in this repo (`recorder/`, `controller/recording.py`) for Once's own AI-assisted recording flow and must not be replaced by Skill Recorder's model. |
| 2. Fixture automation as JSON on disk (intent + ordered steps + params) | `common/automation.ts`, `common/skill.ts`, `common/values.ts`, `common/plan-tools.ts`, `electron/automationbuilder/builder.ts`, `electron/automationbuilder/instructions.ts` | **Reimplement**, do not copy | Skill Recorder's automation/skill schemas are Copilot-agent-generated NL-prompt plans rendered into Scout `automation.json` / `SKILL.md`. That is the wrong contract for once: once wants a deterministic executable step list with typed targets, not NL prompts sent to another agent. The reusable idea is the pattern, not the code: an explicit intent, ordered parameterized steps, named fixed literals substituted at the execution boundary, and a strict validator. once already has `engine.workflow` + `storage.workflows`; the MVP fixture JSON is shaped to that, not to Skill Recorder's schema. |
| 3. Single check command: fixture page host + load fixture JSON + approve + run + verify + exit 0/1 | `evals/builder/run.ts`, `evals/builder/score.ts`, `evals/lib/seed.ts`, `evals/scenarios/*.ts` | **Reimplement**, do not copy | The eval harness is a good conceptual model (fixed scenario -> run builder -> deterministic score against a rubric -> exit code), and the rubric/seed separation is worth borrowing as a design note. But the harness is Node + TypeScript, runs a Copilot builder, and scores NL generalization. once's check command is Python, runs the replay executor against real Chrome, and scores by step status + file/page verification. Copying it would add no Python code we can use; we only keep the rubric-thinking as a design note. |
| 4. Failure path stays honest; pytest covers fixture load + check logic with fake browser actions | `evals/builder/score.ts`, `evals/builder/run.ts`, `evals/scenarios/invoice-extract.ts` | **Reimplement**, do not copy | The scoring idea (forbidden-token + must-use checks on step text) is interesting but not the MVP's failure model. once's failure model is step status propagation, structured evidence, and a single PASS/FAIL verdict from the engine run — already implemented in `check_mvp.py` + `test_check_mvp.py`. No Skill Recorder code is reused there. |
| 5. Persist runs to history SQLite; print run id; second invocation works | Not present in reference in useful form | **Reimplement** | Skill Recorder persists session/analysis recordings and built automations/skill exports, not once-style execution history of approved desktop workflows. once already has `storage/history.py` + `storage/database.py`; the MVP just calls them. |
| 6. Cold-start twice consecutively; no leaked Chrome/profile/server state | `evals/run.ts`, `electron/recorder/*`, `electron/narration/*` | **Skip** | Those address cleanup of a recorder/Electron app's own runtime state. once's cleanup is already explicit: the engine launches an isolated Chrome profile and closes it via `ChromeDevtoolsActions.shutdown()`; the fixture server is a bounded `http.server` stopped in a `finally` block. No reuse needed. |
| 7. DEMO section with exact command, expected result, known gaps | `README.md`, `INSTALL.md` | **Reimplement** | README/docs style is not copyable as code. once writes its own DEMO section in `PROGRESS-DESKTOT.md` from its own verified run. |

What is explicitly NOT reused
- `@github/copilot`, `@github/copilot-sdk`, Copilot sign-in flows, Copilot CLI
  spawning — out of scope and not permitted by the licensing rules.
- Whisper narration, tesseract OCR, screen video capture, frame extraction,
  `electron/recorder/*`, `electron/narration/*`, `electron/sensitive/*` — not
  needed for the MVP and not part of once's Python desktop path.
- `third_party/`, bundled Electron/Chromium runtimes, `sharp`, `koffi`,
  `node-pty`, Electron builder config — not portable to once's stack.
- Skill Recorder's NL-plan → agent-submission → Scout import rendering pipeline
  — once's approval/execution model is different and already exists.
- Any branding, logos, product names, or trademarked text from the reference
  repo.

What the reference did contribute (ideas, not copied code)
- A clear separation between capture, analysis/description, plan, and built-artifact
  rendering — useful as a conceptual boundary when once later adds its own AI-assisted
  recorder/analysis, but implemented independently in once.
- A rubric + seed + run separation for deterministic evaluation — kept as a design
  note for any future once eval harness, but not copied.
- The "values as fixed literals substituted at the render/execution boundary"
  pattern — once already has its own narrower version in the MVP fixture plugin
  (`{url}`, `{text}`, `{cdp_port}` substitution in `check_mvp.py`).

Decision made in this session (simplest option, noted per working protocol)
- The reference repo is useful as a conceptual map, not as a code source for this
  MVP. It does not contain Python, does not target the Chrome DevTools Protocol as
  an automation executor, and is Copilot-centric. I am not copying any file from it.
