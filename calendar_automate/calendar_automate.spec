# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['calendar_automate.py'],
             pathex=['C:\\Users\\gain\\git\\python\\tasks_automation\\calendar_automate'],
             binaries=[],
             datas=[('calendar-automate-srvc-account-ref-file.json', '.'),
                    ('calendar_api_properties', 'calendar_api_properties')],
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
          console=True )
