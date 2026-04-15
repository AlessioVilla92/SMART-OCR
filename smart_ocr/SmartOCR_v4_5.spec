# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = [
    'sklearn.utils._cython_blas', 'sklearn.neighbors._typedefs',
    'sklearn.neighbors._quad_tree', 'sklearn.tree._utils',
    'sklearn.utils._typedefs',
]
hiddenimports += collect_submodules('onnxruntime')
hiddenimports += collect_submodules('cv2')
hiddenimports += collect_submodules('openpyxl')
hiddenimports += collect_submodules('reportlab')


a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('models/svm_classifier.pkl', 'models'),
        ('models/yolo_cbcl.onnx', 'models'),
        ('models/training_report.json', 'models'),
        ('models/training_report_yolo.json', 'models'),
        ('resources', 'resources'),
    ],
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
    name='SmartOCR_v4_5',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources\\icons\\app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SmartOCR_v4_5',
)
