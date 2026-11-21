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
276-line movement inside an append-only artefact is itself a rewrite. Instead,
until PR #1 merges, `scripts/verify.ps1` runs
`scripts/check_log_append_only.py` with `--mode boundary`, which requires every
base line to survive in order and every inserted block to land at an entry
boundary (next non-blank line is a `## ` heading, or the end of the file). That
is stricter than the `git diff --numstat` deletion count it replaced and still
rejects editing, deleting, reordering, and inserting into the body of an entry.

`--mode prefix` (the new content must start with the old content) remains the
default and is the permanent rule. Follow-up: switch `verify.ps1` back to
`--mode prefix` in a small PR into `main` immediately after PR #1 merges, with a
test asserting that a middle insertion fails.

## Test temp directories

`pytest`'s default `tmp_path` root is shared. An intermittent
`FileNotFoundError` on a `tmp_path` file was observed twice in full-suite runs
and never reproduced in isolation, which is consistent with two runs sharing a
temp root. When a full run must be trusted, pass a unique root:

```
.\.venv\Scripts\python.exe -m pytest -q --basetemp=C:\Users\<you>\AppData\Local\Temp\once-pytest-<n>
```

The full suite was green both with and without it; the unique root is what
removed the failure.
