"""Once design system — the single source of truth for the v4 look.

Every colour, type size, geometry value and animation duration used by the UI
lives here. ``ui/`` imports these constants instead of writing literals, and
``tests/test_token_scan_expanded.py`` fails the build when a component file
introduces a colour, a stylesheet size or a duration of its own.

The visual language: a navy rail with a lemon wordmark and a lemon active pill,
colour-blocked page bands with clipped Anton display titles, lemon primary
buttons with navy text, outlined navy secondary buttons and outlined red
destructive buttons.
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
TYPE_PAGE_TITLE_PX = 72
TYPE_HERO_PX = 128
TYPE_STAT_PX = 56
TYPE_WORDMARK_PX = 44
TYPE_HOME_TITLE_PX = 32
TYPE_TITLE_PX = 26
TYPE_QUESTION_PX = 18
TYPE_HOME_SUBTITLE_PX = 16
TYPE_SUBTITLE_PX = 15
TYPE_BODY_PX = 14
TYPE_CAPTION_PX = 13
TYPE_FOOTER_PX = 11

#: Display (Anton) line boxes are 0.85 of the font size: the glyphs stay large
#: while the leading collapses, which is what makes the headlines read as blocks.
DISPLAY_LINE_HEIGHT = 0.85

UI_FONT = "Inter"
DISPLAY_FONT = "Anton"
FONT_STACK = '"Inter", "Segoe UI", system-ui, sans-serif'
DISPLAY_FONT_STACK = '"Anton", "Inter", system-ui, sans-serif'

# --- Color tokens (single source for both stylesheet and painted widgets) ----
BG_APP = "#F2F6FA"
BG_CANVAS = "#FBFCFE"
DOT_GRID = "#DDE3EC"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F7FAFD"
BORDER = "#E1E8F0"
BORDER_STRONG = "#C6D3E0"
ACCENT = "#2472B0"
ACCENT_TEXT = "#1B5A87"
ACCENT_SOFT = "#EAF3FA"
PRIMARY_BTN = "#0B1F33"
TEXT_STRONG = "#0B1F33"
TEXT_BODY = "#334B66"
TEXT_FAINT = "#5B7188"

#: Navy rail. The wordmark and the active pill are the only lemon surfaces here.
NAVY = "#0B1F33"
NAVY_HOVER = "#14305A"
SIDEBAR_BG = NAVY
SIDEBAR_TEXT = "#A8C4DD"
SIDEBAR_TEXT_HOVER = "#FFFFFF"
SIDEBAR_HOVER_BG = NAVY_HOVER
SIDEBAR_ACTIVE_BG = "#F7DC3C"
SIDEBAR_ACTIVE_TEXT = NAVY
SIDEBAR_FOOTER_TEXT = "#7E9AB5"

#: Colour blocking behind page titles.
BAND_BG = "#D8E9F6"
BAND_ALT_BG = "#DDEBF7"
BAND_TEXT = NAVY
BAND_MICRO = "#15507A"

LEMON = "#F7DC3C"
LEMON_DEEP = "#E8C51B"
LEMON_SOFT = "#FDF6D2"
GLACIER_600 = "#2472B0"
GLACIER_BLUE = "#2472B0"
WHITE = "#FFFFFF"
HERO_BLUE = "#3E9BE6"
HERO_BLUE_CONTRAST = "#2472B0"

STATUS_OK = "#1F6B4A"
STATUS_RUNNING = "#1F5F8B"
STATUS_ERROR = "#A33434"
STATUS_WARNING = "#7A4A12"

TINT_ACTION = "#FBF0DC"
TINT_VERIFY = "#E6F4EC"
TINT_PROGRESS = "#EAF5FC"
TINT_STOP = "#FBECEC"
TINT_START = "#FCF6E3"
TINT_FINISH = "#EEF3F8"
TINT_NOTE = "#FBF7DC"

# --- Geometry tokens -------------------------------------------------------
SIDEBAR_WIDTH = 232
SIDEBAR_ICON_PX = 24
SIDEBAR_ICON_GAP_PX = 14
SIDEBAR_ITEM_HEIGHT = 52
SIDEBAR_ITEM_INSET = 12
SIDEBAR_PILL_RADIUS = 12
CIRCLE_BUTTON_PX = 128
CIRCLE_BUTTON_SMALL_PX = 56
EMPTY_STATE_ICON_PX = 48
BAND_HEIGHT = 150
BAND_CROP_PX = 18
ROW_HEIGHT = 64
CONTROL_HEIGHT = 38
CONTROL_HEIGHT_SMALL = 34

# --- Motion tokens ---------------------------------------------------------
PAGE_SLIDE_PX = 16
DURATION_PAGE_MS = 260
DIALOG_SCALE = 0.98
STAGGER_LIMIT = 3
DURATION_DIALOG_MS = 220
DURATION_RUNNING_PULSE_MS = 400
DURATION_STAGGER_MS = 60
DURATION_HERO_MS = 280
HERO_REVEAL_OFFSET_PX = 16
DURATION_HOVER_MS = 120
HOVER_SCALE = 1.03
PRESS_SCALE = 0.97
ARROW_SHIFT_PX = 4

COLOR_TOKENS = {
    "BG_APP": BG_APP,
    "BG_CANVAS": BG_CANVAS,
    "DOT_GRID": DOT_GRID,
    "SURFACE": SURFACE,
    "SURFACE_ALT": SURFACE_ALT,
    "BORDER": BORDER,
    "BORDER_STRONG": BORDER_STRONG,
    "ACCENT": ACCENT,
    "ACCENT_TEXT": ACCENT_TEXT,
    "ACCENT_SOFT": ACCENT_SOFT,
    "PRIMARY_BTN": PRIMARY_BTN,
    "TEXT_STRONG": TEXT_STRONG,
    "TEXT_BODY": TEXT_BODY,
    "TEXT_FAINT": TEXT_FAINT,
    "NAVY": NAVY,
    "NAVY_HOVER": NAVY_HOVER,
    "SIDEBAR_BG": SIDEBAR_BG,
    "SIDEBAR_TEXT": SIDEBAR_TEXT,
    "SIDEBAR_TEXT_HOVER": SIDEBAR_TEXT_HOVER,
    "SIDEBAR_HOVER_BG": SIDEBAR_HOVER_BG,
    "SIDEBAR_ACTIVE_BG": SIDEBAR_ACTIVE_BG,
    "SIDEBAR_ACTIVE_TEXT": SIDEBAR_ACTIVE_TEXT,
    "SIDEBAR_FOOTER_TEXT": SIDEBAR_FOOTER_TEXT,
    "BAND_BG": BAND_BG,
    "BAND_ALT_BG": BAND_ALT_BG,
    "BAND_TEXT": BAND_TEXT,
    "BAND_MICRO": BAND_MICRO,
    "LEMON": LEMON,
    "LEMON_DEEP": LEMON_DEEP,
    "LEMON_SOFT": LEMON_SOFT,
    "GLACIER_600": GLACIER_600,
    "GLACIER_BLUE": GLACIER_BLUE,
    "WHITE": WHITE,
    "HERO_BLUE": HERO_BLUE,
    "HERO_BLUE_CONTRAST": HERO_BLUE_CONTRAST,
    "STATUS_OK": STATUS_OK,
    "STATUS_RUNNING": STATUS_RUNNING,
    "STATUS_ERROR": STATUS_ERROR,
    "STATUS_WARNING": STATUS_WARNING,
    "TINT_ACTION": TINT_ACTION,
    "TINT_VERIFY": TINT_VERIFY,
    "TINT_PROGRESS": TINT_PROGRESS,
    "TINT_STOP": TINT_STOP,
    "TINT_START": TINT_START,
    "TINT_FINISH": TINT_FINISH,
    "TINT_NOTE": TINT_NOTE,
}

#: Text/surface pairs used by pages; the contrast test walks this list.
CONTRAST_PAIRS = (
    ("body on card", TEXT_BODY, SURFACE),
    ("strong on card", TEXT_STRONG, SURFACE),
    ("faint on card", TEXT_FAINT, SURFACE),
    ("body on app", TEXT_BODY, BG_APP),
    ("strong on app", TEXT_STRONG, BG_APP),
    ("body on accent tint", TEXT_BODY, ACCENT_SOFT),
    ("sidebar text on navy", SIDEBAR_TEXT, SIDEBAR_BG),
    ("sidebar text hover on navy", SIDEBAR_TEXT_HOVER, SIDEBAR_HOVER_BG),
    ("sidebar active text on lemon", SIDEBAR_ACTIVE_TEXT, SIDEBAR_ACTIVE_BG),
    ("band title on band", BAND_TEXT, BAND_BG),
    ("band micro on band", BAND_MICRO, BAND_BG),
    ("lemon wordmark on navy", LEMON, NAVY),
    ("button text on primary", PRIMARY_BTN, LEMON),
    ("secondary text on surface", NAVY, SURFACE),
    ("status ok text", STATUS_OK, SURFACE),
    ("status running text", STATUS_RUNNING, SURFACE),
    ("status error text", STATUS_ERROR, SURFACE),
    ("status warning text", STATUS_WARNING, SURFACE),
    ("strong on action tint", TEXT_STRONG, TINT_ACTION),
    ("strong on verify tint", TEXT_STRONG, TINT_VERIFY),
    ("strong on progress tint", TEXT_STRONG, TINT_PROGRESS),
    ("strong on stop tint", TEXT_STRONG, TINT_STOP),
    ("strong on finish tint", TEXT_STRONG, TINT_FINISH),
    ("strong on note tint", TEXT_STRONG, TINT_NOTE),
)

#: Rules the stylesheet keeps for the shared page template. Their font sizes
#: must come from the type tokens above (asserted by tests/test_shell.py).
TYPED_RULES = {
    "QLabel#pageTitle": TYPE_PAGE_TITLE_PX,
    "QLabel#pageSubtitle": TYPE_SUBTITLE_PX,
    "QLabel#homeTitle": TYPE_HOME_TITLE_PX,
    "QLabel#questionLabel": TYPE_QUESTION_PX,
    "QLabel#hintLabel": TYPE_CAPTION_PX,
}


def apply_theme(window) -> None:
    """Install the Once design system on the whole application."""
    app = QApplication.instance() or window
    _set_palette(app)
    _set_stylesheet(app)


def render_stylesheet() -> str:
    """Return the fully substituted stylesheet (used by the token tests)."""
    return _STYLESHEET_TEMPLATE.substitute(_substitutions())


def _set_palette(app) -> None:
    from PySide6.QtGui import QColor, QPalette

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG_APP))
    palette.setColor(QPalette.WindowText, QColor(TEXT_STRONG))
    palette.setColor(QPalette.Base, QColor(SURFACE))
    palette.setColor(QPalette.AlternateBase, QColor(SURFACE_ALT))
    palette.setColor(QPalette.Text, QColor(TEXT_STRONG))
    palette.setColor(QPalette.Button, QColor(SURFACE))
    palette.setColor(QPalette.ButtonText, QColor(TEXT_STRONG))
    palette.setColor(QPalette.Highlight, QColor(NAVY))
    palette.setColor(QPalette.HighlightedText, QColor(WHITE))
    palette.setColor(QPalette.Link, QColor(ACCENT))
    app.setPalette(palette)


def _substitutions() -> dict[str, object]:
    substitutions: dict[str, object] = {name: value for name, value in COLOR_TOKENS.items()}
    substitutions.update(
        {
            "FONT_STACK": FONT_STACK,
            "DISPLAY_FONT_STACK": DISPLAY_FONT_STACK,
            "UI_FONT": UI_FONT,
            "DISPLAY_FONT": DISPLAY_FONT,
            "TYPE_HERO_PX": TYPE_HERO_PX,
            "TYPE_PAGE_TITLE_PX": TYPE_PAGE_TITLE_PX,
            "TYPE_STAT_PX": TYPE_STAT_PX,
            "TYPE_HOME_TITLE_PX": TYPE_HOME_TITLE_PX,
            "TYPE_TITLE_PX": TYPE_TITLE_PX,
            "TYPE_WORDMARK_PX": TYPE_WORDMARK_PX,
            "TYPE_QUESTION_PX": TYPE_QUESTION_PX,
            "TYPE_HOME_SUBTITLE_PX": TYPE_HOME_SUBTITLE_PX,
            "TYPE_SUBTITLE_PX": TYPE_SUBTITLE_PX,
            "TYPE_BODY_PX": TYPE_BODY_PX,
            "TYPE_CAPTION_PX": TYPE_CAPTION_PX,
            "TYPE_FOOTER_PX": TYPE_FOOTER_PX,
            "BAND_HEIGHT": BAND_HEIGHT,
            "SIDEBAR_WIDTH": SIDEBAR_WIDTH,
            "SIDEBAR_ITEM_HEIGHT": SIDEBAR_ITEM_HEIGHT,
            "ROW_HEIGHT": ROW_HEIGHT,
            "CONTROL_HEIGHT": CONTROL_HEIGHT,
            "CONTROL_HEIGHT_SMALL": CONTROL_HEIGHT_SMALL,
            "CIRCLE_BUTTON_RADIUS": CIRCLE_BUTTON_PX // 2,
            "SPACE_XS": SPACING_XS,
            "SPACE_SM": SPACING_SM,
            "SPACE_MD": SPACING_MD,
            "SPACE_LG": SPACING_LG,
            "SPACE_XL": SPACING_XL,
            "SPACE_XXL": SPACING_XXL,
        }
    )
    return substitutions


def _set_stylesheet(app) -> None:
    app.setStyleSheet(render_stylesheet())


_STYLESHEET_TEMPLATE = Template("""
    QMainWindow {
        background: $BG_APP;
    }
    QWidget#sidePanel {
        background: $SIDEBAR_BG;
        border: none;
    }
    QWidget#mainPanel {
        background: $BG_APP;
    }
    QToolBar#sidebar {
        background: $SIDEBAR_BG;
        padding: 0px;
        border: none;
    }
    QLabel#onceLogo {
        font-size: ${TYPE_WORDMARK_PX}px;
        font-weight: 400;
        color: $LEMON;
        padding: ${SPACE_MD}px ${SPACE_XL}px ${SPACE_SM}px ${SPACE_XL}px;
        font-family: $DISPLAY_FONT_STACK;
    }
    QLabel#sidebarFooter {
        font-size: ${TYPE_FOOTER_PX}px;
        color: $SIDEBAR_FOOTER_TEXT;
        padding: ${SPACE_MD}px ${SPACE_XL}px ${SPACE_XS}px ${SPACE_XL}px;
        font-family: $FONT_STACK;
    }
    QLabel#statusFooterText {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $SIDEBAR_TEXT;
        font-family: $FONT_STACK;
    }

    /* --- Display type ---------------------------------------------------- */
    QLabel#pageTitle {
        font-size: ${TYPE_PAGE_TITLE_PX}px;
        font-weight: 400;
        color: $BAND_TEXT;
        font-family: $DISPLAY_FONT_STACK;
        margin: 0px;
    }
    QLabel#pageSubtitle {
        font-size: ${TYPE_SUBTITLE_PX}px;
        color: $TEXT_BODY;
        font-family: $FONT_STACK;
    }
    QLabel#pageMicro {
        font-size: ${TYPE_CAPTION_PX}px;
        font-weight: 700;
        color: $BAND_MICRO;
        font-family: $FONT_STACK;
    }
    QLabel#heroMicro {
        font-size: ${TYPE_CAPTION_PX}px;
        font-weight: 700;
        color: $WHITE;
        font-family: $FONT_STACK;
    }
    QLabel#heroLine {
        font-size: ${TYPE_HERO_PX}px;
        font-weight: 400;
        color: $WHITE;
        font-family: $DISPLAY_FONT_STACK;
    }
    QLabel#heroLineAccent {
        font-size: ${TYPE_HERO_PX}px;
        font-weight: 400;
        color: $LEMON;
        font-family: $DISPLAY_FONT_STACK;
    }
    QLabel#heroSubtitle {
        font-size: ${TYPE_HOME_SUBTITLE_PX}px;
        color: $WHITE;
        font-family: $FONT_STACK;
    }
    QLabel#statNumber {
        font-size: ${TYPE_STAT_PX}px;
        font-weight: 400;
        color: $BAND_TEXT;
        font-family: $DISPLAY_FONT_STACK;
    }
    QLabel#statCaption {
        font-size: ${TYPE_CAPTION_PX}px;
        font-weight: 600;
        color: $TEXT_BODY;
        font-family: $FONT_STACK;
    }
    QFrame#statBlock {
        background: $SURFACE;
        border: 1px solid $BORDER;
        border-radius: 14px;
    }
    QFrame#statBlock[accent="true"] {
        background: $LEMON_SOFT;
        border-color: $LEMON;
    }
    QFrame#heroPanel {
        background: $HERO_BLUE_CONTRAST;
        border: none;
        border-radius: 18px;
    }
    QWidget#heroLines {
        background: transparent;
    }
    QFrame#pageBand {
        background: $BAND_BG;
        border: none;
    }
    QFrame#pageBand[bandTone="alt"] {
        background: $BAND_ALT_BG;
    }
    QLabel#homeTitle {
        font-size: ${TYPE_HOME_TITLE_PX}px;
        font-weight: 700;
        color: $TEXT_STRONG;
        font-family: $FONT_STACK;
    }
    QLabel#homeSubtitle {
        font-size: ${TYPE_HOME_SUBTITLE_PX}px;
        color: $TEXT_BODY;
        font-family: $FONT_STACK;
    }
    QLabel#questionLabel {
        font-size: ${TYPE_QUESTION_PX}px;
        font-weight: 500;
        color: $TEXT_STRONG;
        font-family: $FONT_STACK;
    }
    QLabel#hintLabel {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $TEXT_FAINT;
        font-family: $FONT_STACK;
    }

    /* --- Buttons --------------------------------------------------------- */
    QPushButton#primaryActionButton {
        background: $LEMON;
        color: $NAVY;
        border: 1px solid $LEMON_DEEP;
        border-radius: 10px;
        padding: 9px ${SPACE_XL}px;
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 700;
        font-family: $FONT_STACK;
        min-height: ${CONTROL_HEIGHT}px;
    }
    QPushButton#primaryActionButton:hover {
        background: $LEMON_DEEP;
    }
    QPushButton#primaryActionButton:pressed {
        background: $LEMON_DEEP;
        border-color: $BAND_MICRO;
    }
    QPushButton#primaryActionButton:disabled {
        background: $TINT_FINISH;
        color: $TEXT_FAINT;
        border-color: $BORDER;
    }
    QPushButton#secondaryActionButton {
        background: transparent;
        color: $NAVY;
        border: 1px solid $NAVY;
        border-radius: 10px;
        padding: 8px 16px;
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 600;
        font-family: $FONT_STACK;
        min-height: ${CONTROL_HEIGHT_SMALL}px;
    }
    QPushButton#secondaryActionButton:hover {
        background: $ACCENT_SOFT;
    }
    QPushButton#secondaryActionButton:pressed {
        background: $BAND_BG;
    }
    QPushButton#secondaryActionButton:disabled {
        color: $TEXT_FAINT;
        border-color: $BORDER_STRONG;
    }
    QPushButton#dangerButton {
        background: transparent;
        color: $STATUS_ERROR;
        border: 1px solid $STATUS_ERROR;
        border-radius: 10px;
        padding: 8px 16px;
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 600;
        font-family: $FONT_STACK;
        min-height: ${CONTROL_HEIGHT_SMALL}px;
    }
    QPushButton#dangerButton:hover {
        background: $TINT_STOP;
    }
    QPushButton#dangerButton:pressed {
        background: $TINT_STOP;
        border-color: $STATUS_ERROR;
    }
    QPushButton#dangerButton:disabled {
        color: $TEXT_FAINT;
        border-color: $BORDER_STRONG;
    }
    QPushButton#linkActionButton {
        background: transparent;
        border: none;
        color: $ACCENT_TEXT;
        font-size: ${TYPE_CAPTION_PX}px;
        font-weight: 700;
        padding: 2px 4px;
        font-family: $FONT_STACK;
    }
    QPushButton#linkActionButton:hover {
        color: $NAVY;
    }
    QPushButton#ghostButton {
        background: transparent;
        border: none;
        color: $ACCENT_TEXT;
        font-size: ${TYPE_BODY_PX}px;
        padding: 6px 10px;
        font-family: $FONT_STACK;
    }
    QPushButton#ghostButton:hover {
        color: $NAVY;
    }
    QPushButton#ghostButton:disabled {
        color: $TEXT_FAINT;
    }
    QPushButton#runRowButton {
        background: $LEMON;
        color: $NAVY;
        border: 1px solid $LEMON_DEEP;
        border-radius: 9px;
        padding: 6px 14px;
        font-size: ${TYPE_CAPTION_PX}px;
        font-weight: 700;
        font-family: $FONT_STACK;
        min-height: ${CONTROL_HEIGHT_SMALL}px;
    }
    QPushButton#runRowButton:hover {
        background: $LEMON_DEEP;
    }
    QPushButton#runRowButton:disabled {
        background: $TINT_FINISH;
        color: $TEXT_FAINT;
        border-color: $BORDER;
    }
    QPushButton#runRowButton[armed="true"] {
        background: $NAVY;
        color: $LEMON;
        border-color: $NAVY;
    }
    QPushButton#heroSecondaryButton {
        background: transparent;
        color: $WHITE;
        border: 2px solid $WHITE;
        border-radius: 10px;
        padding: 8px 18px;
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 700;
        font-family: $FONT_STACK;
        min-height: ${CONTROL_HEIGHT_SMALL}px;
    }
    QPushButton#heroSecondaryButton:hover {
        background: $WHITE;
        color: $HERO_BLUE_CONTRAST;
    }
    QPushButton#heroSecondaryButton:pressed {
        background: $BAND_BG;
        color: $HERO_BLUE_CONTRAST;
    }
    QPushButton#heroSecondaryButton:disabled {
        border-color: $SIDEBAR_TEXT;
        color: $SIDEBAR_TEXT;
    }
    QPushButton#circleButton {
        background: $LEMON;
        color: $NAVY;
        border: none;
        border-radius: ${CIRCLE_BUTTON_RADIUS}px;
        font-size: ${TYPE_SUBTITLE_PX}px;
        font-weight: 700;
        font-family: $FONT_STACK;
    }
    QPushButton#circleButton:hover {
        background: $LEMON_DEEP;
    }
    QPushButton#circleButton:pressed {
        background: $LEMON_DEEP;
    }
    QPushButton#outlinedCircleButton {
        background: transparent;
        color: $WHITE;
        border: 2px solid $WHITE;
        border-radius: ${CIRCLE_BUTTON_RADIUS}px;
        font-size: ${TYPE_CAPTION_PX}px;
        font-weight: 700;
        font-family: $FONT_STACK;
    }
    QPushButton#outlinedCircleButton:hover {
        background: $WHITE;
        color: $HERO_BLUE_CONTRAST;
    }
    QPushButton#bannerDismiss {
        background: transparent;
        border: none;
        color: $TEXT_FAINT;
        font-size: ${TYPE_CAPTION_PX}px;
        padding: 4px 6px;
        font-family: $FONT_STACK;
    }
    QPushButton#bannerDismiss:hover {
        color: $TEXT_STRONG;
    }
    QPushButton#confirmButton {
        background: $NAVY;
        color: $LEMON;
        border: none;
        border-radius: 10px;
        padding: 9px 16px;
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 700;
        font-family: $FONT_STACK;
    }
    QPushButton#confirmButton:hover {
        background: $NAVY_HOVER;
    }
    QPushButton#confirmButton[armed="true"] {
        background: $STATUS_ERROR;
        color: $WHITE;
    }
    QPushButton#confirmButton:disabled {
        background: $BORDER;
        color: $TEXT_FAINT;
    }
    QPushButton#primaryActionButton:focus,
    QPushButton#secondaryActionButton:focus,
    QPushButton#dangerButton:focus,
    QPushButton#circleButton:focus,
    QPushButton#outlinedCircleButton:focus,
    QListWidget:focus {
        outline: 2px solid $ACCENT;
        outline-offset: 2px;
    }

    /* --- Surfaces -------------------------------------------------------- */
    QFrame#cardTile {
        background: $SURFACE;
        border: 1px solid $BORDER;
        border-radius: 14px;
    }
    QFrame#sectionCard {
        background: $SURFACE;
        border: 1px solid $BORDER;
        border-radius: 14px;
    }
    QLabel#sectionCardTitle {
        font-size: ${TYPE_QUESTION_PX}px;
        font-weight: 700;
        color: $TEXT_STRONG;
        font-family: $FONT_STACK;
    }
    QLabel#sectionCardBody {
        font-size: ${TYPE_BODY_PX}px;
        color: $TEXT_BODY;
        font-family: $FONT_STACK;
    }
    QLabel#cardTitle {
        font-size: ${TYPE_SUBTITLE_PX}px;
        font-weight: 700;
        color: $TEXT_STRONG;
        font-family: $FONT_STACK;
    }
    QLabel#cardBody {
        font-size: ${TYPE_BODY_PX}px;
        color: $TEXT_BODY;
        font-family: $FONT_STACK;
    }
    QLabel#rowTitle {
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 700;
        color: $TEXT_STRONG;
        font-family: $FONT_STACK;
    }
    QLabel#rowCaption {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $TEXT_FAINT;
        font-family: $FONT_STACK;
    }
    QLabel#rowErrorReason {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $STATUS_ERROR;
        font-family: $FONT_STACK;
    }
    QLabel#emptyHeading {
        font-size: ${TYPE_QUESTION_PX}px;
        font-weight: 700;
        color: $TEXT_STRONG;
        font-family: $FONT_STACK;
    }
    QLabel#emptyBody {
        font-size: ${TYPE_BODY_PX}px;
        color: $TEXT_BODY;
        font-family: $FONT_STACK;
    }
    QWidget#emptyState {
        background: transparent;
    }
    QFrame#homeRunRow,
    QFrame#reviewStepRow {
        background: $SURFACE;
        border: 1px solid $BORDER;
        border-radius: 12px;
    }
    QWidget#automationRow,
    QWidget#runRow {
        background: transparent;
    }
    QLabel#chip {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $TEXT_BODY;
        background: $SURFACE_ALT;
        border: 1px solid $BORDER;
        border-radius: 8px;
        padding: 3px 8px;
        min-height: 18px;
        font-family: $FONT_STACK;
    }
    QLabel#chip[chipKind="ok"] {
        color: $STATUS_OK;
        background: $TINT_VERIFY;
        border-color: $TINT_VERIFY;
        font-weight: 700;
    }
    QLabel#chip[chipKind="fail"] {
        color: $STATUS_ERROR;
        background: $TINT_STOP;
        border-color: $TINT_STOP;
        font-weight: 700;
    }
    QLabel#chip[chipKind="warn"] {
        color: $STATUS_WARNING;
        background: $TINT_ACTION;
        border-color: $TINT_ACTION;
        font-weight: 700;
    }
    QLabel#chip[chipKind="running"] {
        color: $NAVY;
        background: $LEMON;
        border-color: $LEMON_DEEP;
        font-weight: 700;
    }
    QFrame#banner {
        border-radius: 12px;
        border: 1px solid $BORDER;
        background: $SURFACE;
    }
    QFrame#banner[severity="error"] {
        border-color: $STATUS_ERROR;
        background: $TINT_STOP;
    }
    QFrame#banner[severity="warning"] {
        border-color: $STATUS_WARNING;
        background: $TINT_ACTION;
    }
    QFrame#banner[severity="success"] {
        border-color: $STATUS_OK;
        background: $TINT_VERIFY;
    }
    QLabel#bannerTitle {
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 700;
        color: $TEXT_STRONG;
        font-family: $FONT_STACK;
    }
    QLabel#bannerBody {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $TEXT_BODY;
        font-family: $FONT_STACK;
    }
    QLabel#bannerIcon {
        background: transparent;
    }
    QLabel#activityLabel {
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 700;
        color: $TEXT_STRONG;
        font-family: $FONT_STACK;
    }
    QLabel#activityEmpty {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $TEXT_BODY;
        font-family: $FONT_STACK;
    }
    QLabel#activityDetailsLabel {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $TEXT_BODY;
        font-family: $FONT_STACK;
    }
    QLabel#goalLabel {
        font-size: ${TYPE_SUBTITLE_PX}px;
        color: $TEXT_BODY;
        font-family: $FONT_STACK;
    }
    QLabel#automationDetailsLabel {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $TEXT_BODY;
        background: $SURFACE;
        border: 1px solid $BORDER;
        border-radius: 12px;
        padding: 12px 14px;
    }
    QLabel#authorizedLabel,
    QLabel#verifierIntroLabel {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $TEXT_BODY;
        font-family: $FONT_STACK;
    }
    QFrame#settingsWidget, QWidget#settingsWidget {
        background: transparent;
        border: none;
    }
    QScrollArea#settingsScroll {
        border: none;
        background: transparent;
    }
    QGroupBox#settingsGroup {
        border: 1px solid $BORDER;
        border-radius: 12px;
        margin-top: 8px;
        padding-top: 14px;
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 700;
        color: $TEXT_STRONG;
        font-family: $FONT_STACK;
    }
    QGroupBox#settingsGroup::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 6px;
        font-weight: 700;
        color: $TEXT_STRONG;
    }
    QFrame#actionsPanel,
    QFrame#activitiesList,
    QFrame#workflowList,
    QFrame#recordingList,
    QFrame#stepsList,
    QFrame#detailsContainer,
    QFrame#actionsContainer {
        background: $SURFACE;
        border-radius: 12px;
        border: 1px solid $BORDER;
    }
    QFrame#approvalPanel {
        background: $TINT_ACTION;
        border: 1px solid $STATUS_WARNING;
        border-radius: 12px;
    }
    QLabel#approvalTitle {
        color: $TEXT_STRONG;
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 700;
        font-family: $FONT_STACK;
    }
    QLabel#approvalDetails {
        color: $TEXT_BODY;
        font-size: ${TYPE_CAPTION_PX}px;
        font-family: $FONT_STACK;
    }
    QLabel#approvalPanelTitle {
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 700;
        color: $TEXT_STRONG;
        font-family: $FONT_STACK;
    }
    QLabel#approvalPanelStepsHeading {
        font-size: ${TYPE_CAPTION_PX}px;
        font-weight: 700;
        color: $TEXT_STRONG;
        font-family: $FONT_STACK;
    }
    QLabel#approvalPanelBindingNote {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $TEXT_BODY;
        font-family: $FONT_STACK;
    }
    QLabel#approvalRejectionLabel {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $STATUS_ERROR;
        font-weight: 700;
        font-family: $FONT_STACK;
    }
    QLabel#pageDescription {
        font-size: ${TYPE_SUBTITLE_PX}px;
        color: $TEXT_BODY;
        font-family: $FONT_STACK;
    }
    QLabel#panelErrorLabel {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $STATUS_ERROR;
        font-family: $FONT_STACK;
    }
    QLabel#inspectorSummary {
        font-size: ${TYPE_CAPTION_PX}px;
        color: $TEXT_BODY;
        background: $SURFACE_ALT;
        border: 1px solid $BORDER;
        border-radius: 8px;
        padding: 8px 10px;
        font-family: $FONT_STACK;
    }
    QFrame#verifierEditorPanel {
        background: $SURFACE_ALT;
        border: 1px solid $BORDER;
        border-radius: 12px;
    }
    QWidget#erroredRow {
        background: $TINT_STOP;
    }

    /* --- Inputs ---------------------------------------------------------- */
    QLineEdit#descriptionInput,
    QTextEdit#descriptionInput {
        background: $SURFACE;
        color: $TEXT_STRONG;
        border: 1px solid $BORDER_STRONG;
        border-radius: 10px;
        padding: 10px 12px;
        font-size: ${TYPE_SUBTITLE_PX}px;
        font-family: $FONT_STACK;
    }
    QLineEdit#descriptionInput:focus,
    QTextEdit#descriptionInput:focus {
        border-color: $ACCENT;
    }
    QTextEdit#descriptionInput {
        min-height: 120px;
        max-height: 220px;
    }
    QWidget#inputBase {
        background: $SURFACE;
        color: $TEXT_STRONG;
        border: 1px solid $BORDER_STRONG;
        border-radius: 10px;
        padding: 8px 10px;
        font-size: ${TYPE_BODY_PX}px;
        font-family: $FONT_STACK;
    }
    QWidget#inputBase:focus {
        border-color: $ACCENT;
    }
    QLineEdit#inlineStepEdit {
        background: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 4px 6px;
        font-size: ${TYPE_BODY_PX}px;
        font-weight: 600;
        color: $TEXT_STRONG;
        font-family: $FONT_STACK;
    }
    QLineEdit#inlineStepEdit:hover {
        border-color: $BORDER;
        background: $SURFACE_ALT;
    }
    QLineEdit#inlineStepEdit:focus {
        border-color: $ACCENT;
        background: $SURFACE;
    }
    QLineEdit#inspectorField_name,
    QLineEdit#inspectorField_message,
    QLineEdit#inspectorField_target {
        background: $SURFACE;
        color: $TEXT_STRONG;
        border: 1px solid $BORDER_STRONG;
        border-radius: 8px;
        padding: 6px 8px;
        font-size: ${TYPE_CAPTION_PX}px;
        font-family: $FONT_STACK;
    }
    QLineEdit#inspectorField_name:focus,
    QLineEdit#inspectorField_message:focus,
    QLineEdit#inspectorField_target:focus {
        border-color: $ACCENT;
    }
    QGraphicsView#canvasMinimap {
        background: $SURFACE_ALT;
        border: 1px solid $BORDER_STRONG;
        border-radius: 8px;
    }

    /* --- Lists ----------------------------------------------------------- */
    QListWidget#workflowList,
    QListWidget#activitiesList,
    QListWidget#recordingList,
    QListWidget#stepsList,
    QListWidget#editorStepsList,
    QListWidget#approvalStepList {
        background: $SURFACE;
        border: 1px solid $BORDER;
        border-radius: 12px;
        padding: 6px;
        font-size: ${TYPE_BODY_PX}px;
        color: $TEXT_STRONG;
        font-family: $FONT_STACK;
        min-height: 80px;
    }
    QListWidget#workflowList::item,
    QListWidget#activitiesList::item {
        padding: 2px 4px;
        border-radius: 8px;
        margin: 2px 0;
        color: transparent;
    }
    QListWidget#recordingList::item,
    QListWidget#stepsList::item,
    QListWidget#editorStepsList::item,
    QListWidget#approvalStepList::item {
        padding: 8px 10px;
        border-radius: 8px;
        margin: 2px 0;
    }
    QListWidget#workflowList::item:selected,
    QListWidget#activitiesList::item:selected {
        background: $ACCENT_SOFT;
        color: transparent;
    }
    QListWidget#recordingList::item:selected,
    QListWidget#stepsList::item:selected,
    QListWidget#editorStepsList::item:selected,
    QListWidget#approvalStepList::item:selected {
        background: $ACCENT_SOFT;
        color: $TEXT_STRONG;
    }
    QListWidget#workflowList::item:hover,
    QListWidget#activitiesList::item:hover {
        background: $SURFACE_ALT;
        color: transparent;
    }
    QListWidget#recordingList::item:hover,
    QListWidget#stepsList::item:hover,
    QListWidget#editorStepsList::item:hover,
    QListWidget#approvalStepList::item:hover {
        background: $SURFACE_ALT;
    }
""")
