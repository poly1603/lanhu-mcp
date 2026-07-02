"""AI IDE tools page — rich tool cards with paths, config files, and open actions."""

from __future__ import annotations

import os
import subprocess
from typing import Dict, List

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, StatusBadge, CountBadge, stat_chip,
    primary_button, secondary_button, ghost_icon_button, empty_state,
    run_in_background, toast, show_error,
)
from ..state import AppContext

STATUS_ORDER = {"configured": 0, "installed": 1, "not_installed": 2, "unknown": 3}

# Icon mapping for known tools
TOOL_ICONS = {
    "Cursor": ft.Icons.MOUSE,
    "Trae": ft.Icons.HUB,
    "Windsurf": ft.Icons.WAVES,
    "Claude Code": ft.Icons.TERMINAL,
    "Claude Desktop": ft.Icons.DESKTOP_WINDOWS,
    "Codex": ft.Icons.CODE,
    "Cline": ft.Icons.EXTENSION,
    "Roo Code": ft.Icons.PEST_CONTROL_RODENT,
    "Continue": ft.Icons.PLAY_ARROW,
    "VS Code": ft.Icons.CODE,
    "MimoCode": ft.Icons.SYNC,
    "Junie": ft.Icons.SMART_TOY,
    "Gemini CLI": ft.Icons.AUTO_AWESOME,
    "Qoder": ft.Icons.QUERY_BUILDER,
    "Kiro": ft.Icons.ROCKET_LAUNCH,
    "Zed": ft.Icons.ZOOM_IN,
    "Cherry Studio": ft.Icons.CHAT,
    "ChatBox": ft.Icons.CHAT_BUBBLE,
    "OpenCode": ft.Icons.OPEN_IN_NEW,
    "CodeBuddy": ft.Icons.PEOPLE,
}


class IdeToolsPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._grid = ft.GridView(
            runs_count=2, max_extent=480, child_aspect_ratio=1.8,
            spacing=theme.space("4"), run_spacing=theme.space("4"),
        )
        self._stat_bar = ft.Row(spacing=theme.space("4"), wrap=True)
        self._history_items: List[Dict] = []
        self._history_container = ft.Column(spacing=theme.space("2"))

    def _safe(self, fn, default):
        try:
            return fn()
        except Exception:
            return default

    # ── status helpers ────────────────────────────────────────────
    def _ide_status(self, name: str, detail: dict) -> str:
        if detail.get("configured_at"):
            return "configured"
        if detail.get("installed"):
            return "installed"
        return "not_installed"

    def _stat_bar_data(self, details: dict) -> dict:
        installed = sum(1 for d in details.values() if d.get("installed"))
        configured = sum(1 for d in details.values() if d.get("configured_at"))
        total = len(details)
        return {"installed": installed, "configured": configured, "total": total}

    # ── render tool cards ─────────────────────────────────────────
    def _render(self) -> None:
        p = self.ctx.palette
        details = self._safe(self.ctx.ide.get_detection_details, {})

        if not details:
            self._grid.controls = [empty_state(p, "未检测到任何 AI IDE", icon=ft.Icons.DEVELOPER_MODE)]
            self._stat_bar.controls = [
                stat_chip(p, "已安装", "0", icon=ft.Icons.CHECK_CIRCLE, accent=p.text_muted),
                stat_chip(p, "已配置", "0", icon=ft.Icons.SETTINGS, accent=p.text_muted),
                stat_chip(p, "支持", "0", icon=ft.Icons.DEVICES, accent=p.text_muted),
            ]
            return

        sorted_details = sorted(details.items(), key=lambda kv: STATUS_ORDER.get(self._ide_status(kv[0], kv[1]), 99))
        self._grid.controls = [self._tool_card(n, d) for n, d in sorted_details]

        stats = self._stat_bar_data(details)
        self._stat_bar.controls = [
            stat_chip(p, "已安装", str(stats["installed"]), icon=ft.Icons.CHECK_CIRCLE, accent=p.success),
            stat_chip(p, "已配置", str(stats["configured"]), icon=ft.Icons.SETTINGS, accent=p.primary),
            stat_chip(p, "支持", str(stats["total"]), icon=ft.Icons.DEVICES, accent=p.accent),
        ]

        self._render_history()

    def _tool_card(self, name: str, detail: dict) -> ft.Container:
        p = self.ctx.palette
        installed = bool(detail.get("installed"))
        configured = bool(detail.get("configured_at"))
        exe_path = detail.get("exe_path") or ""
        config_dir = detail.get("config_dir") or ""
        config_path = detail.get("config_path") or ""

        status_label = "已配置" if configured else ("已安装" if installed else "未检测到")
        status_kind = "ok" if configured else ("ok" if installed else "idle")
        badge = StatusBadge(p, status_label, status_kind)

        icon = TOOL_ICONS.get(name, ft.Icons.EXTENSION)

        # Path info rows
        path_rows: List[ft.Control] = []
        if exe_path:
            path_rows.append(self._path_row(p, "安装路径", exe_path, can_open=True))
        if config_dir:
            path_rows.append(self._path_row(p, "数据目录", config_dir, can_open=True))
        if config_path:
            path_rows.append(self._path_row(p, "配置文件", config_path, can_open=True, is_file=True))

        if not path_rows:
            path_rows.append(ft.Text("未检测到安装路径", size=theme.font_size("xs"), color=p.text_muted))

        # Action buttons
        actions: List[ft.Control] = []
        if installed:
            actions.append(primary_button("配置 MCP", lambda e, n=name: self._configure(n), icon=ft.Icons.SETTINGS, disabled=self._busy_check()))
        if config_path:
            actions.append(secondary_button("查看配置", lambda e, cp=config_path: self._view_config(cp), icon=ft.Icons.DESCRIPTION))
        if config_dir and os.path.isdir(config_dir):
            actions.append(ghost_icon_button(ft.Icons.FOLDER_OPEN,
                                              lambda e, d=config_dir: self._open_dir(d),
                                              tooltip="打开数据目录"))
        if exe_path and os.path.isfile(os.path.dirname(exe_path)):
            actions.append(ghost_icon_button(ft.Icons.LAUNCH,
                                              lambda e, d=os.path.dirname(exe_path): self._open_dir(d),
                                              tooltip="打开安装目录"))

        content = ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Icon(icon, color=p.primary if installed else p.text_muted, size=24),
                    bgcolor=(p.primary if installed else p.text_muted) + "18",
                    border_radius=theme.radius("lg"),
                    width=44, height=44, alignment=ft.alignment.center,
                ),
                ft.Column([
                    ft.Text(name, size=theme.font_size("lg"), weight=theme.WEIGHT_BOLD, color=p.text_primary),
                    ft.Text("AI 开发工具", size=theme.font_size("xs"), color=p.text_muted),
                ], spacing=theme.space("1"), expand=True),
                badge,
            ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(height=1, color=p.border_light),
            ft.Column(path_rows, spacing=theme.space("2")),
            ft.Divider(height=1, color=p.border_light),
            ft.Row(actions, spacing=theme.space("2"), wrap=True),
        ], spacing=theme.space("3"))

        return ft.Container(
            content=content,
            bgcolor=p.card,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("5"),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=4, color=p.shadow_sm, offset=ft.Offset(0, 2)),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    def _path_row(self, p, label: str, path: str, can_open: bool = False, is_file: bool = False) -> ft.Row:
        icon = ft.Icons.DESCRIPTION if is_file else ft.Icons.FOLDER
        open_btn = ghost_icon_button(
            ft.Icons.OPEN_IN_NEW if is_file else ft.Icons.FOLDER_OPEN,
            lambda e, cp=path: self._open_path(cp, is_file),
            tooltip="打开" + ("文件" if is_file else "目录"),
        ) if can_open and path else ft.Container()

        return ft.Row([
            ft.Icon(icon, size=14, color=p.text_muted),
            ft.Column([
                ft.Text(label, size=theme.font_size("xs"), color=p.text_muted),
                ft.Text(path, size=theme.font_size("xs"), color=p.text_primary, font_family=theme.FONT_MONO,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, selectable=True, expand=True),
            ], spacing=0, expand=True),
            open_btn,
        ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _busy_check(self) -> bool:
        return False  # simplified

    # ── history ───────────────────────────────────────────────────
    def _render_history(self) -> None:
        p = self.ctx.palette
        if not self._history_items:
            self._history_container.controls = [
                ft.Text("配置历史将显示在这里", size=theme.font_size("xs"), color=p.text_muted)
            ]
            return
        items: List[ft.Control] = []
        for h in self._history_items[-5:]:
            items.append(ft.Row([
                ft.Icon(ft.Icons.CHECK_CIRCLE if h.get("ok") else ft.Icons.ERROR, size=14,
                        color=p.success if h.get("ok") else p.danger),
                ft.Text(h.get("name", "?"), size=theme.font_size("sm"), weight=theme.WEIGHT_MEDIUM, color=p.text_primary),
                ft.Text(h.get("msg", ""), size=theme.font_size("xs"), color=p.text_muted, expand=True),
            ], spacing=theme.space("2")))
        self._history_container.controls = items

    # ── lifecycle ─────────────────────────────────────────────────
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
            show_error(self.ctx.page, exc, "全部配置", self.ctx.palette, self.ctx.add_log)
            self.refresh()

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _open_dir(self, path: str) -> None:
        try:
            if os.path.isdir(path):
                os.startfile(path)
            elif os.path.isfile(path):
                os.startfile(os.path.dirname(path))
            self.ctx.add_log(f"[IDE] 已打开目录: {path}")
        except Exception as exc:
            toast(self.ctx.page, f"打开失败: {exc}", "error", self.ctx.palette)

    def _open_path(self, path: str, is_file: bool) -> None:
        try:
            if is_file and os.path.isfile(path):
                os.startfile(path)
            elif os.path.isdir(path):
                os.startfile(path)
            elif os.path.isfile(path):
                os.startfile(path)
            else:
                parent = os.path.dirname(path)
                if os.path.isdir(parent):
                    os.startfile(parent)
                else:
                    toast(self.ctx.page, "路径不存在", "warn", self.ctx.palette)
                    return
            self.ctx.add_log(f"[IDE] 已打开: {path}")
        except Exception as exc:
            toast(self.ctx.page, f"打开失败: {exc}", "error", self.ctx.palette)

    def _view_config(self, config_path: str) -> None:
        p = self.ctx.palette
        if not os.path.isfile(config_path):
            toast(self.ctx.page, "配置文件不存在", "warn", p)
            return
        try:
            with open(config_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(8000)
        except Exception as exc:
            toast(self.ctx.page, f"读取失败: {exc}", "error", p)
            return

        text_field = ft.TextField(
            value=content, multiline=True, min_lines=12, max_lines=24,
            read_only=True, text_size=theme.font_size("xs"),
            font_family=theme.FONT_MONO, expand=True,
        )

        def open_in_editor(e):
            try:
                os.startfile(config_path)
                toast(self.ctx.page, "已在系统编辑器中打开", "ok", p)
            except Exception as exc2:
                toast(self.ctx.page, f"打开失败: {exc2}", "error", p)

        dlg = ft.AlertDialog(
            title=ft.Text(f"配置文件 — {os.path.basename(config_path)}", color=p.text_primary),
            content=ft.Container(width=600, content=text_field),
            actions=[
                ft.TextButton("在编辑器中打开", on_click=open_in_editor),
                ft.TextButton("关闭", on_click=lambda e: self._close_dialog(dlg)),
            ],
        )
        self.ctx.page.open(dlg)

    def _close_dialog(self, dlg: ft.AlertDialog) -> None:
        try:
            self.ctx.page.close(dlg)
        except Exception:
            try:
                dlg.open = False
                self.ctx.page.update()
            except Exception:
                pass

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

        history_card = gradient_card(
            p,
            ft.Column([
                ft.Text("配置历史", size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                self._history_container,
            ], spacing=theme.space("2")),
        )

        return ft.ListView(
            controls=[
                ft.Container(
                    content=section_title(p, "AI 工具", "检测 · 配置 · 批量部署 MCP 接入"),
                    padding=ft.padding.only(left=theme.space("4"), top=theme.space("3"), right=theme.space("4"), bottom=theme.space("3")),
                ),
                ft.Container(
                    content=ft.Column([toolbar, stats_card, self._grid, history_card], spacing=theme.space("4")),
                    padding=ft.padding.only(left=theme.space("4"), top=theme.space("1"), right=theme.space("4")),
                ),
            ],
            spacing=0,
            expand=True,
        )


__all__ = ["IdeToolsPage"]
