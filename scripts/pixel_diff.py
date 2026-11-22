"""Report the percentage of differing pixels between two images."""

from __future__ import annotations

import sys

from PySide6.QtGui import QImage


def load(path: str) -> QImage:
    image = QImage(path)
    if image.isNull():
        raise SystemExit(f"Cannot read image: {path}")
    return image.convertToFormat(QImage.Format.Format_RGBA8888)


def main(before_path: str, after_path: str) -> int:
    before = load(before_path)
    after = load(after_path)
    if before.size() != after.size():
        before = before.scaled(after.size())
    width, height = after.width(), after.height()
    total = width * height
    differing = 0
    for y in range(height):
        for x in range(width):
            if before.pixel(x, y) != after.pixel(x, y):
                differing += 1
    percentage = 100.0 * differing / total if total else 0.0
    print(f"before: {before_path} ({before.width()}x{before.height()})")
    print(f"after : {after_path} ({after.width()}x{after.height()})")
    print(f"differing pixels: {differing} / {total} = {percentage:.1f}%")
    if percentage < 30.0:
        print("design not visibly changed")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: pixel_diff.py BEFORE AFTER")
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
