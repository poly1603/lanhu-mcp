"""Flet GUI package for Lanhu MCP.

This package contains the modern Flet-based desktop UI that replaces the
legacy Tkinter shell. It is organised into:

- ``theme``      : design tokens (colors, spacing, radius, fonts) + Flet themes
- ``components`` : reusable Flet controls (sidebar, cards, badges, toasts, ...)
- ``pages``      : top-level views (overview, service, accounts, projects, ...)
- ``app``        : application shell, navigation/routing and async bridging

All business logic lives in :mod:`lanhu_mcp.core` and
:mod:`lanhu_mcp.services`; this package only renders UI and dispatches events.
"""


def run() -> None:
    """Launch the Flet desktop app (lazy import so ``flet`` stays optional)."""
    from .app import run as _run

    _run()


__all__ = ["theme", "run"]
