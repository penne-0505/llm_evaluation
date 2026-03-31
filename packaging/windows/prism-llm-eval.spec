# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH).resolve().parents[1]
hiddenimports = [
    name for name in collect_submodules("google.genai") if ".tests" not in name
]

datas = [
    (str(project_root / "frontend" / "dist"), "frontend/dist"),
    (str(project_root / "rubrics"), "rubrics"),
    (str(project_root / "prompts"), "prompts"),
    (str(project_root / "judge_system_prompt.md"), "."),
]

bundled_model_cache = project_root / "models" / "models.json"
if bundled_model_cache.exists():
    datas.append((str(bundled_model_cache), "models"))


a = Analysis(
    [str(project_root / "launcher.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="prism-llm-eval",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
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
    name="prism-llm-eval",
)
