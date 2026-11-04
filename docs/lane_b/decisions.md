# Lane B decisions (ids B-001...; newest decision numbers continue upward)

## B-001 — WSL-side CRLF checkout artifact (2026-11-01)
Question: `git status` showed all 161 tracked files modified on a fresh clone; commit/verify work would be poisoned by line-ending churn.
Choice: `git config core.autocrlf true` locally in this clone (only .git/config; no repo file touched, no commit, no dependency change). Evidence: `git diff --numstat | awk` showed 31570 additions / 31570 deletions (perfect symmetry = line endings only); `git diff --ignore-cr-at-eol --numstat` empty; `git -c core.autocrlf=true status -sb` clean before the config change; after it, `git status -sb` clean and `scripts/verify.ps1` ALL CHECKS PASSED.
Reason: it mirrors the Windows-side checkout behavior that made those files' CRLF endings canonical for this clone, without rewriting any file bytes or discarding anyone's work.

## B-002 — git push must run through Windows PowerShell (2026-11-01)
Question: `git push` from WSL fails with `fatal: could not read Username for 'https://github.com': No such device or address`.
Choice: run `push` (and `pull`/`fetch` where authentication is needed) via `powershell.exe -NoProfile -Command "git push ..."` so Windows Credential Manager is used. Evidence: WSL `git push --dry-run origin main` fails as quoted above; PS-side `git push --dry-run origin main` printed `Everything up-to-date`.
Reason: the Linux tool has no stored GitHub credential; the Windows side does.

## B-003 — B6 fix mechanism: detached-runner registry + exit-hook join (2026-11-01)
Question: a worker that ignores cancel stays busy after cancel_and_join detaches it; how can process exit avoid the PySide6 fail-fast (0xC0000409) on destroying a running QThread?
Choice: at detach, keep `(thread, worker)` in a module-level registry `ui/workers.py _detached_runs` and register a one-time atexit hook `_wait_out_detached_runs` that grants one generous bounded join (30 s, `DETACHED_RUN_EXIT_GRACE_MS`) before Python/PySide6 teardown; a thread that finishes inside the bound is then destroyed safely. Terminate-thread and shiboken ownership tricks were investigated and rejected: shiboken6 no longer exposes a SetOwnership-style API (verified by dir() on the installed PySide6 6.12.0 companion), and PySide6's QThread exposes no `currentThreadId` (verified via dir(QThread)); a native-terminate last resort is therefore parked as an unresolved edge (a worker still busy after 30 s may still abort at teardown, warning logged).
Evidence: experiment scripts (deleted afterward) showed retention alone still exits -1073740791; with the exit hook the B6 subprocess test exits 0; `2 passed in 7.85s`; neighborhood `6 passed in 2.47s`.
Reason: close stays non-blocking (5 s production bound unchanged); the 30 s grace only runs at interpreter exit, after the window is already gone; real engine runs stop per step (timed), so the pathological edge remains rare and visibly logged.
