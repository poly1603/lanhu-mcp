"""AI IDE tools page (v2) — enriched summary, config status, collapsible history."""

from __future__ import annotations

from typing import Dict, List

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, StatusBadge, CountBadge, stat_chip,
    primary_button, secondary_button, ghost_icon_button, empty_state,
    run_in_background, toast,
)
from ..state import AppContext


STATUS_ORDER = {"configured": 0, "installed": 1, "not_installed": 2, "unknown": 3}


class IdeToolsPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._tiles = ft.Row(wrap=True, spacing=theme.space("4"), run_spacing=theme.space("4"))
        self._stat_bar = ft.Row(spacing=theme.space("4"), wrap=True)
        self._history = ft.Column(spacing=theme.space("1"))
        self._history_items: List[Dict] = []

    def _safe(self, fn, default):
        try:
            return fn()
        except Exception:
            return default

    # ── internal status ───────────────────────────────────────────
    def _ide_status(self, name: str, detail: dict) -> str:
        if detail.get("configured_at"):
            return "configured"
        if detail.get("installed"):
            return "installed"
        return "not_installed" if not detail.get("installed") else "unknown"

    def _stat_bar_data(self, details: dict) -> dict:
        installed = sum(1 for d in details.values() if d.get("installed"))
        configured = sum(1 for d in details.values() if d.get("configured_at"))
        total = len(details)
        return {"installed": installed, "configured": configured, "total": total}

    # ── tiles ─────────────────────────────────────────────────────
    def _tile(self, name: str, detail: dict) -> ft.Control:
        p = self.ctx.palette
        installed = bool(detail.get("installed"))
        configured = bool(detail.get("configured_at"))
        config_dir = detail.get("config_dir") or detail.get("exe_path") or "未检测到路径"

        status = "configured" if configured else ("installed" if installed else "not_installed")
        status_label = "已配置" if configured else ("已安装" if installed else "未检测到")
        badge = StatusBadge(p, status_label, "ok" if configured else ("ok" if installed else "idle"))

        action = primary_button("配置", lambda e, n=name: self._configure(n), icon=ft.Icons.SETTINGS) if installed else ft.Container()

        return ft.Container(
            width=340,
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.TERMINAL, color=p.primary if installed else p.text_muted, size=22),
                    ft.Text(name, weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary, expand=True),
                    badge,
                ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(config_dir, size=theme.font_size("xs"), color=p.text_muted,
                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Row([action], spacing=theme.space("2")),
            ], spacing=theme.space("2")),
            bgcolor=p.card,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("4"),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=3, color=p.shadow_sm, offset=ft.Offset(0, 1)),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    def _render(self) -> None:
        p = self.ctx.palette
        details = self._safe(self.ctx.ide.get_detection_details, {})
        if not details:
            self._tiles.controls = [empty_state(p, "未检测到任何 AI IDE", icon=ft.Icons.DEVELOPER_MODE)]
            # stat bar
            self._stat_bar.controls = [
                stat_chip(p, "已安装", "0", icon=ft.Icons.CHECK_CIRCLE, accent=p.text_muted),
                stat_chip(p, "已配置", "0", icon=ft.Icons.SETTINGS, accent=p.text_muted),
                stat_chip(p, "支持", "0", icon=ft.Icons.DEVICES, accent=p.text_muted),
            ]
            return

        # sort: configured > installed > not-installed
        sorted_details = sorted(details.items(), key=lambda kv: STATUS_ORDER.get(self._ide_status(kv[0], kv[1]), 99))
        self._tiles.controls = [self._tile(n, d) for n, d in sorted_details]

        stats = self._stat_bar_data(details)
        self._stat_bar.controls = [
            stat_chip(p, "已安装", str(stats["installed"]), icon=ft.Icons.CHECK_CIRCLE, accent=p.success),
            stat_chip(p, "已配置", str(stats["configured"]), icon=ft.Icons.SETTINGS, accent=p.primary),
            stat_chip(p, "支持", str(stats["total"]), icon=ft.Icons.DEVICES, accent=p.accent),
        ]

        # History section
        if self._history_items:
            self._history.controls = [
                ft.Text(f"最近 {min(len(self._history_items), 5)} 条", size=theme.font_size("xs"), color=p.text_muted),
            ] + [
                ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE if h.get("ok") else ft.Icons.ERROR, size=14,
                            color=p.success if h.get("ok") else p.danger),
                    ft.Text(h.get("name", "?"), size=theme.font_size("sm"), weight=theme.WEIGHT_MEDIUM, color=p.text_primary),
                    ft.Text(h.get("msg", ""), size=theme.font_size("xs"), color=p.text_muted, expand=True),
                ], spacing=theme.space("2"))
                for h in self._history_items[-5:]
            ]
        else:
            self._history.controls = [ft.Text("配置历史将显示在这里", size=theme.font_size("xs"), color=p.text_muted)]

    def refresh(self) -> None:
        self._render()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # ── actions ───────────────────────────────────────────────────
    def _configure(self, name: str) -> None:
        self.ctx.add_log(f"正在配置 {name}…")
        toast(self.ctx.page, f"配置 {name}…", "info", self.ctx.palette)

        def work():
            return self.ctx.ide.configure(name, self.ctx.port)

        def done(result):
            ok, msg = result if isinstance(result, tuple) else (bool(result), "")
            self.ctx.add_log(f"[{'OK' if ok else 'FAIL'}] {name}: {msg}")
            self._history_items.append({"name": name, "msg": msg, "ok": ok})
            toast(self.ctx.page, msg or ("已配置" if ok else "配置失败"), "ok" if ok else "error", self.ctx.palette)
            self.refresh()

        def err(exc):
            from ..components import show_error
            show_error(self.ctx.page, exc, f"配置 {name}", self.ctx.palette, self.ctx.add_log)
            self.refresh()

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _configure_all(self) -> None:
        toast(self.ctx.page, "正在配置所有 IDE…", "info", self.ctx.palette)

        def work():
            return self.ctx.ide.configure_all(self.ctx.port)

        def done(results):
            results = results or []
            ok_count = sum(1 for _n, ok, _m in results if ok)
            for n, ok, m in results:
                self._history_items.append({"name": n, "msg": m, "ok": ok})
                self.ctx.add_log(f"[{'OK' if ok else 'FAIL'}] {n}: {m}")
            toast(self.ctx.page, f"已配置 {ok_count}/{len(results)} IDE", "ok" if ok_count else "warn", self.ctx.palette)
            self.refresh()

        def err(exc):
            from ..components import show_error
            show_error(self.ctx.page, exc, "全部配置", self.ctx.palette, self.ctx.add_log)
            self.refresh()

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    # ── view ──────────────────────────────────────────────────────
    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._render()

        toolbar = gradient_card(
            p,
            ft.Row([
                ft.Text("将 MCP 配置写入 AI 编程工具", color=p.text_secondary, expand=True),
                secondary_button("重新检测", lambda e: self.refresh(), icon=ft.Icons.REFRESH),
                primary_button("全部配置", lambda e: self._configure_all(), icon=ft.Icons.DONE_ALL),
            ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=theme.space("4"),
        )

        stats_card = gradient_card(p, self._stat_bar, padding=theme.space("4"))

        history_card = card(p, self._history)

        return ft.Column(
            [
                section_title(p, "AI 工具", "检测 · 配置 · 批量部署 MCP 接入"),
                toolbar,
                stats_card,
                self._tiles,
                history_card,
            ],
            spacing=theme.space("5"),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )


__all__ = ["IdeToolsPage"]
