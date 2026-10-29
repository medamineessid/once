"""Once design system — consistent typography, spacing, and palette.

The tokens below are the single source of truth for layout and text sizes:
they are interpolated into the Qt stylesheet through ``string.Template`` so
the stylesheet cannot drift from them. Pages import the same constants for
margins instead of hard-coding pixel values.
"""

from __future__ import annotations

from string import Template

from PySide6.QtWidgets import QApplication

# --- Spacing tokens (the only allowed layout values) -----------------------
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24
SPACING_XXL = 32
SPACING_VALUES = frozenset(
    {SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL, SPACING_XXL}
)

# --- Type tokens (single source for text sizes) ----------------------------
TYPE_HOME_TITLE_PX = 32
TYPE_TITLE_PX = 26
TYPE_QUESTION_PX = 18
TYPE_HOME_SUBTITLE_PX = 16
TYPE_SUBTITLE_PX = 15
TYPE_BODY_PX = 14
TYPE_CAPTION_PX = 13
TYPE_FOOTER_PX = 11

FONT_STACK = '"Segoe UI", "SF Pro Display", system-ui, sans-serif'

# --- Color tokens (single source for both stylesheet and painted widgets) ----
BG_APP = "#F5F6F8"
BG_CANVAS = "#FBFCFE"
DOT_GRID = "#DDE3EC"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F9FAFB"
BORDER = "#E3E7EE"
BORDER_STRONG = "#D1D5DB"
ACCENT = "#2563EB"
ACCENT_TEXT = "#1D4ED8"
ACCENT_SOFT = "#EEF2FF"
PRIMARY_BTN = "#111827"
TEXT_STRONG = "#1D2733"
TEXT_BODY = "#525A66"
TEXT_FAINT = "#6B7280"
STATUS_OK = "#15803D"
STATUS_ERROR = "#B91C1C"
STATUS_WARNING = "#92400E"
TINT_ACTION = "#FDF0E2"
TINT_VERIFY = "#EAF6EE"
TINT_PROGRESS = "#EAF3F8"
TINT_STOP = "#FDECEC"
TINT_START = "#FCF6E3"
TINT_FINISH = "#F2F4F7"
TINT_NOTE = "#FBF7DC"

#: Text/surface pairs used by pages; the contrast test walks this list.
CONTRAST_PAIRS = (
    ("body on card", TEXT_BODY, "#FFFFFF"),
    ("strong on card", TEXT_STRONG, "#FFFFFF"),
    ("faint on card", TEXT_FAINT, "#FFFFFF"),
    ("body on app", TEXT_BODY, BG_APP),
    ("body on accent tint", TEXT_BODY, ACCENT_SOFT),
    ("accent text on card", ACCENT_TEXT, "#FFFFFF"),
    ("accent text on app", ACCENT_TEXT, BG_APP),
    ("button text on primary", "#FFFFFF", PRIMARY_BTN),
    ("status ok text", STATUS_OK, "#FFFFFF"),
    ("status error text", STATUS_ERROR, "#FFFFFF"),
    ("status warning text", STATUS_WARNING, "#FFFFFF"),
    ("strong on action tint", TEXT_STRONG, TINT_ACTION),
    ("strong on verify tint", TEXT_STRONG, TINT_VERIFY),
    ("strong on progress tint", TEXT_STRONG, TINT_PROGRESS),
    ("strong on stop tint", TEXT_STRONG, TINT_STOP),
    ("strong on start tint", TEXT_STRONG, TINT_START),
    ("strong on finish tint", TEXT_STRONG, TINT_FINISH),
    ("strong on note tint", TEXT_STRONG, TINT_NOTE),
)


def apply_theme(window):
    """Install the Once design system on the whole application."""
    app = QApplication.instance() or window
    _set_palette(app)
    _set_stylesheet(app)


def _set_palette(app):
    from PySide6.QtGui import QColor, QPalette

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#FFFFFF"))
    palette.setColor(QPalette.WindowText, QColor("#1D1D1D"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#F5F5F5"))
    palette.setColor(QPalette.Text, QColor("#1D1D1D"))
    palette.setColor(QPalette.Button, QColor("#E8E8E8"))
    palette.setColor(QPalette.ButtonText, QColor("#1D1D1D"))
    palette.setColor(QPalette.Highlight, QColor("#1D1D1D"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.Link, QColor("#2563EB"))
    palette.setColor(QPalette.LinkVisited, QColor("#7C3AED"))
    app.setPalette(palette)


def _set_stylesheet(app):
    substitutions = {
        "ACCENT": ACCENT,
        "ACCENT_TEXT": ACCENT_TEXT,
        "ACCENT_SOFT": ACCENT_SOFT,
        "BG_APP": BG_APP,
        "SURFACE": SURFACE,
        "SURFACE_ALT": SURFACE_ALT,
        "BORDER": BORDER,
        "BORDER_STRONG": BORDER_STRONG,
        "PRIMARY_BTN": PRIMARY_BTN,
        "TEXT_STRONG": TEXT_STRONG,
        "TEXT_BODY": TEXT_BODY,
        "TEXT_FAINT": TEXT_FAINT,
        "STATUS_OK": STATUS_OK,
        "STATUS_ERROR": STATUS_ERROR,
        "STATUS_WARNING": STATUS_WARNING,
        "TINT_ACTION": TINT_ACTION,
        "TINT_VERIFY": TINT_VERIFY,
        "TINT_PROGRESS": TINT_PROGRESS,
        "TINT_STOP": TINT_STOP,
        "TINT_START": TINT_START,
        "TINT_FINISH": TINT_FINISH,
        "TINT_NOTE": TINT_NOTE,
        "FONT_STACK": FONT_STACK,
        "TYPE_HOME_TITLE_PX": TYPE_HOME_TITLE_PX,
        "TYPE_TITLE_PX": TYPE_TITLE_PX,
        "TYPE_QUESTION_PX": TYPE_QUESTION_PX,
        "TYPE_HOME_SUBTITLE_PX": TYPE_HOME_SUBTITLE_PX,
        "TYPE_SUBTITLE_PX": TYPE_SUBTITLE_PX,
        "TYPE_BODY_PX": TYPE_BODY_PX,
        "TYPE_CAPTION_PX": TYPE_CAPTION_PX,
        "TYPE_FOOTER_PX": TYPE_FOOTER_PX,
    }
    app.setStyleSheet(_STYLESHEET_TEMPLATE.substitute(substitutions))


_STYLESHEET_TEMPLATE = Template("""
    QMainWindow {
        background: #F3F3F3;
    }
    QWidget#sidePanel {
        background: #FFFFFF;
        border-right: 1px solid #E5E5E5;
    }
    QWidget#sidePanel:focus {
        border-right: 1px solid $ACCENT;
    }
    QWidget#mainPanel {
        background: #F3F3F3;
    }
    QToolBar#sidebar {
        padding: 0px;
    }
    QLabel#onceLogo {
        font-size: 28px;
        font-weight: 700;
        color: #1D1D1D;
        padding: 4px 0 12px 0;
        font-family: $FONT_STACK;
    }
    QLabel#sidebarFooter {
        font-size: ${TYPE_FOOTER_PX}px;
        color: #9A9A9A;
        padding: 12px 6px 4px 6px;
        font-family: $FONT_STACK;
    }
    QToolButton#sidebarHomeButton,
    QToolButton#sidebarAutomationsButton,
    QToolButton#sidebarActivityButton,
    QToolButton#sidebarSettingsButton,
    QToolButton#sidebarCreateButton {
        background: transparent;
        border: none;
        border-left: 3px solid transparent;
        color: #4A4A4A;
        font-size: ${TYPE_BODY_PX}px;
        padding: 10px 12px;
        border-radius: 0 8px 8px 0;
        font-family: $FONT_STACK;
        min-height: 10px;
    }
    QToolButton#sidebarHomeButton:hover,
    QToolButton#sidebarAutomationsButton:hover,
    QToolButton#sidebarActivityButton:hover,
    QToolButton#sidebarSettingsButton:hover,
    QToolButton#sidebarCreateButton:hover {
        background: #F3F4F6;
        color: #1D1D1D;
    }
    QToolButton#sidebarHomeButton:focus,
    QToolButton#sidebarAutomationsButton:focus,
    QToolButton#sidebarActivityButton:focus,
    QToolButton#sidebarSettingsButton:focus,
    QToolButton#sidebarCreateButton:focus {
        font-weight: 600;
    }
    QToolButton#sidebarHomeButton:checked,
    QToolButton#sidebarAutomationsButton:checked,
    QToolButton#sidebarActivityButton:checked,
    QToolButton#sidebarSettingsButton:checked,
    QToolButton#sidebarCreateButton:checked {
        background: #FFFFFF;
        border-left: 3px solid $ACCENT;
        color: #1D1D1D;
        font-weight: 500;
    }
    QLabel#homeTitle {
        font-size: ${TYPE_HOME_TITLE_PX}px;
        font-weight: 700;
        color: #1D1D1D;
    }
    QLabel#homeSubtitle {
        font-size: ${TYPE_HOME_SUBTITLE_PX}px;
        color: #525252;
        margin-top: 8px;
    }
    QLabel#pageTitle {
        font-size: ${TYPE_TITLE_PX}px;
        font-weight: 600;
        color: #1D1D1D;
    }
    QLabel#pageSubtitle {
        font-size: ${TYPE_SUBTITLE_PX}px;
        color: #525252;
        margin-top: 4px;
    }
    QLabel#questionLabel {
        font-size: ${TYPE_QUESTION_PX}px;
        font-weight: 500;
        color: #3A3A3A;
    }
    QLabel#hintLabel {
        font-size: ${TYPE_CAPTION_PX}px;
        color: #6B6B6B;
    }
    QLabel#activityLabel {
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 500;
        color: #3A3A3A;
    }
    QLabel#activityEmpty {
        font-size: ${TYPE_CAPTION_PX}px;
        color: #6B6B6B;
    }
    QLabel#activityItem {
        font-size: ${TYPE_CAPTION_PX}px;
        color: #2E7D32;
    }
    QLabel#activityDetailsLabel {
        font-size: ${TYPE_CAPTION_PX}px;
        color: #6B6B6B;
    }
    QLabel#goalLabel {
        font-size: ${TYPE_SUBTITLE_PX}px;
        color: #525252;
        margin-top: 4px;
    }
    QLabel#automationDetailsLabel {
        font-size: ${TYPE_CAPTION_PX}px;
        color: #6B6B6B;
        border-top: 1px solid #E5E7EB;
        padding-top: 8px;
    }
    QLabel#authorizedLabel,
    QLabel#verifierIntroLabel {
        font-size: ${TYPE_CAPTION_PX}px;
        color: #525252;
    }
    QFrame#actionsPanel {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 8px;
        border: 1px solid #ECECEC;
    }
    QFrame#activitiesList {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 6px;
        border: 1px solid #ECECEC;
    }
    QFrame#workflowList {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 6px;
        border: 1px solid #ECECEC;
    }
    QFrame#recordingList {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 6px;
        border: 1px solid #ECECEC;
    }
    QFrame#stepsList {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 6px;
        border: 1px solid #ECECEC;
    }
    QFrame#detailsContainer {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 8px;
        border: 1px solid #ECECEC;
    }
    QFrame#actionsContainer {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 6px;
        border: 1px solid #ECECEC;
    }
    QFrame#settingsWidget {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 8px;
        border: 1px solid #E5E5E5;
    }
    QScrollArea#settingsScroll {
        border: none;
        background: transparent;
    }
    QGroupBox#settingsGroup {
        border: 1px solid #E5E5E5;
        border-radius: 10px;
        margin-top: 8px;
        padding-top: 14px;
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 500;
        color: #3A3A3A;
        font-family: $FONT_STACK;
    }
    QGroupBox#settingsGroup::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 6px;
    }
    QPushButton#primaryActionButton {
        background: $ACCENT;
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 10px 18px;
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 500;
        font-family: $FONT_STACK;
        min-width: 120px;
    }
    QPushButton#primaryActionButton:hover {
        background: #1D4ED8;
    }
    QPushButton#primaryActionButton:pressed {
        background: #1E40AF;
    }
    QPushButton#primaryActionButton:disabled {
        background: #9CA3AF;
        color: #FFFFFF;
    }
    QPushButton#secondaryActionButton {
        background: #FFFFFF;
        color: #1D1D1D;
        border: 1px solid #D1D5DB;
        border-radius: 8px;
        padding: 8px 14px;
        font-size: ${TYPE_BODY_PX}px;
        font-family: $FONT_STACK;
    }
    QPushButton#secondaryActionButton:hover {
        background: #F9FAFB;
        border-color: #9CA3AF;
    }
    QPushButton#secondaryActionButton:pressed {
        background: #F3F4F6;
    }
    QPushButton#secondaryActionButton:disabled {
        background: #F3F4F6;
        color: #9CA3AF;
        border-color: #E5E5E5;
    }
    QPushButton#dangerButton {
        background: #FFFFFF;
        color: #DC2626;
        border: 1px solid #FECACA;
        border-radius: 8px;
        padding: 8px 14px;
        font-size: ${TYPE_BODY_PX}px;
        font-family: $FONT_STACK;
    }
    QPushButton#dangerButton:hover {
        background: #FEF2F2;
        border-color: #FCA5A5;
    }
    QPushButton#dangerButton:pressed {
        background: #FEE2E2;
    }
    QLineEdit#descriptionInput,
    QTextEdit#descriptionInput {
        background: #FFFFFF;
        color: #1D1D1D;
        border: 1px solid #D1D5DB;
        border-radius: 8px;
        padding: 10px 12px;
        font-size: ${TYPE_SUBTITLE_PX}px;
        font-family: $FONT_STACK;
    }
    QLineEdit#descriptionInput:focus,
    QTextEdit#descriptionInput:focus {
        border-color: #2563EB;
        outline: none;
    }
    QTextEdit#descriptionInput {
        min-height: 120px;
        max-height: 220px;
    }
    QListWidget#workflowList,
    QListWidget#activitiesList,
    QListWidget#recordingList,
    QListWidget#stepsList {
        background: #FFFFFF;
        border: 1px solid #E5E5E5;
        border-radius: 8px;
        padding: 4px;
        font-size: ${TYPE_BODY_PX}px;
        color: #1D1D1D;
        font-family: $FONT_STACK;
        min-height: 80px;
    }
    QListWidget#workflowList::item,
    QListWidget#activitiesList::item,
    QListWidget#recordingList::item,
    QListWidget#stepsList::item {
        padding: 8px 10px;
        border-radius: 6px;
        margin: 2px 0;
    }
    QListWidget#workflowList::item:selected,
    QListWidget#activitiesList::item:selected,
    QListWidget#recordingList::item:selected,
    QListWidget#stepsList::item:selected {
        background: #EEF2FF;
        color: #1D1D1D;
    }
    QListWidget#workflowList::item:hover,
    QListWidget#activitiesList::item:hover,
    QListWidget#recordingList::item:hover,
    QListWidget#stepsList::item:hover {
        background: #F9FAFB;
    }

    /* --- P2 components: page header, banners, footer, cards, chips, ghost --- */
    QWidget#pageHeader {
        background: transparent;
    }
    QLabel#pageDescription {
        font-size: ${TYPE_SUBTITLE_PX}px;
        color: ${TEXT_BODY};
        font-family: $FONT_STACK;
    }
    QFrame#cardTile {
        background: ${SURFACE};
        border: 1px solid ${BORDER};
        border-radius: 12px;
    }
    QLabel#cardTitle {
        font-size: ${TYPE_SUBTITLE_PX}px;
        font-weight: 600;
        color: ${TEXT_STRONG};
        font-family: $FONT_STACK;
    }
    QLabel#cardBody {
        font-size: ${TYPE_CAPTION_PX}px;
        color: ${TEXT_BODY};
        font-family: $FONT_STACK;
    }
    QLabel#chip {
        font-size: ${TYPE_CAPTION_PX}px;
        color: ${TEXT_BODY};
        background: ${ACCENT_SOFT};
        border-radius: 8px;
        padding: 2px 8px;
        font-family: $FONT_STACK;
    }
    QLabel#chip[chipKind="ok"] {
        color: ${STATUS_OK};
        background: ${TINT_VERIFY};
    }
    QLabel#chip[chipKind="fail"] {
        color: ${STATUS_ERROR};
        background: ${TINT_STOP};
    }
    QLabel#chip[chipKind="warn"] {
        color: ${STATUS_WARNING};
        background: ${TINT_ACTION};
    }
    QFrame#banner {
        border-radius: 10px;
        border: 1px solid ${BORDER};
        background: ${SURFACE};
    }
    QFrame#banner[severity="error"] {
        border-color: #FCA5A5;
    }
    QFrame#banner[severity="warning"] {
        border-color: #FCD34D;
    }
    QFrame#banner[severity="success"] {
        border-color: #86EFAC;
    }
    QLabel#bannerBadge {
        font-size: ${TYPE_CAPTION_PX}px;
        font-weight: 600;
        color: ${TEXT_BODY};
        font-family: $FONT_STACK;
    }
    QLabel#bannerTitle {
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 600;
        color: ${TEXT_STRONG};
        font-family: $FONT_STACK;
    }
    QLabel#bannerBody {
        font-size: ${TYPE_CAPTION_PX}px;
        color: ${TEXT_BODY};
        font-family: $FONT_STACK;
    }
    QPushButton#bannerDismiss {
        background: transparent;
        border: none;
        color: ${TEXT_FAINT};
        font-size: ${TYPE_CAPTION_PX}px;
        padding: 4px 6px;
        font-family: $FONT_STACK;
    }
    QPushButton#bannerDismiss:hover {
        color: ${TEXT_STRONG};
    }
    QPushButton#ghostButton {
        background: transparent;
        border: none;
        color: ${ACCENT_TEXT};
        font-size: ${TYPE_BODY_PX}px;
        padding: 6px 10px;
        font-family: $FONT_STACK;
    }
    QPushButton#ghostButton:hover {
        text-decoration: underline;
    }
    QPushButton#ghostButton:disabled {
        color: #9CA3AF;
    }
    QPushButton#confirmButton {
        background: ${PRIMARY_BTN};
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 9px 16px;
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 500;
        font-family: $FONT_STACK;
    }
    QPushButton#confirmButton:hover {
        background: #01192F;
    }
    QPushButton#confirmButton[armed="true"] {
        background: ${STATUS_ERROR};
    }
    QPushButton#confirmButton:disabled {
        background: #9CA3AF;
        color: #FFFFFF;
    }
    QLabel#statusFooterText {
        font-size: ${TYPE_CAPTION_PX}px;
        color: ${TEXT_BODY};
        font-family: $FONT_STACK;
    }
    QLabel#emptyHeading {
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 600;
        color: ${TEXT_STRONG};
        font-family: $FONT_STACK;
    }
    QLabel#emptyBody {
        font-size: ${TYPE_CAPTION_PX}px;
        color: ${TEXT_BODY};
        font-family: $FONT_STACK;
    }
    /* inputBase is objectName-based on purpose: the verifier panel's classes
       (QLineEdit/QTextEdit/QPlainTextEdit) are all QWidget subclasses, so one
       selector covers them without naming widget classes the audit does not
       track. */
    QWidget#inputBase {
        background: ${SURFACE};
        color: ${TEXT_STRONG};
        border: 1px solid ${BORDER_STRONG};
        border-radius: 8px;
        padding: 8px 10px;
        font-size: ${TYPE_BODY_PX}px;
        font-family: $FONT_STACK;
    }
    QWidget#inputBase:focus {
        border-color: ${ACCENT};
    }

    /* --- P2 page rows and inline panel ----------------------------------- */
    QWidget#automationRow,
    QWidget#runRow {
        background: transparent;
    }
    QLabel#rowTitle {
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 500;
        color: ${TEXT_STRONG};
        font-family: $FONT_STACK;
    }
    QLabel#rowCaption {
        font-size: ${TYPE_CAPTION_PX}px;
        color: ${TEXT_FAINT};
        font-family: $FONT_STACK;
    }
    QFrame#verifierEditorPanel {
        background: ${SURFACE_ALT};
        border: 1px solid ${BORDER};
        border-radius: 10px;
    }
    QLabel#panelErrorLabel {
        font-size: ${TYPE_CAPTION_PX}px;
        color: ${STATUS_ERROR};
        font-family: $FONT_STACK;
    }
""")
