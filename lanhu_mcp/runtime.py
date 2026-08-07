"""Non-UI runtime branches for the packaged Lanhu MCP application."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

from .core.paths import DATA_DIR, flog


def run_login_helper_from_gui_args() -> int:
    """Run the browser login helper from the packaged application's child process."""
    result_file = Path(sys.argv[2]) if len(sys.argv) > 2 else DATA_DIR / ".login_result.json"
    flog(f"Login helper branch started: args={sys.argv}")
    try:
        from lanhu_login_helper import main as login_main

        sys.argv = [sys.argv[0]] + sys.argv[2:]
        return int(login_main())
    except Exception as error:  # noqa: BLE001 - this process must return structured failure data
        flog(f"Login helper branch failed: {error}", "error")
        flog(traceback.format_exc(), "error")
        try:
            result_file.parent.mkdir(parents=True, exist_ok=True)
            result_file.write_text(
                json.dumps(
                    {
                        "status": "error",
                        "cookies": "",
                        "user": {},
                        "storage": {},
                        "url": "",
                        "error": f"Login helper failed to start: {error}",
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass
        return 1


def run_server_from_gui_args() -> int:
    """Run the embedded MCP server without importing any desktop UI code."""
    try:
        sys.argv = [sys.argv[0]] + [arg for arg in sys.argv[1:] if arg != "--server"]
        flog("Embedded MCP server branch started")
        import lanhu_mcp_server

        try:
            __import__("lanhu_mcp.server")
            flog("Loaded high-fidelity design tools")
        except Exception as import_error:  # noqa: BLE001 - extension tools are additive
            flog(f"Unable to load high-fidelity design tools: {import_error}", "warning")

        transport = os.getenv("MCP_TRANSPORT", "http").lower()
        if transport == "stdio":
            lanhu_mcp_server.mcp.run(transport="stdio")
        else:
            host = os.getenv("SERVER_HOST", "0.0.0.0")
            port = int(os.getenv("SERVER_PORT", "8000"))
            flog(f"MCP HTTP server listening on {host}:{port}/mcp")
            lanhu_mcp_server.mcp.run(transport="http", path="/mcp", host=host, port=port)
        return 0
    except Exception as error:  # noqa: BLE001 - the child process must report a concrete exit status
        flog(f"Embedded MCP server branch failed: {error}", "error")
        flog(traceback.format_exc(), "error")
        return 1
