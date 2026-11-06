# docs/screenshots/latest/INDEX.md

Captured, not reviewed.

Source: `scripts/capture_screenshots.ps1` (real shell through
`scripts/capture_shell_pages.py`, `QT_QPA_PLATFORM=offscreen`, 2026-11-02,
capture exit code 0, all distinct + non-empty). 24 PNGs = 8 pages x 3 sizes.
The editor capture opens a fresh definition through the shell's own
`_show_editor()` entry point; the review capture opens the demo workflow,
so it shows the relabelled "Automation details" mode (D14). The recording
capture opens the dedicated recording route through `_show_recording()`;
a page-state leak it exposed in the create capture is fixed in the driver.

| File | Page | Size (bytes) |
|---|---|---|
| 1280x800-home.png | Home | 10351 |
| 1280x800-my-automations.png | My automations | 10098 |
| 1280x800-activity.png | Activity | 8580 |
| 1280x800-settings.png | Settings | 9898 |
| 1280x800-create-automation.png | Create automation | 10819 |
| 1280x800-editor.png | Editor | 10674 |
| 1280x800-recording.png | Recording | 8688 |
| 1280x800-review.png | Review | 13680 |
| 1366x768-home.png | Home | 10472 |
| 1366x768-my-automations.png | My automations | 10209 |
| 1366x768-activity.png | Activity | 8702 |
| 1366x768-settings.png | Settings | 10021 |
| 1366x768-create-automation.png | Create automation | 10924 |
| 1366x768-editor.png | Editor | 14529 |
| 1366x768-recording.png | Recording | 8738 |
| 1366x768-review.png | Review | 14951 |
| 1920x1080-home.png | Home | 14120 |
| 1920x1080-my-automations.png | My automations | 14011 |
| 1920x1080-activity.png | Activity | 12440 |
| 1920x1080-settings.png | Settings | 13644 |
| 1920x1080-create-automation.png | Create automation | 14695 |
| 1920x1080-editor.png | Editor | 17936 |
| 1920x1080-recording.png | Recording | 12456 |
| 1920x1080-review.png | Review | 21796 |
