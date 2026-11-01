# Lane B append-only log

## 2026-11-01 — session 1 (append-only; newer entries below)
- Verified clone state: main == origin/main == afc342e; `scripts/verify.ps1` ALL CHECKS PASSED (pytest `468 passed, 2 skipped in 112.43s`), full output pasted in session transcript.
- Installed exact pinned requirements (requirements-dev.txt) into this clone's `.venv`: PySide6 6.12.0, pytest 9.1.1, pytest-cov 7.1.0, pytest-qt 4.5.0, ruff 0.17.1, pyinstaller 6.22.3 (+ runtime pins). No dependency files changed.
- Saved session prompt verbatim to docs/LANE_B_PROMPT.md; created docs/lane_b/ ledger (progress/decisions/questions/parked/log/permissions). Landed on main as `45706bc`.

## 2026-11-01 — B6: detach-path exit crash proven and fixed
- Pre-fix proof: subprocess child exercising cancel_and_join's detach path with a cancel-ignoring worker exited with `3221226505` (0xC0000409) after printing `DETACH=True`; a control experiment (retention-only, exit-hook omitted) still exited `-1073740791`, proving the exit-hook join is the required mechanism.
- Fix in ui/workers.py: module-level `_detached_runs` registry + one-time atexit hook with 30 s bounded grace join; disabled paths rejected: shiboken6 ownership API absent in PySide6 (dir evidence), QThread.currentThreadId absent (dir evidence).
- Focused verification: `tests/test_b6_cancel_detach_exit.py` → `2 passed in 7.85s`; `tests/test_close_during_run.py tests/test_workers.py` → `6 passed in 2.47s`.

