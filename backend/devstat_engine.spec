# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the DevStat offline analysis engine.
# Build:  cd backend && pyinstaller devstat_engine.spec --noconfirm
# Output: dist/DevStatEngine/DevStatEngine (exe on Windows, bin on mac/Linux)
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# uvicorn (and a few libs) import submodules by string; PyInstaller misses them.
hidden = list(collect_submodules("uvicorn")) + [
    "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.loops.asyncio", "uvicorn.loops.uvloop",
    "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl", "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.auto", "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on", "uvicorn.config", "uvicorn.workers", "uvicorn.server",
    "uvicorn.middleware.wsgi", "uvicorn.middleware.proxy_headers",
    "scipy.special.cython_special", "scipy.special.basic", "scipy.linalg.cython_lapack",
    "pandas._libs.tslibs.base", "pandas._libs.tslibs.nattype", "pandas._libs.tslibs.offsets",
    "sklearn.utils._cython_blas", "sklearn.utils._cython_errors",
]

a = Analysis(
    ["run_local.py"],
    pathex=["."],
    binaries=[],
    datas=collect_data_files("app")
    + collect_data_files("r")
    + [("static", "static")],  # bundle the built SPA so the engine serves it offline
    hiddenimports=hidden,
    hookspath=[],
    excludes=["torch", "tensorflow", "matplotlib", "PyQt5", "tkinter", "pytest", "scrapy"],
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
