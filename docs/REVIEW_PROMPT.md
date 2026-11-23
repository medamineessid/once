# Reusable PR review prompt

Paste this into a fresh review session for PR **N**. Replace `N` and the task
file only. Do not accept a PR as done from the author's prose alone.

```text
Review PR N in the once repository. Re-read repo state before acting: check
branch, status and gh.exe state yourself. Read docs/COLLABORATOR.md,
docs/PLAN.md, .github/CODEOWNERS and the task brief named in the PR body first.
Apply the docs-versus-code rule: if docs/STATE.md or an old doc disagrees with
the code and pasted output, the repo state wins; report the drift, do not edit
STATE.md.

Return these sections, in this order:

1. Diff and scope. Paste `git.exe diff --stat origin/main...HEAD`. List every
   changed path and say whether it is allowed by the brief. Name any forbidden
   path (engine/, integrations/, recorder/, controller/, storage/, step schema,
   docs/ai_engineering_log.md, docs/STATE.md, .github/ unless this is the
   governance PR). Say explicitly: "scope OK" or "scope violation: <paths>".

2. Tests changed. List added, edited, deleted, skipped and weakened tests.
   A skip or weakened assertion is a REQUEST CHANGES unless the same line has
   `# allowed-skip: <reason>` and the brief permits it.

3. Evidence pasted. Quote the exact pytest summary line and the ruff check /
   ruff format --check result lines from the PR body. State which evidence
   level from docs/PLAN.md is claimed (tests only, tests + own real screen,
   real desktop) and whether the pasted output supports it. For UI work, name
   each app-window screenshot and the one sentence describing it against
   docs/UI_SPEC.md.

4. Five riskiest changes. Give exactly five entries as `path:line — risk —
   question for the author`. If fewer than five risky changes exist, say so and
   list the ones that matter.

5. Verdict. One of APPROVE, REQUEST CHANGES or ESCALATE. REQUEST CHANGES for a
   scope violation, missing pasted output, a weakened test, or an unsupported
   evidence claim. ESCALATE for approval, safety, schema, policy or dependency
   questions. APPROVE only when every check above is satisfied.

6. Could not verify. List what you did not run, could not see, or could not
   confirm from the terminal output. Never write "looks good" for an image you
   did not view.
```

Reviewer checklist (short form):

- [ ] Repo state re-read before review (branch, status, gh.exe state).
- [ ] Branch, status and task brief agree with the PR.
- [ ] Only allowed files changed; owner-only paths untouched.
- [ ] Pytest and both ruff commands pasted with real output.
- [ ] Evidence level matches what was actually run; gaps say "not verified".
- [ ] No bare `except:`, no `except Exception: pass`, no deleted tests.
- [ ] Verdict and "could not verify" section present.
