# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

# Get the absolute path of the current directory
current_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(['calendar_automate.py'],
             pathex=[current_dir],
             binaries=[],
             datas=[
                 (os.path.join(current_dir, 'calendar-automate-srvc-account-ref-file.json'), '.'),
                 (os.path.join(current_dir, 'calendar_api_properties'), 'calendar_api_properties')
             ],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='calendar_automate',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True,
          icon=os.path.join(current_dir, 'calendar_icon.ico'))

# Collect all files in one directory
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='calendar_automate')
