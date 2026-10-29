"""Reused shell components (P2): banner, inline confirm, status footer.

Components in this package must not contain page logic; they are presentation
only. ui/ stays free of file-system mutation (working agreement rule 3).
"""

from ui.components.banner import Banner
from ui.components.cards import Card, Chip, EmptyState
from ui.components.confirm import InlineConfirm
from ui.components.footer import StatusFooter
from ui.components.icons import (
    draw_activity_glyph,
    draw_alert_circle,
    draw_automations_glyph,
    draw_check_circle,
    draw_home_glyph,
    draw_info_circle,
    draw_settings_glyph,
    icon_pixmap,
)
from ui.components.pageheader import PageHeader
from ui.components.verifier_panel import VerifierEditorPanel

__all__ = [
    "Banner",
    "Card",
    "Chip",
    "EmptyState",
    "InlineConfirm",
    "PageHeader",
    "StatusFooter",
    "VerifierEditorPanel",
    "draw_activity_glyph",
    "draw_alert_circle",
    "draw_automations_glyph",
    "draw_check_circle",
    "draw_home_glyph",
    "draw_info_circle",
    "draw_settings_glyph",
    "icon_pixmap",
]
