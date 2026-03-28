# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.hooks import copy_metadata

datas = [('/Users/ale/Desktop/GitHub/SMART OCR/smart_ocr/desktop_app.py', '.'), ('templates', 'templates'), ('core', 'core'), ('training', 'training'), ('style.py', '.'), ('app.py', '.'), ('.streamlit', '.streamlit'), ('models', 'models')]
binaries = []
hiddenimports = ['pathlib.Path', 'socket', 'subprocess', 'sys', 'threading', 'time', 'webbrowser', 'webview']
datas += copy_metadata('streamlit')
tmp_ret = collect_all('streamlit')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['/var/folders/q0/v626gwf147n552ws3p79mzgw0000gn/T/tmpkx7kk49d.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='SmartOCR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name='SmartOCR',
)
