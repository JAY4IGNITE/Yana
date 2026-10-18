# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for YANA Agent Windows executable."""

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

agent_dir = Path('.').resolve()

hidden_imports = (
    collect_submodules('uvicorn')
    + collect_submodules('fastapi')
    + collect_submodules('pydantic')
    + collect_submodules('pydantic_settings')
    + collect_submodules('aiosqlite')
    + collect_submodules('app')
)

# Normal planning uses the configured AI provider. The optional Laya classifier
# pulls in a full local training runtime, so bundle it only when requested.
excludes = ['tkinter', 'unittest', 'pytest']
if os.environ.get('YANA_BUNDLE_INTENT_ROUTER') != '1':
    excludes += ['laya', 'torch', 'transformers']

a = Analysis(
    ['app/main.py'],
    pathex=[str(agent_dir)],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='yana-agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # Tauri launches this with CREATE_NO_WINDOW and redirects stdout/stderr to agent.log.
    # Preserve streams for Uvicorn's logging setup.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
