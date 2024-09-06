# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import shutil

block_cipher = None

# Get the absolute path of the spec file's directory
spec_dir = os.path.dirname(os.path.abspath(SPEC))

# Clean the output directory
output_dir = os.path.join(spec_dir, 'dist', 'calendar_automate')
if os.path.exists(output_dir):
    shutil.rmtree(output_dir)

a = Analysis(
    [os.path.join(spec_dir, 'calendar_automate.py')],
    pathex=[spec_dir],
    binaries=[],
    datas=[
        (os.path.join(spec_dir, 'calendar-automate-srvc-account-ref-file.json'), '.'),
        (os.path.join(spec_dir, 'calendar_api_properties'), 'calendar_api_properties'),
    ],
    hiddenimports=[
        'google.auth',
        'google.auth.transport',
        'google.auth.transport.requests',
        'google.oauth2.credentials',
        'googleapiclient.discovery',
        'googleapiclient.http',
        'google_auth_oauthlib',
        'google.oauth2.service_account',
        'google.oauth2',
        'google.auth.exceptions',
        'google.auth.transport.urllib3',
        'google.auth.crypt',
        'google.auth.jwt',
        'google_auth_httplib2',
        'httplib2',
        'oauth2client',
        'pyasn1',
        'pyasn1_modules',
        'rsa',
        'six',
        'uritemplate',
        'setuptools',
        'pkg_resources',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(spec_dir, 'hook.py')],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Add data files from calendar_api_properties directory
calendar_api_properties_dir = os.path.join(spec_dir, 'calendar_api_properties')
for root, dirs, files in os.walk(calendar_api_properties_dir):
    for file in files:
        file_path = os.path.join(root, file)
        rel_dir = os.path.relpath(root, calendar_api_properties_dir)
        a.datas += [(os.path.join('calendar_api_properties', rel_dir, file), file_path, 'DATA')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='calendar_automate',
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
    icon=os.path.join(spec_dir, 'calendar_icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='calendar_automate',
)
