# Manual acceptance checklist (first-time user, about 20 minutes)

Purpose: a repeatable, honest manual pass over Once. Automated tests cover the
same paths offscreen; this checklist is what a human should do once before a
release. Tick items yourself and note anything unclear in
`docs/ai_engineering_log.md` under "Human review".

## 1. Start Once
- [ ] Launch `Once.exe` (packaged build) or run `python app.py` from the venv.
- [ ] A window opens with a **Workflows** tab (list plus a preloaded demo
      workflow) and an **Agent proposals** tab.
- [ ] Nothing has to be configured before the app is usable.

## 2. Understand what Once does and does not automate
- [ ] Once runs only allowlisted, exactly-configured commands you configure.
- [ ] Once never runs arbitrary shell commands, never clicks or types in other
      applications, never talks to the internet unless you explicitly enabled
      cloud analysis (Gemini) or run an external coding agent on request.
- [ ] Where to see this: the proposal panel is the only place changes are
      made, and only after your explicit approval.

## 3. Configure a verifier (acceptance checks)
- [ ] On the Agent proposals tab click **Configure acceptance checks**.
- [ ] Fill in: the synthetic cases file (a JSON file you have written with
      known expected values), the command that checks one input (exactly one
      `{input}` placeholder, plus at most one `{checkout}` placeholder for
      worktree verification), a timeout, and a worktree directory **outside**
      your target repository.
- [ ] Save; the config is written to `%LOCALAPPDATA%\Once\verifier.json` only
      after the same validation a restart applies.
- [ ] Enter an invalid command (two `{input}` placeholders) and confirm the
      dialog explains the problem instead of saving.

## 4. Run a workflow
- [ ] Select the demo workflow on the Workflows tab, click **Run**, and watch
      step statuses (SUCCEEDED/FAILED/SKIPPED appear as recorded evidence).
- [ ] Click **Cancel run** during a run and confirm it stops cleanly.
- [ ] Open a saved workflow JSON file and confirm it loads; save a new one
      from the form.

## 5. Review evidence and a proposal
- [ ] In a Git repository with a real defect, run: verification first
      (evidence of failing fields appears), then **Request agent proposal**.
- [ ] Confirm the tab shows the EXACT proposed diff (no summary paraphrase),
      the changed files, bounded redacted output tails only.
- [ ] Confirm that a proposal whose verification has not passed yet cannot be
      approved (the button stays disabled with an explanation).

## 6. Approve or reject a proposal
- [ ] Reject a proposal first and confirm the repo keeps its original branch
      content and the rejection is recorded (it blocks later approval).
- [ ] Make a second proposal, let pre-merge verification pass, click
      **Approve and apply proposal** only after reading the diff, then confirm
      the change lands as a fast-forward on your branch and a rerun verifies.

## 7. Recover from a failed agent run
- [ ] When an agent run fails, read the error: it names the branch where the
      incomplete output was parked (`once/agent/...` or
      `once/agent/parked-...`) or explains it could not park safely, with the
      exact branch you are on.
- [ ] In Git, confirm your branch content is unchanged; the parked branch
      holds the agent output for inspection. `git checkout` your branch and
      re-propose.
- [ ] A dirty or staged repository must be refused before any Git plumbing
      happens: your uncommitted work is untouched.

## 8. Restart and inspect history
- [ ] Close Once and open it again.
- [ ] The Agent proposals tab still lists past proposals with their recorded
      decisions; recorded approvals can be applied after a restart via
      **Apply previously approved proposal**.
- [ ] History details show past workflow runs and verification runs (per case,
      per field).
- [ ] `%LOCALAPPDATA%\Once` contains `once.db`, `workflows\`, `recordings\`,
      and `logs\once.log`; deleting the app folder does not delete this data.

## Known manual-only items
- The startup-failure modal (corrupt data folder/database) is shown by the
  packaged exe and was verified by reading the dialog text over Windows UI
  Automation; clicking OK in the real dialog has only been done by a human
  (report result here if you try it).
- Live paid coding agents and live Gemini analysis were never run in
  development (policy: no unauthorized cloud access).
