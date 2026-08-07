"""Packaged desktop entry point.

The repository contains a legacy Tkinter shell for compatibility and a newer
Flet shell used by the desktop app. Keeping command dispatch here makes the
PyInstaller entry unambiguous while preserving the existing helper/server
branches.
"""

from __future__ import annotations

import sys


def main() -> int:
    if "--login-helper" in sys.argv or "--server" in sys.argv:
        from lanhu_mcp_gui import run_login_helper_from_gui_args, run_server_from_gui_args

        if "--login-helper" in sys.argv:
            return int(run_login_helper_from_gui_args())
        return int(run_server_from_gui_args())

    try:
        from lanhu_mcp.gui import run
    except ImportError:
        from lanhu_mcp_gui import launch_gui

        launch_gui()
        return 0

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())