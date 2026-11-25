# UI reference captures

`defects/` holds the "before" images for the defects in `docs/UI_DEFECTS.md`.
They are real app-window captures of the shell `app.py` builds, rendered
offscreen from synthetic fixtures and saved by
`scripts/capture_ui_defects.py`. Nothing here is a full-desktop capture.

Regenerate them from any checkout with:

```
python scripts/capture_ui_defects.py
```

The script builds its own fixture folder under the system temp directory:
thirteen saved automations (one long name, one short, one accented), two files
that cannot be read, and three history rows (succeeded, failed, still running).
It never reads or writes the real `%LOCALAPPDATA%/Once` folder.

| state | files | what it shows |
| --- | --- | --- |
| Home | `home-960x600.png`, `home-1920x1020.png` | hero, three counts, recent runs |
| My automations | `my-automations-960x600.png`, `my-automations-1920x1020.png` | 13 rows, unreadable-files banner, approval panel open |
| Automation details | `details-960x600.png`, `details-1920x1020.png` | one saved automation in the details page |
| Settings | `settings-960x600.png`, `settings-1920x1020.png` | authorized folders and the acceptance checker |
| Delete dialog | `delete-dialog-960x600.png`, `delete-dialog-1920x1020.png` | the confirmation opened over the shell |

All ten are PNG, under 300 KB each. The dialog is captured at its own size
(400x126), which does not change with the window size.

These images are evidence of a rendering, not a review: a person must open each
one and write one sentence saying what it shows before it is cited as proof.
