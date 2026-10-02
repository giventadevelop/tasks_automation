# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for calendar + contacts automation.
# property_files: use repo root `tasks_automation/property_files/` (see calendar_api_README.md)
# or a local `property_files/` next to this spec; each file is included only if it exists.
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

_SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
_REPO_ROOT = os.path.abspath(os.path.join(_SPEC_DIR, '..'))
_LAUNDRY_DIR = os.path.join(_REPO_ROOT, 'Laundry_TryCents')

_PROPERTY_SEARCH_ROOTS = [
    os.path.join(_REPO_ROOT, 'property_files'),
    os.path.join(_SPEC_DIR, 'property_files'),
]
_PROPERTY_NAMES = [
    'calendar_api_properties.properties',
    'calendar-automate-srvc-account-ref-file.json',
    'google_desktop_oauth_client_contacts_api.json',
    'token.pickle',
]

_datas = []
for _name in _PROPERTY_NAMES:
    for _root in _PROPERTY_SEARCH_ROOTS:
        _src = os.path.join(_root, _name)
        if os.path.isfile(_src):
            _datas.append((_src, 'property_files'))
            break

_laundry_py = os.path.join(_LAUNDRY_DIR, 'laundry_automation.py')
if os.path.isfile(_laundry_py):
    # Optional legacy bundle path; GUI launches run_laundry.bat from resolved_tasks_automation_root().
    _datas.append((_laundry_py, 'Laundry_TryCents'))

# Google / Anthropic live inside a try/ in the entry script; pull full trees so the onefile
# bundle always contains them. Requires: pip install google-api-python-client google-auth-oauthlib ...
_hidden = [
    'calendar_app_paths',
    'prompt_library',
    'jproperties',
    'oauth_setup',
    'selenium',
    'selenium.webdriver',
    'selenium.webdriver.chrome.options',
    'selenium.webdriver.chrome.service',
    'selenium.webdriver.common.by',
    'selenium.webdriver.support.ui',
    'selenium.webdriver.support.expected_conditions',
    'selenium.common.exceptions',
    'selenium.webdriver.common.action_chains',
]
for _pkg in (
    'google',
    'googleapiclient',
    'google_auth_oauthlib',
    'anthropic',
    'tenacity',
    'httpx',
    'pillow_avif',
):
    try:
        _hidden.extend(collect_submodules(_pkg))
    except Exception:
        pass
_hidden = list(dict.fromkeys(_hidden))

try:
    _datas.extend(collect_data_files('googleapiclient'))
except Exception:
    pass
try:
    # Mozilla CA bundle for HTTPS (Google / Anthropic) when frozen as onefile exe.
    _datas.extend(collect_data_files('certifi'))
except Exception:
    pass
try:
    _datas.extend(collect_data_files('pillow_avif'))
except Exception:
    pass
try:
    from PyInstaller.utils.hooks import collect_dynamic_libs
    _binaries = collect_dynamic_libs('pillow_avif')
except Exception:
    _binaries = []
# Explicit Windows extension module for AVIF decode in onefile builds.
try:
    import pillow_avif as _pavif
    import glob as _glob
    _pavif_dir = os.path.dirname(_pavif.__file__)
    for _pyd in _glob.glob(os.path.join(_pavif_dir, '_avif*.pyd')):
        _binaries.append((_pyd, 'pillow_avif'))
    _avif_plugin = os.path.join(_pavif_dir, 'AvifImagePlugin.py')
    if os.path.isfile(_avif_plugin):
        _datas.append((_avif_plugin, 'pillow_avif'))
    _avif_init = os.path.join(_pavif_dir, '__init__.py')
    if os.path.isfile(_avif_init):
        _datas.append((_avif_init, 'pillow_avif'))
except Exception:
    pass
for _name in ('certifi', 'PIL', 'pillow_avif', 'pillow_avif.AvifImagePlugin'):
    if _name not in _hidden:
        _hidden.append(_name)

a = Analysis(
    ['google_calendar_and_contacts_automate.py'],
    pathex=[_SPEC_DIR, _LAUNDRY_DIR],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=_hidden,
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
