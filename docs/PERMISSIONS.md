# Permissions ledger (2026-10-31, A1 session)

Command prefixes actually run this session, with what each does. My tool shell
is bash (Git Bash on Windows); the user-facing verify script is PowerShell 5.1
compatible (run unmodified from the repo root).

| Prefix | Reads | Writes | Deletes |
|---|---|---|---|
| `git branch --show-current` / `git status -sb` / `git log` / `git diff` / `git show` / `git rev-parse` | yes | no | no |
| `git fetch` | yes (remote metadata) | updates remote-tracking refs only | no |
| `git switch -c slice/a1-automation-names origin/main` | yes | creates one branch (nothing overwritten) | no |
| `git add <files>` + `git commit -m` (workflow files, docs) | yes | writes git objects on the slice branch | no |
| `git --no-pager log --oneline --decorate` | yes | no | no |
| `./.venv/Scripts/python.exe --version` | yes | no | no |
| `./.venv/Scripts/python.exe -m pytest ...` (focused and full suites; tmp_path fixtures only) | yes, repo + tmp paths | pytest caches; tests only touch tmp_path | no |
| `./.venv/Scripts/python.exe -m ruff [check|format] ...` (on touched files only; `--fix` once on an import sort in ui/pages/editor.py) | yes | rewrites only the listed source files | no |
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1` | yes (repo) | runs pytest/ruff/smoke checks; app-level output only; no user folders | no |
| `ls` / `tail` / `head` on repo files | yes | no | no |
| built-in file tools: read_files, str_replace, write_file (touched files only) | yes | rewrites only the listed repo files | no |

Not run this session: any git destructive command (no checkout/reset/clean/
stash/prune/force-push), no branch or worktree deletion, no desktop or Chrome
automation (scripts/chrome_demo.py, scripts/notepad_demo.py never invoked), no
dependency changes, no touching of other worktrees or real user folders.
