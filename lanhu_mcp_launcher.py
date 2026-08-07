"""Packaged desktop entry point for the Flet application and MCP branches."""

from __future__ import annotations

import sys


def main() -> int:
    if "--login-helper" in sys.argv or "--server" in sys.argv:
        from lanhu_mcp.runtime import run_login_helper_from_gui_args, run_server_from_gui_args

        if "--login-helper" in sys.argv:
            return int(run_login_helper_from_gui_args())
        return int(run_server_from_gui_args())

    from lanhu_mcp.gui import run

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())