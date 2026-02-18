# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import copy_metadata


spec_dir = Path(globals().get("SPECPATH", Path.cwd()))
project_root = spec_dir.resolve().parent
if sys.platform.startswith("win"):
    icon_path = project_root / "packaging" / "assets" / "app-icon.ico"
else:
    icon_path = project_root / "packaging" / "assets" / "app-icon.png"
datas = [
    (str(project_root / "rubrics"), "rubrics"),
    (str(project_root / "prompts"), "prompts"),
    (str(project_root / "judge_system_prompt.md"), "."),
    (str(project_root / "app.py"), "."),
]
datas += copy_metadata("streamlit")

block_cipher = None


a = Analysis(
    [str(project_root / "scripts" / "streamlit_entrypoint.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="prism-llm-eval",
    icon=str(icon_path),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
