# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
   ['calendar_automate.py'],
pathex=['C:/Users/gain/git/python/tasks_automation/calendar_automate'],
binaries=[],
datas=[('C:/Users/gain/git/python/tasks_automation/calendar_automate/property_files/calendar-automate-srvc-account-ref-file.json','property_files'), ('C:/Users/gain/git/python/tasks_automation/calendar_automate/property_files/calendar_api_properties.properties','property_files')],
hiddenimports=[],
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
