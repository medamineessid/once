# UI spec

The machine-readable source of this page is `scripts/ui_spec.py`; a test asserts
the two never drift. `scripts/ui_audit.py` enforces every line, for each page and
state, at 100/125/150% scale and at 960x600, 1280x800 and 1920x1020.

## Required elements

Every objectName below must exist, be visible, have a non-zero size and lie
inside the window (or its page's scroll viewport). Missing, hidden, zero-size or
off-screen is a finding.

### Home

| objectName | element |
| --- | --- |
| `sidebarHomeButton` | sidebar row 1 |
| `sidebarAutomationsButton` | sidebar row 2 |
| `sidebarActivityButton` | sidebar row 3 |
| `sidebarSettingsButton` | sidebar row 4 |
| `heroPanel` | the blue hero panel |
| `heroMicro` | "N saved automations ready" |
| `heroLine` | display line 1, "AUTOMATE" |
| `heroLineAccent` | display line 2, "ANYTHING." |
| `heroSubtitle` | guiding line under the hero |
| `circleButton` | the Record circle |
| `buildButton` | the Build control |
| `statNumber` | a stat tile's number |
| `activityLabel` | "YOUR RECENT RUNS" |

### My automations

| objectName | element |
| --- | --- |
| `pageBand` | the header band |
| `pageMicro` | the micro label |
| `pageTitle` | "MY AUTOMATIONS" |
| `pageSubtitle` | the one-line description |
| `workflowList` | the list of saved automations |
| `previewSelectedButton` | Preview, in the toolbar row above the list |
| `clearDraftsButton` | Clear unnamed drafts, in the same toolbar row |

With the attention banner shown: `banner`, `bannerTitle`, `bannerBody`,
`bannerRevealButton` (one Reveal in folder action per unreadable file).

### Activity

| objectName | element |
| --- | --- |
| `activitiesList` | the run list |
| `detailsContainer` | the detail area of the selected run |
| `activityDetailsLabel` | its text |

### Settings

| objectName | element |
| --- | --- |
| `settingsScroll` | the scroll area |
| `settingsWidget` | its content |

### Automation details

| objectName | element |
| --- | --- |
| `detailsScrollArea` | the scrolling body |
| `goalLabel` | the goal line |
| `stepsList` | the step list |
| `approvalPanel` | the permission panel |
| `approvalDetails` | the step detail text |

### Permission panel (inside Automation details)

| objectName | element |
| --- | --- |
| `approvalPanel` | the panel |
| `approvalPanelTitle` | its title |
| `approvalStepList` | the ordered action list |
| `approvalPanelBindingNote` | the footnote |
| `primaryActionButton` | "Approve for this run" — always visible |
| `secondaryActionButton` | "Do not run" — always visible |

### Confirm-delete dialog

| objectName | element |
| --- | --- |
| `deleteConfirmDialog` | the dialog |
| `deleteConfirmTitle` | its title |
| `deleteConfirmBody` | its message |
| `confirmDeleteButton` | Delete, `variant=destructive` |
| `cancelDeleteButton` | Cancel, `variant=secondary` |

### Parameter dialog

| objectName | element |
| --- | --- |
| `parameterDialog` | the dialog |
| `dialogBody` | its body |
| `fieldLabel` | one label per required value |
| `parameterOkButton` | Continue, `variant=primary` |
| `parameterCancelButton` | Cancel, `variant=secondary` |

## Structural rules

| rule | page | requirement |
| --- | --- | --- |
| `header_gaps` | every page with a band | 8–12px between micro label, title and subtitle |
| `sidebar_equal_width` | every page | the four sidebar items share one width and one left edge |
| `sidebar_focus_not_pill` | every page | keyboard focus draws an outline, never the active pill fill |
| `hero_lines_stacked` | Home | both display lines start at the same left edge and stack |
| `hero_micro_gap` | Home | 10–14px between the micro label and the first display line |
| `record_circle_padding` | Home | circle ≥ 96px, icon ≤ 48px |
| `build_label_centred` | Home | the Build label fits its button |
| `row_run_label` | My automations | only a running row says "Running"; a row waiting for approval keeps "Run" (disabled) |
| `settings_checker_border` | Settings | the Configure checker control has a visible border on all four edges |

## Defect classes the audit checks on every page and state

| check | meaning |
| --- | --- |
| `a-contains` | a visible widget leaves its parent, the window or its scroll viewport |
| `b-overlap` | two visible leaf widgets overlap and are not ancestor/descendant |
| `c-clipped` | text needs more room than the widget gives it |
| `d-contrast` | a button's text is under 3:1 against its own background |
| `d-border` | an outlined button has no visible border on one of its four edges |
| `e-required` | a required element is missing, hidden, zero-size or off-screen |
| `f-animation` | hovering or pressing moves or resizes the control |
| `f-rule` | a structural rule above does not hold |

## Running it

```powershell
python scripts/ui_audit.py                 # real Windows platform, all scales and sizes
python scripts/ui_audit.py --offscreen     # the CI subset (100% only, no real windows)
```

It writes app-window PNGs and `audit-report.json` to a temp folder, prints a
summary and exits non-zero when it finds anything. The data folder is synthetic
(`scripts/build_ui_fixtures.py`); the real one is never opened.

**Standing rule:** run the full audit before every UI-visible pull request and
attach the summary. `scripts/verify.ps1` runs the offscreen subset so CI keeps
the same checks green.
