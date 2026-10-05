# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Desktop AI Pet — Asha.

Build (from the project root, i.e. one directory above this file):
    Windows:  pyinstaller packaging/asha.spec
    Linux:    pyinstaller packaging/asha.spec

Produces a single-folder build under dist/Asha/ containing the Asha
executable plus the `assets/` folder it needs at runtime. A single-file
(--onefile) build is intentionally avoided: Asha reads/writes
`database/asha_memory.db` and `logs/asha.log` next to the executable,
which is simplest to reason about with a folder build.
"""

import sys
from pathlib import Path

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).resolve().parent

added_files = [
    (str(PROJECT_ROOT / "assets"), "assets"),
]

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        "ai.openai_provider",
        "ai.ollama_provider",
        "voice.tts_engine",
        "voice.stt_engine",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Asha",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # no terminal window on Windows; background app
    icon=str(PROJECT_ROOT / "assets" / "icons" / "tray_icon.ico") if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Asha",
)
