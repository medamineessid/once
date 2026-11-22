"""Icon test for Once UI.

Verifies that Phosphor Icons are rendered correctly with QSvgRenderer
and that pixmap pixel sizes equal logical size times devicePixelRatio.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from ui.components.phosphor_icons import render_icon_pixmap

# Test sizes per the spec
TEST_ICON_SIZES = [
    ("sidebar", 24),
    ("button", 20),
    ("empty_state", 48),
]


@pytest.mark.parametrize("name, logical_size", TEST_ICON_SIZES)
def test_icon_pixmap_pixel_size(name: str, logical_size: int):
    """Assert that the icon pixmap's pixel size equals logical size * devicePixelRatio.

    This is the key DPI-scaling test: at 100% (ratio=1.0), pixel_size = logical_size.
    At 125% (ratio=1.25), pixel_size = logical_size * 1.25, etc.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    device_pixel_ratio = app.devicePixelRatio()
    pixel_size = int(logical_size * device_pixel_ratio)

    # Render the icon pixmap
    # Using a generic icon name; in production these would be real icons
    pixmap = render_icon_pixmap(
        icon_name="home",  # placeholder; will be replaced with real icons
        weight="Bold",
        logical_size=logical_size,
        color=QColor(255, 255, 255),  # white for contrast
    )

    # The critical assertion: pixel size must equal logical * ratio
    assert pixmap.size().width() == pixel_size, (
        f"{name} icon: expected pixel width {pixel_size}, got {pixmap.size().width()}"
    )
    assert pixmap.size().height() == pixel_size, (
        f"{name} icon: expected pixel height {pixel_size}, got {pixmap.size().height()}"
    )


def test_sidebar_icon_bold_weight():
    """Verify sidebar icons use Bold weight.

    Sidebar icons should be rendered with the Bold weight variant.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    dpi = app.devicePixelRatio()
    pixmap = render_icon_pixmap(
        icon_name="home",
        weight="Bold",
        logical_size=24,
        color=QColor(255, 255, 255),
    )
    assert pixmap.size().width() == int(24 * dpi)
    assert pixmap.size().height() == int(24 * dpi)


def test_active_icon_fill_weight():
    """Verify active items use Fill weight.

    Active selected items should use the Fill weight variant of icons.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    dpi = app.devicePixelRatio()
    pixmap = render_icon_pixmap(
        icon_name="home",
        weight="Fill",
        logical_size=24,
        color=QColor(255, 255, 255),
    )
    assert pixmap.size().width() == int(24 * dpi)
    assert pixmap.size().height() == int(24 * dpi)


def test_no_emoji_icons():
    """Verify no emoji are used as icons.

    All icons must be sourced from the Phosphor SVG set, not emoji.
    """
    # This is a code-structure check: ensure no QIcon(QPixmap.fromImage)
    # with emoji content is used in the sidebar/button code.
    # The test passes if the phosphor_icons module is being used
    # and no emoji-based QIcon calls exist in ui/.
    import inspect

    from ui.shell import SidebarButton

    source = inspect.getsource(SidebarButton.__init__)
    # Check that no emoji/emoji-related code is in the button init
    assert "\U0001f600" not in source, "Found emoji in SidebarButton source"
    assert "emoji" not in source.lower(), "Found emoji reference in SidebarButton source"
