"""Diagnose every bundled font file one at a time.

Prints, per file: name, size in bytes, first four bytes in hex, the id returned
by QFontDatabase.addApplicationFont (-1 means failure), the families it
registers, and any qt.qpa.fonts message it triggers.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"


def main() -> int:
    app = QApplication.instance() or QApplication([sys.argv[0]])
    _ = app

    messages: list[str] = []

    def handler(mode: object, context: object, message: str) -> None:
        text = str(message)
        if "font" in text.lower() or "qt.qpa.fonts" in text.lower():
            messages.append(text)

    # Route Qt's own warnings into our list so we can attribute them per file.
    from PySide6.QtCore import qInstallMessageHandler

    qInstallMessageHandler(handler)

    files = sorted(FONT_DIR.glob("*.ttf"))
    print(f"Scanning {len(files)} font files in {FONT_DIR}\n")
    failures: list[str] = []
    for path in files:
        data = path.read_bytes()
        header = data[:4].hex()
        print(f"file            : {path.name}")
        print(f"size (bytes)    : {len(data)}")
        print(f"first 4 bytes   : {header}")
        before = len(messages)
        font_id = QFontDatabase.addApplicationFont(str(path))
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        print(f"addApplicationFont id : {font_id}")
        print(f"families             : {list(families)}")
        new_msgs = messages[before:]
        print(f"qt.qpa.fonts messages : {new_msgs if new_msgs else '[]'}")
        if font_id < 0 or not families:
            failures.append(path.name)
        print()

    print(f"FAILING FILES ({len(failures)}): {failures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
