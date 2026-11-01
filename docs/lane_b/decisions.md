# Lane B decisions (ids B-001...; newest decision numbers continue upward)

## B-001 — WSL-side CRLF checkout artifact (2026-11-01)
Question: `git status` showed all 161 tracked files modified on a fresh clone; commit/verify work would be poisoned by line-ending churn.
Choice: `git config core.autocrlf true` locally in this clone (only .git/config; no repo file touched, no commit, no dependency change). Evidence: `git diff --numstat | awk` showed 31570 additions / 31570 deletions (perfect symmetry = line endings only); `git diff --ignore-cr-at-eol --numstat` empty; `git -c core.autocrlf=true status -sb` clean before the config change; after it, `git status -sb` clean and `scripts/verify.ps1` ALL CHECKS PASSED.
Reason: it mirrors the Windows-side checkout behavior that made those files' CRLF endings canonical for this clone, without rewriting any file bytes or discarding anyone's work.

## B-002 — git push must run through Windows PowerShell (2026-11-01)
Question: `git push` from WSL fails with `fatal: could not read Username for 'https://github.com': No such device or address`.
Choice: run `push` (and `pull`/`fetch` where authentication is needed) via `powershell.exe -NoProfile -Command "git push ..."` so Windows Credential Manager is used. Evidence: WSL `git push --dry-run origin main` fails as quoted above; PS-side `git push --dry-run origin main` printed `Everything up-to-date`.
Reason: the Linux tool has no stored GitHub credential; the Windows side does.
