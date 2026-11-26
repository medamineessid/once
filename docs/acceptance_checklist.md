# Manual acceptance checklist (first-time user, about 20 minutes)

Status: current
Last verified: 2026-11-26 · `main f2e6ca3`
Owner: lane C (proof and delivery)

What a person does once before calling a release good. Automated tests cover the
same pages offscreen; this is the pass that catches what a test cannot — a
control that is there, wired and unreadable. Tick what you actually saw and note
anything unclear in `docs/evidence/TEMPLATE.md`.

## 1. First run (3 minutes)

- [ ] `python app.py` opens the shell on **Home**; the navy rail shows Home,
      My automations, Activity, Settings.
- [ ] Nothing has to be configured before the app is usable.
- [ ] **Start with a recording** and **Build an automation** are both visible and
      do not overlap at 100% scaling.
- [ ] Close and reopen the app: it opens on the same page and keeps its data.

## 2. Home (3 minutes)

- [ ] The hero lines are stacked and left-aligned, with no clipped descender.
- [ ] The lemon **Record** circle and the outlined **Build** button are on one
      row, aligned to each other.
- [ ] The saved-automation count is a real number, not a placeholder.
- [ ] Recent activity lists real runs; a failed run shows its first plain reason
      ("Could not find the 'Save' button in Notepad."), not an error code.

## 3. My automations (4 minutes)

- [ ] Every saved automation fits inside the list; nothing is cut off and a
      scrollbar appears only when it is needed.
- [ ] **Preview** and **Clear unnamed drafts** sit in their own row **above** the
      list and never cover a row.
- [ ] **Run** on a desktop automation opens the approval panel; the panel shows
      all of its text and both buttons (**Approve for this run** and **Do not
      run**) without scrolling inside a clipped box.
- [ ] A row that is waiting for approval still reads **Run**, not "Running…".
- [ ] **Delete** opens one dialog: red filled **Delete**, outlined **Cancel**, and
      Cancel is the default when you press Enter.
- [ ] With the keyboard: Tab reaches both dialog buttons and you can see which
      one has focus.

## 4. Activity (3 minutes)

- [ ] Every run has a name, status chip, duration and timestamp.
- [ ] **Run again** repeats the run through the approval gate; **Delete** removes
      the row after confirming.
- [ ] An all-observation run reads **Observation only — nothing was performed**,
      not Succeeded.
- [ ] An in-progress run refuses deletion with an explanation.

## 5. Settings (3 minutes)

- [ ] Sections are cards, not nested boxes; nothing is clipped at 100% or 150%.
- [ ] Hover and press on **Configure checker…** stay inside the button; no border
      escapes the rectangle and no button changes size.
- [ ] Switching a setting says what changed and survives a restart.

## 6. Rail and dialogs (2 minutes)

- [ ] Every rail row has the same width; the active pill and the hover state line
      up with the row edges.
- [ ] Keyboard focus on a rail row is an outline only — it never looks like a
      second active pill.
- [ ] A click on a rail row does not draw the keyboard outline.

## 7. Stop and restart (2 minutes)

- [ ] Start a run and press the footer **Stop**: the run ends **Cancelled**.
- [ ] `Ctrl+Alt+Q` during another run does the same, and does nothing outside a
      run.
- [ ] `%LOCALAPPDATA%\Once` holds `once.db`, `workflows\`, `recordings\` and
      `logs\once.log`; restarting keeps all of it.

## Known manual-only items

- The startup-failure dialog (corrupt data folder or database) is shown by the
  packaged exe; clicking OK in the real dialog has only been done by a person.
- The real-desktop replay of a recorded task is `docs/REAL_DESKTOP_CHECKLIST.md`,
  not this list.
