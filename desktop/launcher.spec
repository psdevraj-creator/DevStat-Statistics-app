# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the DevStat Desktop Edition launcher (Chrome app-mode).
# Builds a single, console-less executable that:
#   1. starts the bundled analysis engine (DEVSTAT_OFFLINE=1) on 127.0.0.1:8210
#   2. waits for /api/health
#   3. opens Chrome/Edge/Safari in --app mode (no address bar)
# Usage:  python -m PyInstaller launcher.spec --noconfirm

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DevStatDesktopLauncher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
