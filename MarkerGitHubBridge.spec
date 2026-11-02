# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

project_root = Path(SPECPATH)
tk_runtime = project_root / ".tk-runtime"
os.environ["TCL_LIBRARY"] = str(tk_runtime / "tcl_library")
os.environ["TK_LIBRARY"] = str(tk_runtime / "tk_library")

a = Analysis(
    [str(project_root / "sync.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / ".env.example"), "."),
        (str(tk_runtime), "tk_runtime"),
    ],
    hiddenimports=["dotenv", "requests", "tkinter", "tkinter.ttk"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MarkerGitHubBridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
