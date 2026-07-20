# -*- mode: python ; coding: utf-8 -*-
import os
import customtkinter
from PyInstaller.utils.hooks import collect_all

CUSTOMTKINTER_PATH = os.path.dirname(customtkinter.__file__)

# Empacota o pacote playwright completo, incluindo o driver Node
# (driver/node.exe + driver/package/cli.js) usado por `playwright install`
# na primeira execução. Sem isso, o driver não é encontrado no .exe.
pw_datas, pw_binaries, pw_hiddenimports = collect_all('playwright')

# Empacota o cacert.pem do certifi (fallback de CAs para a verificação TLS do
# updater). Sem uma lista de CAs, o OpenSSL do .exe falha com "unable to get
# local issuer certificate" em máquinas cujo store do Windows está incompleto.
cf_datas, cf_binaries, cf_hiddenimports = collect_all('certifi')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=pw_binaries + cf_binaries,
    datas=[
        (CUSTOMTKINTER_PATH, 'customtkinter'),
        ('assets/icon.ico', 'assets'),
        *pw_datas,
        *cf_datas,
    ],
    hiddenimports=[
        'customtkinter',
        'darkdetect',
        'PIL',
        'PIL._tkinter_finder',
        'pandas',
        'openpyxl',
        'playwright',
        'playwright.sync_api',
        'certifi',
        'truststore',
        *pw_hiddenimports,
        *cf_hiddenimports,
    ],
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
    a.binaries,
    a.datas,
    [],
    name='Saffar',
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
    icon='assets/icon.ico',
)
