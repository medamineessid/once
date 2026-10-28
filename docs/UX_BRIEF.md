# Once UX Brief

Date: 2026-10-27. Written from evidence only: README.md, AGENTS.md, ui/main_window.py (the old window's capabilities), ui/pages/*, ui/shell.py, controller/service.py. The USER INPUT block of the session prompt was empty, so **every product guess is tagged ASSUMPTION** and can be corrected by the user.

## 1. Audience and promise

**Audience:** an ordinary, non-technical Windows user who wants repetitive computer work automated without scripting. (Source: README.md:3-6 — "a local Windows desktop application for building and running bounded, observable workflows"; AGENTS.md — "an ordinary, non-technical user".)

**Promise (verbatim from the product):**
- Home tagline (ui/pages/home.py:28-31): "Your personal assistant for automating repetitive computer tasks."
- README.md:3-6: bounded, observable workflows; the deterministic engine controls execution; no unrestricted scripts or opaque AI actions.

**First five minutes should feel like:** open Once, see one clear action ("Try a demonstration"), run it, watch it succeed in Activity, then describe one own task and be walked through creating an automation — all offline, nothing leaving the machine. (ASSUMPTION: the user's empty INPUT did not specify this; derived from the Home page's existing two actions, home.py:54-69.)

**How automations get created (ASSUMPTION, needs user confirmation):** a mix — a typed task form as the default entry point, with "Record what I do" offered in the same create flow (recording exists in the old window: ui/main_window.py:570-583, 423-462), and AI proposals reviewed through the existing approval path (ui/review_view.py:47). The brief's journey J2/J5/J6 assume this mix.

## 2. User journeys (each 3-6 plain-language steps)

**J1 — Try a demonstration**
1. Open Once; the Home page shows the welcome message and "Try a demonstration".
2. Click "Try a demonstration"; the button shows the run is in progress.
3. The run finishes with a plain result ("Run succeeded: N steps recorded").
4. Open Activity: the demo run appears in the list with its outcome.

**J2 — Create an automation**
1. Click "Create an automation" on Home (or "New automation" on My automations).
2. Type what the automation should do in plain language; press Create.
3. Optionally add, reorder or remove steps in the draft (same capabilities as the old window's form: ui/main_window.py:101-104, 89-93).
4. Optionally click "Record what I do" to capture steps instead of typing them (J5).
5. Save; the new automation appears in My automations.

**J3 — My automations**
1. Open My automations from the sidebar.
2. Click a row to see its steps.
3. Click "Preview" to see what would happen (nothing executes).
4. Click "Run" and confirm; watch progress.
5. Cancel a running automation from the same screen.

**J4 — Activity**
1. Open Activity from the sidebar.
2. See the list of past runs, newest first.
3. Click a run to see its steps and outcomes.
4. Use the details to understand what happened without opening a log.

**J5 — Recording lifecycle (inside the create flow)**
1. While creating an automation, choose "Record what I do".
2. Perform the task once on screen; stop when done.
3. Review the recorded steps offline (no cloud analysis without consent; AGENTS.md recorder amendment).
4. Delete a recording you no longer want.

**J6 — AI proposals**
1. Open a proposal from the review screen.
2. Read the diff and the verification evidence in plain language.
3. Approve or reject; nothing is applied without explicit approval.
4. Approved changes are re-run against tests before anything consequential happens.

**J7 — Desktop and browser steps**
1. Add a desktop or browser step in the create flow.
2. See exactly which steps will click, type or change something before approving.
3. Approve through the one existing approval path (engine/desktop.py approve_desktop_workflow).
4. Preview, then run, then check the result in Activity.

**J8 — Settings**
1. Open Settings from the sidebar.
2. Choose the folder Once is allowed to work in.
3. Configure the acceptance checker (verifier) if used.
4. Nothing here runs automations; it only configures.

**J9 — Capability checklist**
1. Open docs/MVP_CHECKLIST.md (for maintainers).
2. Every old-window capability has a new location (file:line), a test, and DONE/MISSING.
3. The default-window switch is proposed to the user, never made by the agent.

## 3. Page-by-page content spec

Sidebar (fixed): **Home, My automations, Activity, Settings** — these four only, full height, flush to the left edge, no stray text (ui/shell.py:63-127 is the current implementation; its footer is corrected by the defect list in section 5).

### Home
- **Shows:** the welcome title + tagline; the recent-activity summary (last successful runs) drawn from the real history (ui/pages/home.py:106-122); a short "what's next" affordance.
- **Single primary action:** "Create an automation" (home.py:54-57 is the primary button today).
- **Also:** "Try a demonstration" as the secondary action.
- **No sidebar duplication:** the "My automations" button (home.py:66-69) is removed or becomes a *summary* ("You have N automations — view all"), not a navigation clone.
- **Empty state:** "You haven't run any automations yet. Try the demonstration to get started." (home.py:78-83 — keep this wording).

### My automations
- **Shows:** the saved workflow list (ui/pages/my_automations.py:258), selected automation's steps in the details area.
- **Single primary action:** "Run" (with confirmation, my_automations.py:179-198). "Open" and "Preview" are secondary; "New automation" is the creation entry point.
- **Empty state:** "No saved automations yet. Create one from Home." (my_automations.py:95 — keep).

### Activity
- **Shows:** run list from persisted history (ui/pages/activity.py:57-84) and per-step results for the selected run (activity.py:64-77).
- **Single primary action:** selecting a run to inspect it (read-only page; no mutating action).
- **Empty state:** "Select a run to see details." plus, when there are no runs yet: "No runs yet — try the demonstration from Home." (ASSUMPTION: exact wording to be confirmed).

### Create automation (a flow, not a sidebar page)
- **Shows:** the task description field, the draft step list with add/move/remove, the save action, and the "Record what I do" entry point (J2/J5). Recording lives **here**, not in Settings.
- **Single primary action:** Save automation.
- **Empty state:** a placeholder example in the description field (today: "Example: ..." — ui/pages/create_automation.py, placeholder text) and one pre-seeded empty step list with a hint.

### Settings (configuration only)
- **Shows:** (1) the authorized folder — where Once may act (ui/pages/settings.py:70-91); (2) verifier/acceptance-checker configuration — the old window's VerifierConfigDialog (ui/verifier_dialog.py:65); (3) a coding-agent connection **only if it actually works** — today it does not, so it is absent.
- **Single primary action:** "Choose folder" (settings.py:87-91).
- **Removed from Settings (they do not work today):** the Recording group (settings.py:93-127 — the shell's handlers are `pass`, ui/shell.py:279-283; recording moves to the create flow per J5), the Gemini group (settings.py:129-145 — Connect/Disconnect only print a status sentence; there is no integration), the Coding agent buttons (settings.py:147-165 — both only print "there are none yet"), and the empty Advanced group (settings.py:167-180 — label only, no controls).
- **Empty state:** "No folder selected." (settings.py:78) — keep.

## 4. The honest-controls rule

1. **No visible, enabled control may be unwired.** If clicking it does nothing real, it does not ship. (Tested: every visible, enabled QPushButton must have a connected handler — B3 test.)
2. **An unfinished feature is hidden**, not disabled-with-explanation, not decorated.
3. **Never show jargon** such as "placeholder", "stub" or "not implemented" to the user. Explain unfinished things in plain language only if the user must be told ("Not available yet" + what to do instead), never in the UI chrome.
4. Signals that connect to `pass` handlers (ui/shell.py:273-283 today) violate this rule; either the handler does real work or the control is removed.

## 5. Layout rules (design foundation for B3)

- **Sidebar:** full height of the central area, flush to the left edge, no floating card, no rounded outer margin, no stray labels. Exactly the four nav items plus one brand mark; footer text is a single fixed label.
- **Page content:** top-aligned inside a scroll area, under the page title, left-aligned consistently, with a **maximum content width of ~960 px** centered in the remaining space (or left-aligned with a fixed margin — pick one and apply it to every page; ASSUMPTION: centered-with-max-width, it matches the existing `AlignHCenter` usage in home.py:37, activity.py:35).
- **Spacing scale (tokens):** 4, 8, 12, 16, 24, 32 px only; defined once in `ui/styles/` as Python constants and referenced everywhere — no ad-hoc margins in pages.
- **Type scale (tokens):** defined once in `ui/styles/` (e.g. title 26, subtitle 15, body 14, caption 13 — today these are scattered as inline `setStyleSheet` strings, e.g. home.py:44, activity.py:44, settings.py:84).
- **Color:** one accent color (the existing #2563EB), neutral grays for text/surfaces; contrast of text against its background ≥ 4.5:1 (e.g. #6b6b6b on #FFFFFF is ~4.6:1 — borderline; #525252 on white is ~7.4:1 — safe. Verify each pair when tokens land).
- **Font:** system font stack, Segoe UI first (`font-family: "Segoe UI", system-ui, sans-serif`). The current sidebar button hard-codes 'Inter' first (ui/shell.py:71) and Home hard-codes `QFont("Inter", ...)` (home.py:43) — Inter is not guaranteed on Windows; Segoe UI must come first.
- **Keyboard:** every interactive control shows a visible focus ring; tab order follows reading order (top-to-bottom, left-to-right within a page); the default button is reachable first.

## 6. Defect list (user's fact 7) and the rule that prevents each

| # | Observed in the maximized 1920x1080 window | Preventing rule |
|---|---|---|
| 1 | Sidebar is a small floating card, ~1/3 of the window height | Sidebar is full-height, flush left, part of the window frame — not a card (section 5) |
| 2 | Stray "Once" and "..." in the sidebar footer | Sidebar contains exactly four nav items + one brand label; footer is one fixed string; no ellipsis artifacts (section 5) |
| 3 | Page content vertically centered with ~400 px of empty space above | Content is top-aligned in a scroll area under the page title (section 5) |
| 4 | "Recent activity" is a small left-aligned block while everything else is centered | One alignment per page: every block uses the same left edge (section 5) |
| 5 | "My automations" appears in the sidebar **and** as a Home button | Home does not duplicate sidebar entries; at most a summary link with a count (section 3) |
| 6 | Most buttons do nothing | Honest-controls rule: no visible, enabled control without a real handler (section 4) |
| 7 | Automations cannot be created | Create flow is journey J2; until it exists, the entry point is hidden, not fake (sections 3-4) |
| 8 | Recording sits under Settings | Recording lives inside the create flow (J5); Settings is configuration only (section 3) |

## 7. Out of brief

File management/undo, multi-tab browsing, downloads/uploads, installer polish and packaging rebuilds are out of scope until after the MVP (working agreement, hard rule 10). Architecture rules are unchanged: `ui/` never mutates the file system — pages call controller services only (AGENTS.md S8).
