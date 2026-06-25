"""Reusable Flet controls and helpers (Flet 0.28.x API).

These helpers wrap common layout patterns (cards, badges, buttons, empty
states, metric tiles, toasts) using the design tokens from
:mod:`lanhu_mcp.gui.theme`. They take an explicit ``palette`` argument so they
work in both light and dark mode.
"""

from __future__ import annotations

import threading
import traceback
from typing import Callable, List, Optional

import flet as ft

from .. import theme
from ..theme import Palette


# ---------------------------------------------------------------------------
# Async bridge
# ---------------------------------------------------------------------------
def run_in_background(
    page: ft.Page,
    work: Callable[[], object],
    on_done: Optional[Callable[[object], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
) -> threading.Thread:
    """Run ``work`` on a daemon thread, then dispatch the result on the page.

    Flet event handlers run on UI worker threads; long/blocking work (network,
    disk) must not block them. This helper runs ``work()`` off-thread and then
    invokes ``on_done(result)`` (or ``on_error(exc)``) and calls
    ``page.update()`` so the UI refreshes.
    """

    def runner() -> None:
        try:
            result = work()
        except Exception as exc:  # noqa: BLE001 - surfaced to on_error
            traceback.print_exc()
            if on_error is not None:
                try:
                    on_error(exc)
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
            try:
                page.update()
            except Exception:  # noqa: BLE001
                pass
            return
        if on_done is not None:
            try:
                on_done(result)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        try:
            page.update()
        except Exception:  # noqa: BLE001
            pass

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# Cards & containers
# ---------------------------------------------------------------------------
def card(
    palette: Palette,
    content: ft.Control,
    *,
    padding: int = 20,
    expand: bool = False,
) -> ft.Container:
    """A white surface card with subtle border and rounded corners."""
    return ft.Container(
        content=content,
        bgcolor=palette.card,
        border=ft.border.all(1, palette.border_light),
        border_radius=theme.radius("lg"),
        padding=padding,
        expand=expand,
    )


def section_title(palette: Palette, text: str, subtitle: str = "") -> ft.Control:
    children: List[ft.Control] = [
        ft.Text(
            text,
            size=theme.font_size("xl"),
            weight=theme.WEIGHT_SEMIBOLD,
            color=palette.text_primary,
        )
    ]
    if subtitle:
        children.append(
            ft.Text(subtitle, size=theme.font_size("sm"), color=palette.text_secondary)
        )
    return ft.Column(children, spacing=theme.space("1"))


def metric_tile(
    palette: Palette,
    label: str,
    value: str,
    *,
    icon: Optional[str] = None,
    accent: Optional[str] = None,
) -> ft.Container:
    """A small KPI tile for the overview page."""
    accent_color = accent or palette.primary
    head: List[ft.Control] = []
    if icon:
        head.append(ft.Icon(icon, size=18, color=accent_color))
    head.append(
        ft.Text(label, size=theme.font_size("sm"), color=palette.text_secondary)
    )
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(head, spacing=theme.space("2")),
                ft.Text(
                    value,
                    size=theme.font_size("3xl"),
                    weight=theme.WEIGHT_BOLD,
                    color=palette.text_primary,
                ),
            ],
            spacing=theme.space("2"),
        ),
        bgcolor=palette.card,
        border=ft.border.all(1, palette.border_light),
        border_radius=theme.radius("lg"),
        padding=theme.space("5"),
        expand=True,
    )


def empty_state(
    palette: Palette,
    message: str,
    *,
    icon: str = ft.Icons.INBOX_OUTLINED,
    action: Optional[ft.Control] = None,
) -> ft.Container:
    children: List[ft.Control] = [
        ft.Icon(icon, size=40, color=palette.text_disabled),
        ft.Text(
            message,
            size=theme.font_size("base"),
            color=palette.text_muted,
            text_align=ft.TextAlign.CENTER,
        ),
    ]
    if action is not None:
        children.append(action)
    return ft.Container(
        content=ft.Column(
            children,
            spacing=theme.space("3"),
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        alignment=ft.alignment.center,
        padding=theme.space("10"),
    )


def field_row(palette: Palette, label: str, value: str) -> ft.Control:
    """A label/value pair used in detail panels."""
    return ft.Row(
        [
            ft.Text(
                label,
                size=theme.font_size("sm"),
                color=palette.text_secondary,
                width=110,
            ),
            ft.Text(
                value or "未读取到",
                size=theme.font_size("sm"),
                color=palette.text_primary if value else palette.text_muted,
                selectable=True,
                expand=True,
            ),
        ],
        spacing=theme.space("3"),
        vertical_alignment=ft.CrossAxisAlignment.START,
    )


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------
def primary_button(
    text: str,
    on_click: Callable,
    *,
    icon: Optional[str] = None,
    disabled: bool = False,
) -> ft.FilledButton:
    return ft.FilledButton(text=text, icon=icon, on_click=on_click, disabled=disabled)


def secondary_button(
    text: str,
    on_click: Callable,
    *,
    icon: Optional[str] = None,
    disabled: bool = False,
) -> ft.OutlinedButton:
    return ft.OutlinedButton(text=text, icon=icon, on_click=on_click, disabled=disabled)


def danger_button(
    palette: Palette,
    text: str,
    on_click: Callable,
    *,
    icon: Optional[str] = None,
    disabled: bool = False,
) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        text=text,
        icon=icon,
        on_click=on_click,
        disabled=disabled,
        style=ft.ButtonStyle(color=palette.danger),
    )


def ghost_icon_button(
    icon: str,
    on_click: Callable,
    *,
    tooltip: str = "",
    disabled: bool = False,
) -> ft.IconButton:
    return ft.IconButton(icon=icon, tooltip=tooltip, on_click=on_click, disabled=disabled)


# ---------------------------------------------------------------------------
# Badges & toasts
# ---------------------------------------------------------------------------
class StatusBadge(ft.Container):
    """A small colored pill indicating a status (ok / warn / error / idle)."""

    def __init__(self, palette: Palette, text: str, kind: str = "idle") -> None:
        self._palette = palette
        color_map = {
            "ok": (palette.success, "#1A00A870"),
            "warn": (palette.warning, "#1AED7B2F"),
            "error": (palette.danger, "#1AE34D59"),
            "idle": (palette.text_muted, palette.surface_hover),
            "info": (palette.primary, palette.primary_light),
        }
        fg, bg = color_map.get(kind, color_map["idle"])
        super().__init__(
            content=ft.Row(
                [
                    ft.Container(
                        width=8,
                        height=8,
                        bgcolor=fg,
                        border_radius=theme.radius("full"),
                    ),
                    ft.Text(text, size=theme.font_size("sm"), color=fg),
                ],
                spacing=theme.space("2"),
                tight=True,
            ),
            bgcolor=bg,
            border_radius=theme.radius("full"),
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
        )


def toast(page: ft.Page, message: str, kind: str = "info", palette: Optional[Palette] = None) -> None:
    """Show a transient SnackBar message."""
    if palette is None:
        palette = theme.LIGHT
    color_map = {
        "ok": palette.success,
        "error": palette.danger,
        "warn": palette.warning,
        "info": palette.primary,
    }
    bar = ft.SnackBar(
        content=ft.Text(message, color="#FFFFFF"),
        bgcolor=color_map.get(kind, palette.primary),
    )
    page.open(bar)


__all__ = [
    "run_in_background",
    "card",
    "section_title",
    "metric_tile",
    "empty_state",
    "field_row",
    "primary_button",
    "secondary_button",
    "danger_button",
    "ghost_icon_button",
    "StatusBadge",
    "toast",
]
