"""Top-level page views for the Lanhu MCP Flet GUI.

Each page is a class taking an :class:`~lanhu_mcp.gui.state.AppContext` and
exposing ``build() -> ft.Control``. Dynamic pages also expose ``refresh()``.
"""

from .overview import OverviewPage
from .service import ServicePage
from .accounts import AccountsPage
from .projects import ProjectsPage
from .ide_tools import IdeToolsPage
from .logs import LogsPage

__all__ = [
    "OverviewPage",
    "ServicePage",
    "AccountsPage",
    "ProjectsPage",
    "IdeToolsPage",
    "LogsPage",
]
