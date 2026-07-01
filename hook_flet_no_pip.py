"""
LanhuMCP runtime hook: provide `exit`/`quit` in builtins and no-op flet.utils.pip
helpers so the frozen EXE doesn't try to invoke `pip install` (which fails in
frozen mode and then calls `exit(1)`, raising NameError on the missing builtin).
"""
import builtins
import sys


def _noop(*args, **kwargs):
    return None


# 1. Inject `exit` / `quit` into builtins (they're normally only available in
#    interactive mode via site.py; PyInstaller's bootloader skips site.py in
#    some cases and the absence breaks any error handler that calls exit()).
if not hasattr(builtins, "exit"):
    builtins.exit = sys.exit
if not hasattr(builtins, "quit"):
    builtins.quit = sys.exit

# 2. Patch flet.utils.pip before flet.app imports it. In a frozen EXE we never
#    need flet to spawn `python -m pip install` (the dependencies are already
#    bundled). The three ensure_* functions call `exit(1)` on failure which
#    would otherwise terminate the GUI process before the user even sees it.
try:
    import flet.utils.pip as _flet_pip
    _flet_pip.install_flet_package = _noop
    _flet_pip.ensure_flet_desktop_package_installed = _noop
    _flet_pip.ensure_flet_web_package_installed = _noop
    _flet_pip.ensure_flet_cli_package_installed = _noop
except Exception:
    # flet may not even be importable; that's fine.
    pass
