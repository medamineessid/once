# TASK-016 — Windows packaging PyInstaller spike (dependency-approved-needed)

Lane: `tests` · Difficulty: `normal` · Owner review required: `yes` · Label: `lane/tests`, `dependency-approved` · Size: `M`

## Goal

Find out whether the current `once.spec` can produce a Windows executable that
starts the shell and exits cleanly, and record the exact command, exit code and
limits. This is a spike: the output is a decision and evidence note, not a
release promise.

## Files allowed

- `once.spec`
- `scripts/packaging_spike.py` (new)
- `docs/evidence/packaging_spike.md`

## Files forbidden

- `engine/`, `storage/`, `recorder/`, `controller/`, `integrations/`, `ui/`
- `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`
- `.github/`, `scripts/verify.ps1`, `scripts/check_log_append_only.py`
- `docs/ai_engineering_log.md`, `docs/STATE.md`, `docs/PLAN.md`
- step schema, workflow validators, approval code

## Acceptance commands (run yourself)

```
python -m pytest -q tests/test_check_pr_guards.py
ruff check .
ruff format --check .
```

The owner ran these three commands on this base and they pass. Paste the
packaging command and its real exit code in the PR as well.

## Screenshots

None unless the packaged app itself is launched; then capture the app window
only and say it came from the packaged executable, not from source.

## Out of scope

Adding PyInstaller to requirements, changing CI, signing, installer creation,
auto-update, or claiming a release before `dependency-approved` is granted.

## Notes

`dependency-approved` is required before any dependency change. If the spike
needs one, stop, record the need and wait for the owner; do not edit
requirements files.
