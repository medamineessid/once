# -*- mode: python ; coding: utf-8 -*-
"""Windows one-folder bundle for Once, built with PyInstaller from this spec.

Build (from the project root, inside a Windows virtual environment):
    python -m PyInstaller once.spec --noconfirm --clean

The result is dist\\Once\\Once.exe. It needs no Python installation. User data
stays in %LOCALAPPDATA%\\Once at runtime and is never written into the bundle
directory, so installing or upgrading never touches existing user data.

Hidden imports are required because pynput, mss, pywinauto, win32api, and
win32cred are imported lazily inside functions, which the module graph
cannot see statically.
"""

hiddenimports = [
    "pynput",
    "mss",
    "pywinauto",
    "win32api",
    "win32cred",
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # never bundle development-only tooling into the release artifact
        "pytest",
        "pytest_qt",
        "test",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Once",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # release build: no console window visible to the user
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Once",
)
