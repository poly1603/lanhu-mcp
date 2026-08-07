"""Compatibility facade for the modern Flet Lanhu MCP application.

The former 166 KB desktop interface was retired.  This module intentionally
contains no desktop widgets; it keeps the historical helper imports working
for scripts while directing the GUI entry point to :mod:`lanhu_mcp.gui`.
"""

from __future__ import annotations

import urllib.request

from lanhu_mcp.gui import run as _run_flet
from lanhu_mcp.runtime import run_login_helper_from_gui_args, run_server_from_gui_args
from lanhu_mcp.core.paths import (
    APP_DIR,
    DATA_DIR,
    ENV_FILE,
    COOKIE_FILE,
    ACCOUNTS_FILE,
    PROJECTS_FILE,
    LOG_FILE,
    DEFAULT_LANHU_LOGIN_URL,
    AVATAR_MAX_BYTES,
    ensure_writable_data_dir,
    flog,
    is_gui_smoke_mode,
    should_show_native_error_dialog,
    first_existing_path,
    now_text,
    is_port_in_use,
    validate_port,
    find_server_exe,
    find_server_dir,
    app_runtime_label,
)
from lanhu_mcp.core.accounts import *  # noqa: F403 - compatibility exports
from lanhu_mcp.core.projects import *  # noqa: F403 - compatibility exports
from lanhu_mcp.core.avatar import avatar_cache_path, download_avatar
from lanhu_mcp.services.tools_registry import *  # noqa: F403 - compatibility exports
from lanhu_mcp.services.lanhu_api import *  # noqa: F403 - compatibility exports
from lanhu_mcp.services.ide_config import IDE_REGISTRY, IDEManager
from lanhu_mcp.services.service_manager import (
    ServiceManager,
    build_server_start_command,
    find_server_script,
)


COLORS = {
    "bg": "#F6F8FB",
    "sidebar": "#101828",
    "card": "#FFFFFF",
    "primary": "#2563EB",
    "success": "#12B76A",
    "danger": "#F04438",
    "text_primary": "#101828",
    "text_secondary": "#667085",
    "border": "#D0D5DD",
    "border_light": "#EAECF0",
}
SPACING = {"0": 0, "1": 4, "2": 8, "3": 12, "4": 16}
FONT = {"family": "Segoe UI", "mono": "Cascadia Code", "sizes": {"sm": 12, "base": 14, "lg": 16}}
ANIMATION = {"fast": 100, "normal": 200, "slow": 300}
ANIMATION_INTERVALS = {"sidebar_pulse": 180, "page_transition": 120}


def animation_interval_ms(animation_name: str) -> int:
    return int(ANIMATION_INTERVALS.get(animation_name, ANIMATION["normal"]))


def should_run_sidebar_pulse(window_state: str, has_focus: bool) -> bool:
    return bool(has_focus and window_state in ("normal", "zoomed"))


def project_rows_signature(projects: list[dict]) -> tuple[tuple[str, ...], ...]:
    fields = ("id", "team_id", "name", "type", "updated_at", "team_name", "owner_name", "source", "url")
    return tuple(tuple(str(project.get(field) or "") for field in fields) for project in projects)


def account_rows_signature(accounts: list[dict], active_id: str) -> tuple[tuple[str, ...], ...]:
    fields = (
        "id", "name", "email", "mobile", "username", "nickname", "avatar", "company", "team", "team_name",
        "role", "updated_at", "source_url",
    )
    rows = []
    for account in accounts:
        cookie = str(account.get("cookie") or "")
        fingerprint = str(account.get("cookie_fingerprint") or cookie_fingerprint(cookie) or "")
        rows.append(tuple([str(account.get(field) or "") for field in fields] + [fingerprint, str(len(cookie)), "1" if account.get("id") == active_id else "0"]))
    return tuple(rows)


def launch_gui() -> None:
    """Launch only the current Flet interface."""
    _run_flet()


def create_gui() -> None:
    """Backward-compatible alias for the modern Flet entry point."""
    launch_gui()


if __name__ == "__main__":
    import sys

    if "--login-helper" in sys.argv:
        raise SystemExit(run_login_helper_from_gui_args())
    if "--server" in sys.argv:
        raise SystemExit(run_server_from_gui_args())
    launch_gui()
