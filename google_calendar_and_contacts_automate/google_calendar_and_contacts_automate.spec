# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['google_calendar_and_contacts_automate.py'],
    pathex=[
        'C:/Users/gain/git/python/tasks_automation/google_calendar_and_contacts_automate',
        'C:/Users/gain/git/python/tasks_automation/Laundry_TryCents'
    ],
    binaries=[],
    datas=[
        ('property_files/calendar_api_properties.properties', 'property_files'),
        ('property_files/calendar-automate-srvc-account-ref-file.json', 'property_files'),
        ('property_files/google_desktop_oauth_client_contacts_api.json', 'property_files'),
        ('property_files/token.pickle', 'property_files'),
        ('../Laundry_TryCents/laundry_automation.py', '.')
    ],
    hiddenimports=[
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.common.exceptions',
        'selenium.webdriver.common.action_chains'
    ],
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
    name='google_calendar_and_contacts_automate',
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
