# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the DevStat offline analysis engine.
# Build:  cd backend && pyinstaller devstat_engine.spec --noconfirm
# Output: dist/DevStatEngine/DevStatEngine.exe  (set DEVSTAT_ENGINE_EXE to this)
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hidden = (
    collect_submodules("uvicorn")
    + collect_submodules("statsmodels")
    + collect_submodules("lifelines")
    + collect_submodules("sklearn")
    + collect_submodules("scipy")
    + collect_submodules("pandas")
    + collect_submodules("factor_analyzer")
    + collect_submodules("app")
    + collect_submodules("r")
)

a = Analysis(
    ["run_local.py"],
    pathex=["."],
    binaries=[],
    datas=collect_data_files("app") + collect_data_files("r"),
    hiddenimports=hidden,
    hookspath=[],
    excludes=["torch", "tensorflow", "matplotlib", "PyQt5", "tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DevStatEngine",
    console=True,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="DevStatEngine")
