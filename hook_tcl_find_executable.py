"""PyInstaller 运行时 Tcl/Tk 初始化补丁。"""

import ctypes
import os
import sys
from pathlib import Path


def _first_existing_path(candidates: list[Path]) -> Path | None:
    """返回第一个存在的候选路径。"""
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _bootstrap_tcl_tk() -> None:
    """让打包后的 Tkinter 能找到 Tcl/Tk 脚本和宿主 exe。"""
    if sys.platform != "win32":
        return

    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    app_dir = Path(sys.executable).parent

    try:
        os.add_dll_directory(str(bundle_dir))
    except (AttributeError, OSError):
        pass

    tcl_dll = _first_existing_path([
        bundle_dir / "tcl86t.dll",
        app_dir / "tcl86t.dll",
    ])
    if tcl_dll:
        try:
            tcl = ctypes.CDLL(str(tcl_dll))
            tcl.Tcl_FindExecutable.argtypes = [ctypes.c_wchar_p]
            tcl.Tcl_FindExecutable(sys.executable)
        except Exception:
            pass

    tcl_dir = _first_existing_path([
        bundle_dir / "_tcl_data",
        app_dir / "_tcl_data",
    ])
    tk_dir = _first_existing_path([
        bundle_dir / "_tk_data",
        app_dir / "_tk_data",
    ])
    if tcl_dir:
        os.environ["TCL_LIBRARY"] = str(tcl_dir)
    if tk_dir:
        os.environ["TK_LIBRARY"] = str(tk_dir)


_bootstrap_tcl_tk()
