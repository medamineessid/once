"""Read-only probe of an existing Notepad window's UI Automation tree."""

import sys

from pywinauto import Desktop
from pywinauto.uia_defines import NoPatternInterfaceError

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def has_pattern(wrapper, name: str) -> str:
    pattern = getattr(wrapper, f"iface_{name}", None)
    try:
        return "yes" if pattern() is not None else "no"
    except NoPatternInterfaceError:
        return "no-pattern"
    except Exception as error:  # noqa: BLE001 - probe only
        return f"error {error}"

desktop = Desktop(backend="uia")
candidates = [
    w
    for w in desktop.windows()
    if getattr(w.element_info, "class_name", None) == "Notepad"
]
print("notepad top-levels:", len(candidates))
for wrapper in candidates:
    info = wrapper.element_info
    print("WINDOW pid=", getattr(info, "process_id", None), "name=", repr(getattr(info, "name", None)))
    for child in wrapper.descendants():
        cinfo = child.element_info
        control = getattr(cinfo, "control_type", None)
        if control is None:
            continue
        if control in ("Button", "MenuBar", "Pane", "TitleBar", "Custom"):
            continue
        value = None
        try:
            has_value = has_pattern(child, "value")
        except Exception as error:  # noqa: BLE001 - probe only
            has_value = f"error {error}"
        print(
            "  ctl=",
            control,
            "aid=",
            repr(getattr(cinfo, "automation_id", None)),
            "cls=",
            repr(getattr(cinfo, "class_name", None)),
            "name=",
            repr((getattr(cinfo, "name", None) or "")[:30]),
            "value_pattern=",
            has_value,
        )
