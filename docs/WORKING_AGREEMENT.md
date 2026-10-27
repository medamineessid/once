# WORKING AGREEMENT

## Hard rules

1. Never change the semantics of the approval gate, replay policy, workflow validators or safety invariants. Calling them and adding tests for them is allowed.
2. No new or removed dependencies. No deleting, skipping or weakening tests.
3. Architecture tests stay green: engine/ never imports PySide6 or ui/; ui/ never mutates the file system.
4. Tests use only pytest tmp_path, never real user folders, and never open a blocking modal dialog (stub or avoid QMessageBox and QDialog.exec). Qt tests run with QT_QPA_PLATFORM=offscreen.
5. One branch per slice, slice/<short-name>, created from up-to-date main. Small commits with real line breaks (several -m flags or -F file, never literal \n). Merge to main only with git merge --ff-only after every check passes. You may push slice branches and main. Never force-push, rewrite published history, delete branches or worktrees, or run git worktree prune or git clean. Do not touch the other worktrees (once-desktop, /tmp ones).
6. Run git branch --show-current before the first edit of every task and after every merge. If it is not the intended branch, stop and fix that first.
7. docs/ai_engineering_log.md is append-only; after every commit that touches it, git diff --numstat origin/main...HEAD -- docs/ai_engineering_log.md must show 0 deletions.
8. No bare "except:" and no "except Exception: pass".
9. Hard-crash orphan Chrome processes are a documented known limitation; do not work on them. The unreachable selector block at the end of _validate_wait_page_target is harmless; leave it.
10. Out of scope until after the MVP: file management and undo, multi-tab browsing, downloads and uploads, installer polish, packaging rebuilds.

## Evidence rules

- Every report contains raw pasted terminal output for each check: git branch --show-current, git status --short, git log --oneline -5, the full pytest summary lines, ruff check, ruff format --check, and the log numstat line. Never paste a number you did not just obtain.
- If a claim cannot be tied to pasted output, write "I cannot confirm this".
- Do not write "works", "validated" or "end to end" unless you ran the real entry point (app.py or app.py --shell) and pasted the result.
- Quote file:line for every claim about code.
- Screenshots are evidence only if produced through the real app.py code path; say which path, and say "captured, not reviewed".

## Stop protocol (BLOCKED)

Stop when: a change would alter approval, policy or validator behavior; AGENTS.md conflicts with this agreement; a dependency would need to change; a test would need to be removed, skipped or weakened; a file other than ones you created in the same slice would need deleting; a test would touch real user folders; the same failure persists after 3 genuine attempts; a check that passed before fails and you cannot find the cause; or you are unsure whether an action is destructive. Then write docs/BLOCKED.md (question, options, your recommendation and why, evidence), commit and push the current branch, mark the ledger item BLOCKED, and end with a message starting "BLOCKED:" of at most five lines. Do not make the decision yourself.
