# Lane B permissions — every command prefix actually run

Format: one line per distinct command prefix (actions with credentials or outside the repo listed explicitly). All work stays inside C:\Users\DELL\once-lane-b.

- (read) git branch --show-current / git status -sb / git fetch / git --no-pager log / git config / git diff / git checkout -b / git remote -v / git push --dry-run
- (write, local) git checkout -b (branch creation)
- (network, authenticated) git push — via Windows PowerShell (`powershell.exe -NoProfile -Command "git push ..."`) because WSL git has no stored credential (decisions B-002)
- (write, venv) powershell.exe: .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt (exact pins, no dependency change)
- (execute) powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1
