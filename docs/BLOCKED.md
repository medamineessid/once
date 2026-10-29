# BLOCKED — B3: removing unwired Settings controls vs. "no test may be removed"

- Date: 2026-10-27
- Branch: slice/layout-foundation (PHASE A already merged and pushed to main at 1685475)
- Ledger item: B3 — status BLOCKED
- Written by: agent, per the stop protocol in the session working agreement

## Question

B3 says: "remove every unwired control". The UX brief (docs/UX_BRIEF.md §3) says the
Settings page must drop its non-functional groups — Recording, Gemini integration,
Coding agent, Advanced — because none of them do real work:

- Recording buttons emit `recording_started`/`recording_stopped`, which the shell
  connects to `pass` handlers (ui/shell.py:279-283) — clicking them shows nothing.
- "Connect/Disconnect Gemini" only prints a status sentence (ui/pages/settings.py:195-206);
  there is no Gemini integration wired to it.
- "Open proposals"/"Start review" only print "there are none yet"
  (ui/pages/settings.py:207-218).
- The Advanced group has a label and no controls (ui/pages/settings.py:165-180).

Removing those controls makes three existing tests lose their subject:

1. `tests/test_shell.py:106` `test_settings_page_opens_from_sidebar` asserts the
   four placeholder groups are visible (asserts at 112-115).
2. `tests/test_shell.py:118` `test_settings_page_shows_placeholder_integration_messages`
   asserts the fake Gemini/coding-agent/recording status messages (calls at 122-133).
3. `tests/test_shell.py:136` `test_settings_page_has_recording_controls` asserts the
   three recording buttons exist and are enabled (asserts at 138-143).

The working agreement forbids me from deleting, skipping or weakening tests, and its
stop protocol says a change that would require that must be referred to you rather
than decided by me.

## Options

**A) Remove the four non-functional groups and rewrite the three tests to assert the
new honest state** (e.g. "Settings shows only the authorized-folder section"; "no
button in Settings emits a dead signal"). The three tests currently assert the
presence of placeholder UI — not safety behaviour — so the rewrite keeps Settings
covered while matching the brief.

**B) Keep the groups, leave their behaviour as-is.** All three tests keep passing,
but Settings keeps visible buttons that do nothing real, which violates the
honest-controls rule (B3, UX brief §4) and the fact-7 defect list.

**C) Keep the groups but reword their messages to plain-language "not available yet".**
Honest, but still shows non-functional controls (UX brief §4 says unfinished features
are hidden), and test 2 asserts the current message prefixes, so it breaks anyway.

## Recommendation

**Option A.** Why: the three tests encode the placeholder state that the UX brief you
approved for this phase explicitly removes; rewriting them preserves test coverage of
the Settings page while deleting tests of fake features. No safety invariant (S1-S12),
no approval/policy/validator test, and no engine test is touched — the collision is
confined to `tests/test_shell.py`, which tests shell wiring only.

## Evidence

- `grep -rn "_recordings_group|_gemini_group|_coding_agent_group|_advanced_group|_start_recording|_connect_gemini|_disconnect_gemini|_open_coding_agent|_delete_recording|_on_recording|_on_verifier_configured|_show_run_details" tests/` → matches only in tests/test_shell.py lines 112-115, 122-132, 138-143 (plus .pyc cache).
- `ui/pages/settings.py:104,129,147,165` create the four groups;
  `ui/pages/settings.py:195-218` are the status-sentence handlers;
  `ui/shell.py:273-283` are the `pass` handlers.
- No test references the Home "My automations" button, the sidebar footer labels, or the
  shell stub handlers — those parts of B3 have no test collision and can proceed once
  this decision is made.

RESOLVED: Option A (user-approved) on 2026-10-28 — the agent (previous session prompt) acted on it and recorded the work in docs/ai_engineering_log.md (entry 2026-10-28, B3); the three replaced tests are named in the 2026-10-27 entry above.

## What I did instead of deciding

Committed this file and the completed B1/B2 work (docs/UX_BRIEF.md, journey queue in
docs/PROGRESS.md) on slice/layout-foundation and pushed the branch. No Settings or
layout code was changed yet.
