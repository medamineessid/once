# Workflow notes

Operational notes about how changes move through this repository. The rules
themselves live in `AGENTS.md` and `docs/WORKING_AGREEMENT.md`; this file records
exceptions and their reasons.

## Engineering-log ordering exception (2026-11-21, PR #1)

`docs/ai_engineering_log.md` is append-only: earlier entries are never edited,
reordered or removed.

PR #1 (`lane-a-merged` into `main`) does not satisfy that as a strict prefix.
The branch inserted 459 lines **between the file header and the first
`2026-10-21` entry** instead of appending them at the end. Nothing was lost:
every one of `origin/main`'s 1289 lines is still present, in order, unedited
(verified by a line-subsequence check: 1289 of 1289 matched). The single
"deleted line" that `git diff --numstat` reports is `main`'s final line, which
lacks a trailing newline.

Shape of the file at `lane-a-merged` HEAD (1748 lines):

| HEAD lines | Content |
| --- | --- |
| 1–4 | header |
| 5–281 | 17 entries dated 2026-11-07 down to 2026-11-01, inserted out of order |
| 282–1567 | the original log, starting at `2026-10-21 — Step 0` |
| 1568–1748 | 9 entries appended at the end, 2026-11-01 to 2026-11-18 |

Two smaller oddities sit in the same diff: two blank lines added inside the
blank separator run before the `2026-10-22 — Draft editing` entry (HEAD lines
293–294), and one blank line of the header block absorbed by the alignment.

Decision: do **not** reorder or edit the log to make it a strict prefix. A
276-line movement inside an append-only artefact is itself a rewrite.

Temporary exception, now closed: while PR #1 was open, `scripts/verify.ps1` ran
`scripts/check_log_append_only.py` with `--mode boundary`, which requires every
base line to survive in order and every inserted block to land at an entry
boundary (next non-blank line is a `## ` heading, or the end of the file). That
was stricter than the `git diff --numstat` deletion count it replaced and still
rejected editing, deleting, reordering, and inserting into the body of an entry.

`--mode prefix` (the new content must start with the old content) is the
permanent rule. PR #1 is merged, so the follow-up has landed: `verify.ps1` is
back on `--mode prefix`, and `tests/test_ci.py` asserts the script never passes
`--mode boundary` again. `tests/test_check_log_append_only.py` also has a CLI
test proving a line inserted in the middle of the log fails under `prefix`.

## Intermittent `FileNotFoundError` in the review-panel test

`tests/test_review_ui.py` failed about one run in three with
`FileNotFoundError` on `repo/extractor.py`. The cause was in the test, not in
the product: `qtbot.waitSignal()` returns a `SignalBlocker` and does **not**
block unless it is used as a context manager (or `.wait()` is called). Three
calls were bare statements, so the test polled the repository while the apply
worker's `git merge --ff-only` was still running. `git` unlinks each file
before writing the merged version, so a poll can land in that window.

Fixed by wrapping the action inside the wait:

```
with qtbot.waitSignal(panel._apply_worker_done, timeout=60_000):
    panel._apply_recorded_approval()
```

The repository was never left in a bad state: the file was present after each
run, and the test now passes repeatedly (5 consecutive runs and a full suite
with a unique `--basetemp`).

The earlier note that a shared pytest temp root caused this was wrong, and has
been corrected here.
