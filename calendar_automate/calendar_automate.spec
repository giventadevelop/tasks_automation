# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['calendar_automate.py'],
    pathex=[],
    binaries=[],
     datas=[('property_files/calendar-automate-srvc-account-ref-file.json', '.'),
           ('property_files/calendar_api_properties.properties', '.'),
           ('hook.py', '.')],
    hiddenimports=['google.auth', 'google.auth.transport.requests', 'google.oauth2.credentials', 'google_auth_oauthlib.flow', 'googleapiclient.discovery'],
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
    a.binaries,
    a.datas,
    [],
    name='calendar_automate',
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
