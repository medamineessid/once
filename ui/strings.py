"""Centralised UI strings (P2 prompt rule: one module, English, sentence case).

Editor and shell pages must not hard-code their own sentence strings; this is
the single place that a later French translation touches (QUESTION Q1).
"""

from __future__ import annotations

# --- Shell and pages --------------------------------------------------------
APP_TITLE = "Once"
SIDEBAR_HOME = "Home"
SIDEBAR_AUTOMATIONS = "My automations"
SIDEBAR_ACTIVITY = "Activity"
SIDEBAR_SETTINGS = "Settings"

FOOTER_READY = "Ready"
FOOTER_RUNNING = "Running…"
FOOTER_ATTENTION = "Needs attention"

# --- Demonstration banners ----------------------------------------------------
DEMO_FINISHED_TITLE = "Demonstration finished"
DEMO_FINISHED_BODY = "The demonstration ran successfully. Nothing on your computer was changed."
DEMO_STOPPED_TITLE = "Demonstration stopped"
DEMO_FAILED_TITLE = "Demonstration failed"

# --- Home -------------------------------------------------------------------
HOME_TITLE = "Welcome to Once"
HOME_SUBTITLE = "Your personal assistant for automating repetitive computer tasks."
HOME_CREATE_ACTION = "Create an automation"
HOME_CARD_DEMO_TITLE = "Try a demonstration"
HOME_CARD_DEMO_BODY = (
    "Watch a small, safe automation run on this PC. Nothing is changed on your computer."
)
HOME_CARD_CREATE_TITLE = "Create from scratch"
HOME_CARD_CREATE_BODY = "Build an automation from connected steps on a visual canvas."
HOME_CARD_RECORD_TITLE = "Record a task"
HOME_CARD_RECORD_BODY = (
    "Do the task once while Once records your actions, then review and edit the draft."
)
HOME_RECENT_LIST_TITLE = "Recent activity"
HOME_RECENT_EMPTY = "You haven't run any automations yet. Try the demonstration to get started."
HOME_RUN_SUCCEEDED = "Succeeded"
HOME_RUN_FAILED = "Failed"
HOME_RUN_CANCELLED = "Cancelled"
HOME_CARD_DEMO_ACTION = "Run demonstration"

# --- My automations ----------------------------------------------------------
MY_TITLE = "My automations"
MY_SUBTITLE = "Open, preview and run the automations you have saved."
MY_NEW_ACTION = "New automation"
MY_EMPTY = "No saved automations yet. Create one from Home."
MY_DETAILS_EMPTY = "Select an automation to see its details."
MY_RUN = "Run"
MY_RUN_CONFIRM = "Confirm run?"
MY_RUN_RUNNING = "Running…"
MY_OPEN = "Open"
MY_PREVIEW = "Preview"
MY_LAST_RUN_PREFIX = "Last run"
MY_NOT_RUN = "Not run yet"
MY_BANNER_ERROR_TITLE = "Automation problem"
MY_RUN_HINT_TITLE = "Pick an automation first"
MY_RUN_HINT_BODY = "Select an automation in the list, then press Run."

# --- Activity ----------------------------------------------------------------
ACTIVITY_TITLE = "Activity"
ACTIVITY_SUBTITLE = "A readable history of the runs you started."
ACTIVITY_EMPTY_LIST = "No runs yet — try the demonstration from Home."
ACTIVITY_DETAILS_EMPTY = "Select a run to see details."

# --- Settings ---------------------------------------------------------------
SETTINGS_TITLE = "Settings"
SETTINGS_SUBTITLE = "Configure how Once works for you."
SETTINGS_CASES_LABEL = "Acceptance cases file"
SETTINGS_ARGV_LABEL = "Checker command line"
SETTINGS_TIMEOUT_LABEL = "Timeout per case (seconds)"
SETTINGS_WORKTREE_LABEL = "Worktree directory for reruns"
SETTINGS_SAVE_CONFIG = "Save configuration"
SETTINGS_CLOSE_PANEL = "Close"
SETTINGS_CONFIG_SAVED_TITLE = "Checker configuration saved"
SETTINGS_CONFIG_SAVED_BODY = "The acceptance checker is configured in your data folder."
SETTINGS_NO_DATA_DIR_TITLE = "Checker not configured"
SETTINGS_NO_DATA_DIR_BODY = (
    "Once could not find its data folder on this machine, so the checker"
    " cannot be configured here yet."
)

# --- Banners (what happened / what to do next) -------------------------------
BANNER_INFO = "Info"
BANNER_SUCCESS = "Success"
BANNER_WARNING = "Warning"
BANNER_ERROR = "Error"

# --- Create automation -------------------------------------------------------
CREATE_TITLE = "Create automation"
CREATE_QUESTION = "What would you like Once to do?"
CREATE_PLACEHOLDER = "Example: Open my invoices folder and identify PDF files."
CREATE_HINT = "Once will prepare a plan for your review before any action is executed."
CREATE_BUTTON = "Create automation"
CREATE_NOT_AVAILABLE_TITLE = "Not available yet"
CREATE_NOT_AVAILABLE_BODY = (
    "Once cannot turn a typed description into an automation yet."
    " Nothing was created. You can open a saved automation on My automations;"
    " building automations arrives with the visual editor."
)
RUN_CANCELLED_MESSAGE = "The run was cancelled before it finished."
