# Once — AI Engineering Log

Append-only. Format per AGENTS.md. Human fills in the "Human review" line.

## 2026-10-21 — Step 0: Pre-flight, evidence, decisions   (commit: n/a — git repo not yet initialised; Step 1 runs `git init`)

- Task: Establish a verified, pinned toolchain decision record without writing application code: detect environment, look up current facts (Python support status, PySide6 + dev-tool versions/compatibility, Microsoft naming docs, `st_birthtime` availability), choose the Python version, record everything in `docs/decisions.md`.
- AI contribution: created `once/` folder, `AGENTS.md` (Master Prompt verbatim), `docs/decisions.md` (evidence + D1–D10 + version decision), this log. No application code written (per step constraint).
- Defect found: two retrieval attempts failed and were worked around honestly — (a) pypi.org/project/Send2Trash/ and /ruff/ served a bot "Client Challenge" page instead of content → used `pip index versions` (live PyPI query) and the PyPI JSON API; (b) github.com/arsenet/send2trash/releases returned 404 (wrong owner) → correct repo is arsenetar/send2trash, release date taken from a search snippet and flagged as best-evidence in decisions.md.
- Verification: ran locally — `py -0p` (3 interpreters listed), `python --version` (3.14.3), `git --version` (2.55.0.windows.4), `cmd //c ver` (10.0.26300.9550), `st_birthtime` presence check on 3.14.3 and 3.13.5 (True/True), `pip index versions` for pytest/pytest-cov/pytest-qt/ruff/pyinstaller/send2trash (latest: 9.1.1 / 7.1.0 / 4.5.0 / 0.17.1 / 6.22.3 / 2.1.0), `pip install --dry-run send2trash==2.1.0` on 3.14 → "Would install Send2Trash-2.1.0" exit 0. Fetched and cited: devguide.python.org/versions, pypi.org/project/PySide6 (6.12.0, Requires-Python >=3.10,<3.16, win_amd64 abi3 wheel present), learn.microsoft.com naming-a-file (reserved chars/names incl. superscript variants), pypi.org/pypi/send2trash/2.1.0/json (classifiers to 3.14). NOT verified: send2trash 2.1.0 release date (search snippet only), ruff `target-version = "py314"` support (checked at Step 1).
- Outcome: PASSED
- Human review: 

## 2026-10-22 — Revised vision milestone: workflow foundation   (commit: 2eaecb4)
- Task: Reconcile the file-management-first specification with the broader
  workflow automation vision and implement a real, testable orchestration base.
- AI contribution: revised the product definition and roadmap; added immutable
  workflow models, deterministic execution with failure propagation and
  cancellation, a Qt-free controller service, and a minimal UI trigger.
- Defect found: the existing controller package contained only `__init__.py`;
  the first implementation therefore added the missing service explicitly
  rather than placing workflow logic in the UI.
- Verification: `.\.venv\Scripts\ruff.exe format .` reformatted one file;
  `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`;
  `.\.venv\Scripts\python.exe -m pytest -q` printed `25 passed, 1 skipped`;
  `QT_QPA_PLATFORM=offscreen .\.venv\Scripts\python.exe app.py --smoke-test`
  exited 0. The skipped test reported that symbolic links are unavailable.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Step 1: Project foundation   (commit: d1375f0)
- Task: Establish the launchable Qt skeleton, pinned development environment, test fixtures, architecture guards, and quality configuration.
- AI contribution: completed the dependency manifest, Ruff and pytest configuration, deterministic Windows-safe fixture writes, and Step 1 validation.
- Defect found: fixture text writes used Windows newline translation, making the expected deterministic byte size wrong; switched fixture creation to UTF-8 bytes. Ruff's security and naming rules also needed test-specific ignores for required subprocess and `test_S<n>` safety names.
- Verification: `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` installed PyInstaller 6.22.3; PySide6 import probe printed `PySide6 import ok`; `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`; `.\.venv\Scripts\ruff.exe format --check .` printed `17 files already formatted`; `.\.venv\Scripts\python.exe -m pytest -q` printed `13 passed in 0.57s`; `.\.venv\Scripts\python.exe app.py --smoke-test` exited 0.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Step 2: Scanner and filters   (commit: 3c6b4c9)
- Task: Build a read-only folder scanner and pure filter utilities that return immutable `FileEntry` objects without mutating the filesystem.
- AI contribution: created `engine/scanner.py`, `engine/filters.py`, and `engine/fs.py`; expanded the domain model in `engine/models.py`; added `tests/test_scanner.py` covering hidden files, symlinks, Unicode names, suffix rules, and deterministic scans.
- Defect found: the first scanner version treated all files as hidden because it used Windows attribute checks incorrectly on a path object. The test fixture also used newline-sensitive byte-size assumptions that were not Windows-safe.
- Verification: `.\.venv\Scripts\ruff.exe check .` printed `All checks passed!`; `.\.venv\Scripts\ruff.exe format --check .` printed `20 files already formatted` after the final format pass; `.\.venv\Scripts\python.exe -m pytest -q` printed `20 passed, 1 skipped in 1.32s`.
- Outcome: PASSED
- Human review:

## 2026-10-22 — Phase 0: Resume check   (commit: pending)
- Task: Confirm the repository boundary and resume state, preserve the existing Step 0 evidence, and establish progress tracking.
- AI contribution: verified the workspace, Git state, environment pins, existing skeleton, and baseline quality results; added progress tracking.
- Defect found: baseline fixture expected POSIX newline byte size on Windows; this is recorded for the Step 1 foundation fix.
- Verification: `git rev-parse --show-toplevel` returned `C:/Users/DELL/once` with no commits; `py -0p`, `python --version`, and `git --version` returned the recorded environment; `.venv` package list showed the pinned packages; smoke test passed; pytest reported `1 failed, 12 passed`; Ruff check passed and format check reported `tests/test_architecture.py`.
- Outcome: PASSED
- Human review:
