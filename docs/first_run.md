# First run: a walkthrough, with the places that confuse people

Status: current
Last verified: 2026-11-26 · `main f2e6ca3`
Owner: lane B (app experience)


This is the shortest honest path through Once for someone who has never seen it,
written by walking it. Each "where people get stuck" note is a real observation
from driving the running app, not a guess.

## 1. Start the app

```
.venv\Scripts\python.exe app.py
```

The window opens on **Home**. The navy rail on the left is the whole navigation:
Home, My automations, Activity, Settings.

**Where people get stuck:** the big lemon circle says **Record** and the outlined
button next to it says **Build**. They are two different ways to make the same
thing, and nothing on screen says which to pick. Rule of thumb: Record if you can
perform the task once, Build if you already know the steps.

## 2. Make the first automation

Recording:

1. Click the lemon **Record** circle.
2. Perform the task once, slowly. Type instead of pasting where you can; text is
   captured per control.
3. Press **Stop recording** when finished.
4. Once shows the **Review recorded draft** page. Read the steps. Every step is
   labelled either as something Once can replay or as an observation it will
   only report.

**Where people get stuck:** a recording that ends with a document that has
unsaved changes produces a *close* step that hits the application's own "save
your changes?" prompt. Once answers that prompt with **don't save** — the run
never writes a file you did not ask for — but if you wanted the file saved, add
a save step (Ctrl+S is an allowlisted shortcut) before closing.

## 3. Run it

1. Open **My automations**.
2. Each row has its own **Run**, **Open**, **Delete**. Press Run.
3. If the automation touches the desktop, a panel lists exactly which mutating
   steps will happen and which applications will be launched (by path and
   SHA-256). Nothing runs until you press **Approve**.

**Where people get stuck:** the panel is the run gate, not a message. Pressing
Run twice only re-arms it. And an automation whose steps are only observations
finishes as **Observation only — nothing was performed**; that is not a failure,
and the Activity page says so in those words.

## 4. Watch it, and stop it

While a run is live, the footer at the bottom of the rail changes to **Running…**
and a **Stop** button appears next to it. **Ctrl+Alt+Q** works anywhere, even
when Once is behind the application it is driving. Cancelling is cooperative: the
current step finishes, then no further step starts, and the run ends **Cancelled**.

**Where people get stuck:** Ctrl+Alt+Q is a global hotkey, so it is active only
while a run is live. Outside a run it does nothing, which is the intended
behaviour.

## 5. Read what happened

**Activity** lists every run with its real name, status, duration, and — when it
failed — the first plain-language reason ("Could not find the 'Save' button in
Notepad"). Each row can be run again or deleted.

**Where people get stuck:** "Run again" needs the automation file. If the
automation was deleted, the row stays in history but the repeat action says the
automation is gone instead of pretending.

## 6. Values you do not want to bake in

Write `{name}` (or any short lowercase name) in a step's message, target, or the
automation title. When you press Run, Once asks for the value, uses it for that
run only, then asks again next time. Nothing about the value is saved.

## 7. What Once will not do

- It will not delete your files permanently, overwrite an existing file, or merge
  or push agent changes.
- It will not run arbitrary shell commands or AI-written code.
- It will not use the network unless you configured an integration and consented.
- It will not click anything you did not approve for that specific run.

If a task needs one of those, Once is the wrong tool and should say so rather
than improvise.
