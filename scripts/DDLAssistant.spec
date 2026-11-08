# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import sys
ROOT = Path(SPECPATH).parent

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('windows_toasts')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('winrt')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['../launcher.py'],
    pathex=[ROOT.as_posix()],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / 'scripts/frozen_logging.py')],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick'],
    noarchive=False,
    optimize=0,
)
# Qt on Windows 11 uses the system ICU API. An unrelated Poppler ICU can
# be found on PATH during analysis, but it exports versioned symbols and
# cannot replace Windows' icuuc.dll. Never bundle that foreign DLL.
def native_binary(entry):
    destination, source, kind = entry
    name = Path(destination).name.lower()
    if name.startswith(('api-ms-win-', 'ext-ms-win-')) or name == 'icuuc.dll' or name.startswith('icudt'):
        return None  # Windows 11 supplies these system contracts.
    if name in ('libssl-3-x64.dll', 'libcrypto-3-x64.dll'):
        python_copy = Path(sys.base_prefix) / 'DLLs' / name
        if python_copy.exists():
            source = str(python_copy)
    return destination, source, kind

a.binaries = [value for entry in a.binaries if (value := native_binary(entry)) is not None]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DDLAssistant',
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
