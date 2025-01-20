# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['google_calendar_and_contacts_automate.py'],
    pathex=[
        'C:/Users/gain/git/python/tasks_automation/google_calendar_and_contacts_automate',
        'C:/Users/gain/git/python/tasks_automation/Laundry_TryCents'
    ],
    binaries=[],
    datas=[
        # Property files - using relative paths and correct target directory
        ('property_files/calendar_api_properties.properties', 'property_files'),
        ('property_files/calendar-automate-srvc-account-ref-file.json', 'property_files'),
        ('property_files/google_desktop_oauth_client_contacts_api.json', 'property_files'),
        ('property_files/token.pickle', 'property_files'),
        # Laundry automation files
        ('../Laundry_TryCents/laundry_automation.py', '.')
    ],
    hiddenimports=[
        'google.auth',
        'google.auth.transport.requests',
        'google_auth_oauthlib.flow',
        'googleapiclient.discovery',
        'anthropic',
        'jproperties',
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.edge.options',
        'selenium.webdriver.edge.service',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.common.exceptions',
        'oauth_setup'  # Add oauth_setup module
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

# Add oauth_setup.py to the analysis
a.datas += [('oauth_setup.py', 'oauth_setup.py', 'DATA')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='google_calendar_and_contacts_automate',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
