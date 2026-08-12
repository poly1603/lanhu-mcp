"""User-invoked cleanup for disposable desktop data.

The cleanup boundary is deliberately narrow: logs, recent-project behavior,
avatar files, close-window preference, and in-memory discovery caches are
disposable. Account cookies, account profiles, project configuration, and IDE
MCP configuration are user data and are never removed here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .paths import AVATAR_CACHE_DIR, WINDOW_PREFERENCES_FILE
from . import projects as projects_core

__all__ = ["clear_local_cache"]


def _clear_files(directory: Path) -> int:
    """Remove files in one known cache directory without following broad paths."""
    if not directory.exists() or not directory.is_dir():
        return 0
    removed = 0
    try:
        children = list(directory.iterdir())
    except OSError:
        return 0
    for child in children:
        if not child.is_file():
            continue
        try:
            child.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def clear_local_cache(ctx: Optional[object] = None) -> dict[str, int | bool]:
    """Clear disposable local state and return a small cleanup summary.

    ``ctx`` is optional so the operation remains easy to test. When supplied,
    its persistent log stream is truncated through the normal context API so
    an already-open log handler remains valid on Windows.
    """
    log_count = 0
    if ctx is not None:
        try:
            log_count = len(ctx.get_logs())
            ctx.clear_logs()
        except (AttributeError, TypeError):
            log_count = 0

    recent_count = projects_core.clear_recent_projects()

    close_behavior_cleared = False
    try:
        if WINDOW_PREFERENCES_FILE.exists():
            WINDOW_PREFERENCES_FILE.unlink()
            close_behavior_cleared = True
    except OSError:
        pass

    avatar_count = _clear_files(AVATAR_CACHE_DIR)

    # These are process-local caches only; the next render/request will lazily
    # rebuild them and no account/project data is touched.
    try:
        from .config import _metadata_cache

        _metadata_cache.clear()
    except (ImportError, AttributeError):
        pass
    try:
        from ..services.tools_registry import clear_tool_discovery_cache

        clear_tool_discovery_cache()
    except (ImportError, AttributeError):
        pass

    return {
        "logs": log_count,
        "recent_projects": recent_count,
        "avatars": avatar_count,
        "close_behavior": close_behavior_cleared,
    }
