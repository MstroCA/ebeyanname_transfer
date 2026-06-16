# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — Beyanname Transfer.

Platform bağımsız: Windows'ta .exe, macOS'ta .app, Linux'ta binary üretir.

Build:
    pip install -r requirements.txt -r build-requirements.txt
    pyinstaller --noconfirm build.spec
"""

import sys

block_cipher = None

# Platforma göre ikon
icon_file = None
if sys.platform.startswith("win"):
    icon_file = "assets/app.ico"
elif sys.platform == "darwin":
    icon_file = "assets/app.icns" if __import__("os").path.exists("assets/app.icns") else None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets/app.ico', 'assets'),
        ('assets/logo.png', 'assets'),
    ],
    hiddenimports=[
        'psycopg2',
        'PySide6.QtSvg',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtNetwork',
        'PySide6.Qt3DCore', 'PySide6.QtWebEngineCore', 'PySide6.QtMultimedia',
        'PySide6.QtPdf', 'PySide6.QtCharts', 'PySide6.QtDataVisualization',
        'PySide6.QtBluetooth', 'PySide6.QtPositioning', 'PySide6.QtSensors',
        'PySide6.QtSerialPort', 'PySide6.QtTest', 'PySide6.QtWebSockets',
        'tkinter', 'unittest', 'pydoc',
    ],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='BeyannameTransfer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=icon_file,
)

# macOS app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name='BeyannameTransfer.app',
        icon=icon_file,
        bundle_identifier='tr.gov.gib.beyanname-transfer',
        info_plist={
            'CFBundleShortVersionString': '2.0.0',
            'NSHighResolutionCapable': 'True',
        },
    )
