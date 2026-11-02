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
HOME_TITLE = "What do you want to automate?"
HOME_SUBTITLE = "Choose how to show Once the task. You can build the steps yourself or record them."
HOME_CARD_CREATE_TITLE = "Build it yourself"
HOME_CARD_CREATE_BODY = "Add clear steps on a visual canvas, then preview and save the automation."
HOME_CARD_CREATE_ACTION = "Build an automation"
HOME_CARD_RECORD_TITLE = "Record a task"
HOME_CARD_RECORD_BODY = (
    "Show Once the task once. Your recording stays on this PC and needs review before it can run."
)
HOME_CARD_RECORD_ACTION = "Start with a recording"
HOME_RECENT_LIST_TITLE = "Your recent runs"
HOME_RECENT_EMPTY = "No runs yet. Save an automation, then run it from My automations."
RECORDING_PAGE_TITLE = "Record a task"
RECORDING_PAGE_SUBTITLE = (
    "Show Once the task once. Recording stays on this PC and becomes a draft for review."
)
RECORDING_BACK = "Back to choices"
RECORDING_SAVED_NEXT = "Next: review the recording before turning it into steps."
HOME_RUN_SUCCEEDED = "Succeeded"
HOME_RUN_FAILED = "Failed"
HOME_RUN_CANCELLED = "Cancelled"

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
MY_SAVED_PREFIX = "Saved"
MY_UNREADABLE_TITLE = "Files need attention"
MY_UNREADABLE_BODY = (
    "Some files in this folder could not be read as automations. "
    "They are listed by file name and cannot be opened."
)

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
CREATE_RECORD_TITLE = "Record a task"
CREATE_RECORD_BODY = "Show Once what to do. Recording saves a redacted local event log for review."
CREATE_RECORD_START = "Start recording"
CREATE_RECORD_STOP = "Stop recording"
CREATE_RECORDING_ACTIVE = "Recording is active. Perform the task, then choose Stop recording."
CREATE_RECORDING_SAVED = (
    "Recording saved locally. It still needs review before it can become runnable steps."
)
RUN_CANCELLED_MESSAGE = "The run was cancelled before it finished."

# --- Editor -----------------------------------------------------------------
EDITOR_RENAME_ERROR_TITLE = "Name not applied"
EDITOR_RENAME_EMPTY_MESSAGE = "An automation needs a name. The previous name was kept."
EDITOR_EDIT_ERROR_TITLE = "Changes not applied"
EDITOR_UNSAVED_TITLE = "Unsaved changes"
EDITOR_UNSAVED_BODY = "Save your changes, discard them, or stay in the editor."
EDITOR_SAVE = "Save"
EDITOR_DISCARD = "Discard"
EDITOR_STAY = "Stay"
EDITOR_RUN = "Run automation"
EDITOR_RUN_SAVE_FIRST_TITLE = "Save before running"
EDITOR_RUN_SAVE_FIRST_BODY = "Save this automation first. Once saved, run it from My automations."
EDITOR_RUN_STARTED = "Automation is running."
EDITOR_RUN_SUCCEEDED = "Automation finished successfully."
EDITOR_RUN_FAILED = "Automation could not finish."
EDITOR_CANCEL_RUN = "Cancel run"
EDITOR_RUN_CANCELLED = "Automation was cancelled."
EDITOR_INSPECTOR_STEPS = "step"
EDITOR_INSPECTOR_NO_TARGET = "no target"
EDITOR_INSPECTOR_TARGET_UNREADABLE = "target the editor cannot show"
EDITOR_INSPECTOR_KIND_READ_ONLY = "Read-only"
EDITOR_INSPECTOR_KIND_MUTATING = "Changes your computer"
EDITOR_INSPECTOR_MUTATING_NOTE = (
    "This step changes your computer. Once asks for approval before it can run."
)

# --- Review -----------------------------------------------------------------
REVIEW_EDIT = "Edit automation"
REVIEW_APPROVE = "Approve draft and edit"
REVIEW_TITLE_DRAFT = "Review recorded draft"
REVIEW_TITLE_SAVED = "Automation details"
