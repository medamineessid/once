"""One-off pywinauto API surface inspection (not part of the test suite)."""

from pywinauto.controls.uiawrapper import UIAWrapper

print("UIAWrapper methods:")
print([m for m in dir(UIAWrapper) if not m.startswith("_")])
