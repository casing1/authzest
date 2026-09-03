# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

project_root = Path(SPECPATH)
frontend_dist = project_root / "frontend" / "dist"
datas = copy_metadata("authzest")
if frontend_dist.is_dir():
    datas.append((str(frontend_dist), "frontend/dist"))

analysis = Analysis(
    [str(project_root / "src" / "authzest" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["authzest.api.app"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="authzest",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
