"""Once design system — consistent typography, spacing, and palette."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication


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
    app.setStyleSheet("""
        QMainWindow {
            background: #F3F3F3;
        }
        QWidget#sidePanel {
            background: #FFFFFF;
            border-right: 1px solid #E5E5E5;
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
            font-family: "Inter", "Segoe UI", "SF Pro Display", system-ui, sans-serif;
        }
        QLabel#onceManufacturer {
            font-size: 12px;
            color: #6B6B6B;
            padding: 0 6px;
            font-family: "Inter", "Segoe UI", "SF Pro Display", system-ui, sans-serif;
        }
        QLabel#sidebarFooter {
            font-size: 11px;
            color: #9A9A9A;
            padding: 12px 6px 4px 6px;
            font-family: "Inter", "Segoe UI", "SF Pro Display", system-ui, sans-serif;
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
            font-size: 14px;
            padding: 10px 12px;
            border-radius: 0 8px 8px 0;
            font-family: "Inter", "Segoe UI", "SF Pro Display", system-ui, sans-serif;
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
        QToolButton#sidebarHomeButton:checked,
        QToolButton#sidebarAutomationsButton:checked,
        QToolButton#sidebarActivityButton:checked,
        QToolButton#sidebarSettingsButton:checked,
        QToolButton#sidebarCreateButton:checked {
            background: #FFFFFF;
            border-left: 3px solid #2563EB;
            color: #1D1D1D;
            font-weight: 500;
        }
        QLabel#homeTitle {
            font-size: 34px;
            font-weight: 600;
            color: #1D1D1D;
        }
        QLabel#homeSubtitle {
            font-size: 16px;
            color: #525252;
            margin-top: 8px;
        }
        QLabel#pageTitle {
            font-size: 28px;
            font-weight: 600;
            color: #1D1D1D;
        }
        QLabel#pageSubtitle {
            font-size: 16px;
            color: #525252;
            margin-top: 4px;
        }
        QLabel#questionLabel {
            font-size: 20px;
            font-weight: 500;
            color: #3A3A3A;
        }
        QLabel#hintLabel {
            font-size: 14px;
            color: #6B6B6B;
        }
        QLabel#activityLabel {
            font-size: 15px;
            font-weight: 500;
            color: #3A3A3A;
        }
        QLabel#activityEmpty {
            font-size: 14px;
            color: #6B6B6B;
        }
        QLabel#activityItem {
            font-size: 14px;
            color: #2E7D32;
        }
        QLabel#activityDetailsLabel {
            font-size: 14px;
            color: #6B6B6B;
        }
        QLabel#goalLabel {
            font-size: 16px;
            color: #525252;
            margin-top: 4px;
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
            font-size: 14px;
            font-weight: 500;
            color: #3A3A3A;
            font-family: "Inter", "Segoe UI", "SF Pro Display", system-ui, sans-serif;
        }
        QGroupBox#settingsGroup::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 6px;
        }
        QPushButton#primaryActionButton {
            background: #2563EB;
            color: #FFFFFF;
            border: none;
            border-radius: 8px;
            padding: 10px 18px;
            font-size: 14px;
            font-weight: 500;
            font-family: "Inter", "Segoe UI", "SF Pro Display", system-ui, sans-serif;
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
            font-size: 14px;
            font-family: "Inter", "Segoe UI", "SF Pro Display", system-ui, sans-serif;
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
            font-size: 14px;
            font-family: "Inter", "Segoe UI", "SF Pro Display", system-ui, sans-serif;
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
            font-size: 15px;
            font-family: "Inter", "Segoe UI", "SF Pro Display", system-ui, sans-serif;
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
            font-size: 14px;
            color: #1D1D1D;
            font-family: "Inter", "Segoe UI", "SF Pro Display", system-ui, sans-serif;
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
    """)
