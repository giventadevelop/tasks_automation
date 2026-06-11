"""Resolve config and bundle paths for script vs PyInstaller onefile."""
import os
import sys

PROPERTY_SUBDIR = 'property_files'
_PROPERTIES_FILE = 'calendar_api_properties.properties'


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bundle_root():
    """Where onefile assets are unpacked (Laundry_TryCents, etc.)."""
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
    return _repo_root()


def property_files_dir_candidates():
    """
    property_files directories to try, in order.
    Frozen: exe directory first (sidecar config), then PyInstaller temp unpack.
    """
    if not getattr(sys, 'frozen', False):
        yield os.path.join(_repo_root(), PROPERTY_SUBDIR)
        return
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    yield os.path.join(exe_dir, PROPERTY_SUBDIR)
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        yield os.path.join(meipass, PROPERTY_SUBDIR)


def resolved_property_files_dir():
    """
    Absolute path to the property_files directory that contains calendar_api_properties.properties,
    or the first candidate directory (for error messages / mkdir hints) if none exist yet.
    """
    marker = _PROPERTIES_FILE
    dirs = list(property_files_dir_candidates())
    for d in dirs:
        if os.path.isfile(os.path.join(d, marker)):
            return d
    return dirs[0]


def property_files_locations_hint():
    """Human-readable list of paths checked for calendar_api_properties.properties."""
    return "\n".join(os.path.join(d, _PROPERTIES_FILE) for d in property_files_dir_candidates())


def tasks_automation_root_candidates():
    """
    Directory that contains Laundry_TryCents and YouTube_Transcribe (repo root: tasks_automation).
    When frozen, does not use sys._MEIPASS — those tools live outside the onefile bundle.
    """
    if not getattr(sys, 'frozen', False):
        yield _repo_root()
        return
    env = (os.environ.get('TASKS_AUTOMATION_ROOT') or '').strip().rstrip('/\\')
    if env:
        yield env
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    yield os.path.join(exe_dir, 'tasks_automation')
    if os.name == 'nt':
        # Common checkout on this machine; override with TASKS_AUTOMATION_ROOT for portability.
        yield r'C:\E_Drive\project_workspace\tasks_automation'


def resolved_tasks_automation_root():
    """First candidate root that contains Laundry_TryCents\\run_laundry.bat, else first candidate."""
    marker = os.path.join('Laundry_TryCents', 'run_laundry.bat')
    roots = list(tasks_automation_root_candidates())
    for r in roots:
        if r and os.path.isfile(os.path.join(r, marker)):
            return r
    return roots[0] if roots else _repo_root()
