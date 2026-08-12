"""AI IDE tools page — rich tool cards with paths, config files, and open actions."""

from __future__ import annotations

import os
import subprocess
import time
from typing import Dict, List

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, StatusBadge, CountBadge, stat_chip,
    primary_button, secondary_button, ghost_icon_button, empty_state,
    run_in_background, toast, show_error,
)
from ..state import AppContext
from ..components.widgets import page_banner

STATUS_ORDER = {"configured": 0, "installed": 1, "not_installed": 2, "unknown": 3}
IDE_CARD_HEIGHT = 390

# Icon mapping for known tools
TOOL_ICONS = {
    "Cursor": ft.Icons.MOUSE,
    "Trae": ft.Icons.HUB,
    "Windsurf": ft.Icons.WAVES,
    "Claude Code": ft.Icons.TERMINAL,
    "Claude Desktop": ft.Icons.DESKTOP_WINDOWS,
    "Codex": ft.Icons.CODE,
    "Cline": ft.Icons.EXTENSION,
    "Roo Code": ft.Icons.EXTENSION,
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
        # Use the page's outer ListView as the only vertical scroll owner.
        # GridView's fixed child_aspect_ratio used to force these cards to a
        # short height and clip the action row at the bottom.
        self._grid = ft.ResponsiveRow(
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=theme.space("4"),
            run_spacing=theme.space("4"),
        )
        self._stat_bar = ft.Row(spacing=theme.space("4"), wrap=True)
        self._history_items: List[Dict] = []
        self._history_container = ft.Column(spacing=theme.space("2"))
        self._details_cache: Dict = {}
        self._details_loaded_at = 0.0
        self._details_cache_ttl = 8.0

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
        now = time.monotonic()
        if not self._details_cache or now - self._details_loaded_at >= self._details_cache_ttl:
            self._details_cache = self._safe(self.ctx.ide.get_detection_details, {})
            self._details_loaded_at = now
        all_details = self._details_cache
        details = {name: detail for name, detail in all_details.items() if detail.get("installed")}

        if not details:
            self._grid.controls = [ft.Container(
                content=empty_state(p, "未检测到任何 AI IDE", icon=ft.Icons.DEVELOPER_MODE),
                col={"sm": 12},
            )]
            self._stat_bar.controls = [
                stat_chip(p, "已安装", "0", icon=ft.Icons.CHECK_CIRCLE, accent=p.text_muted),
                stat_chip(p, "已配置", "0", icon=ft.Icons.SETTINGS, accent=p.text_muted),
                stat_chip(p, "支持", "0", icon=ft.Icons.DEVICES, accent=p.text_muted),
            ]
            return

        sorted_details = sorted(details.items(), key=lambda kv: STATUS_ORDER.get(self._ide_status(kv[0], kv[1]), 99))
        self._grid.controls = [
            ft.Container(
                content=self._tool_card(name, detail),
                col={"sm": 12, "md": 6, "lg": 4, "xl": 4},
            )
            for name, detail in sorted_details
        ]

        stats = self._stat_bar_data(details)
        self._stat_bar.controls = [
            stat_chip(p, "已安装", str(stats["installed"]), icon=ft.Icons.CHECK_CIRCLE, accent=p.success),
            stat_chip(p, "已配置", str(stats["configured"]), icon=ft.Icons.SETTINGS, accent=p.primary),
            stat_chip(p, "本机工具", str(stats["total"]), icon=ft.Icons.DEVICES, accent=p.accent),
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

        visible_paths = path_rows[:2]
        if len(path_rows) > 2:
            visible_paths.append(ft.Text(f"还有 {len(path_rows) - 2} 项配置路径", size=theme.font_size("xs"), color=p.text_muted))

        content = ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Icon(icon, color=p.primary if installed else p.text_muted, size=22),
                    bgcolor=theme.alpha(p.primary if installed else p.text_muted, 0x18),
                    border_radius=theme.radius("lg"),
                    width=42, height=42, alignment=ft.alignment.center,
                ),
                ft.Column([
                    ft.Text(name, size=theme.font_size("base"), weight=theme.WEIGHT_BOLD, color=p.text_primary),
                    ft.Text("AI 开发工具", size=theme.font_size("xs"), color=p.text_muted),
                ], spacing=0, expand=True),
                badge,
            ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(height=1, color=p.border_light),
            ft.Column(visible_paths, spacing=theme.space("2")),
            ft.Container(expand=True),
            ft.Row(actions, spacing=theme.space("2"), wrap=True),
        ], spacing=theme.space("3"), expand=True)

        return ft.Container(
            content=content,
            height=IDE_CARD_HEIGHT,
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
            ft.Icon(icon, size=13, color=p.text_disabled),
            ft.Column([
                ft.Text(label, size=theme.font_size("xs"), color=p.text_muted),
                ft.Text(path, size=theme.font_size("xs"), color=p.text_secondary, font_family=theme.FONT_MONO,
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

    def _flow_item(self, p, title: str, desc: str, icon: str, accent: str) -> ft.Control:
        return ft.Row([
            ft.Container(
                content=ft.Icon(icon, size=16, color=accent),
                bgcolor=theme.alpha(accent, 0x16),
                border_radius=theme.radius("md"),
                width=32,
                height=32,
                alignment=ft.alignment.center,
            ),
            ft.Column([
                ft.Text(title, size=theme.font_size("sm"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Text(desc, size=theme.font_size("xs"), color=p.text_muted),
            ], spacing=0),
        ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # ── lifecycle ─────────────────────────────────────────────────
    def refresh(self) -> None:
        self._render()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    def _invalidate_detection_cache(self) -> None:
        self._details_cache = {}
        self._details_loaded_at = 0.0

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
            del self._history_items[:-20]
            self._invalidate_detection_cache()
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
            del self._history_items[:-20]
            self._invalidate_detection_cache()
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
        # A detected IDE can have a global config directory before the file is
        # created.  Open an empty editor in that case so the user can create
        # the file directly from this dialog.
        try:
            content = ""
            if os.path.isfile(config_path):
                with open(config_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(12000)
        except Exception as exc:
            toast(self.ctx.page, f"读取失败: {exc}", "error", p)
            return

        extension = os.path.splitext(config_path)[1].lower().lstrip(".") or "text"
        language = {"yml": "yaml", "yaml": "yaml", "json": "json", "toml": "toml"}.get(extension, "text")
        editor = ft.TextField(
            value=content,
            multiline=True,
            min_lines=18,
            max_lines=28,
            text_size=theme.font_size("xs"),
            text_style=ft.TextStyle(font_family=theme.FONT_MONO),
            expand=True,
            border_color=p.border,
            focused_border_color=p.primary,
            bgcolor=p.input_bg,
            color=p.text_primary,
        )
        preview = ft.Markdown(
            value=f"```{language}\n{content}\n```",
            code_theme=ft.MarkdownCodeTheme.ATOM_ONE_DARK,
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            expand=True,
        )

        def update_preview(_event=None) -> None:
            preview.value = f"```{language}\n{editor.value or ''}\n```"
            try:
                preview.update()
            except Exception:
                pass

        editor.on_change = update_preview

        editor_panel = ft.Container(
            content=editor,
            expand=True,
            bgcolor=p.input_bg,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("lg"),
            padding=theme.space("2"),
        )
        preview_panel = ft.Container(
            content=preview,
            expand=True,
            bgcolor="#0B1220",
            border_radius=theme.radius("lg"),
            padding=theme.space("3"),
        )

        editor_tabs = ft.Row(
            [editor_panel, preview_panel],
            expand=True,
            spacing=theme.space("2"),
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        def save_config(_event) -> None:
            try:
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                with open(config_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(editor.value or "")
                self._invalidate_detection_cache()
                self.ctx.add_log(f"[IDE] 已保存配置: {config_path}")
                toast(self.ctx.page, "配置已保存", "ok", p)
                self._close_dialog(dlg)
                self.refresh()
            except Exception as exc:
                show_error(self.ctx.page, exc, "保存配置", p, self.ctx.add_log)

        def open_in_editor(_event):
            try:
                os.startfile(config_path)
                toast(self.ctx.page, "已在系统编辑器中打开", "ok", p)
            except Exception as exc2:
                toast(self.ctx.page, f"打开失败: {exc2}", "error", p)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Column([
                    ft.Text(f"{os.path.basename(config_path)}", color=p.text_primary, weight=theme.WEIGHT_SEMIBOLD),
                    ft.Text(config_path, size=theme.font_size("xs"), color=p.text_muted, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=0, expand=True),
                ghost_icon_button(ft.Icons.CLOSE, lambda _event: self._close_dialog(dlg), tooltip="关闭"),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            content=ft.Container(width=820, height=560, content=editor_tabs),
            actions=[
                ft.TextButton("在编辑器中打开", on_click=open_in_editor),
                ft.TextButton("取消", on_click=lambda _event: self._close_dialog(dlg)),
                ft.FilledButton("保存配置", icon=ft.Icons.SAVE_OUTLINED, on_click=save_config),
            ],
            on_dismiss=lambda _event: self._close_dialog(dlg) if getattr(dlg, "open", False) else None,
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

        header = ft.Container(
            content=ft.Row([
                section_title(p, "AI 工具", "仅显示本机已安装的 AI 工具"),
                ft.Container(expand=True),
            ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=theme.space("6"), top=theme.space("5"), right=theme.space("6"), bottom=theme.space("3")),
        )

        intro_card = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.TERMINAL, size=18, color=p.primary),
                ft.Text(
                    "仅列出当前电脑已安装的 AI 工具，可按需写入当前 MCP 地址。",
                    size=theme.font_size("sm"), color=p.text_secondary, expand=True,
                ),
            ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=p.primary_light,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("4"),
        )
        stats_card = gradient_card(p, self._stat_bar, padding=theme.space("4"))

        flow_card = ft.Container(
            content=ft.Row([
                self._flow_item(p, "检测", "识别已安装工具", ft.Icons.SEARCH, p.primary),
                ft.Icon(ft.Icons.CHEVRON_RIGHT, size=18, color=p.text_disabled),
                self._flow_item(p, "写入", "生成 MCP 配置", ft.Icons.EDIT_DOCUMENT, p.accent),
                ft.Icon(ft.Icons.CHEVRON_RIGHT, size=18, color=p.text_disabled),
                self._flow_item(p, "重启", "让 IDE 重新加载配置", ft.Icons.RESTART_ALT, p.success),
            ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER, wrap=True),
            bgcolor=p.card,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("4"),
        )

        history_card = gradient_card(
            p,
            ft.Column([
                ft.Text("配置历史", size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                self._history_container,
            ], spacing=theme.space("2")),
        )

        body = ft.Column([intro_card, stats_card, self._grid], spacing=theme.space("4"), tight=True)
        view = ft.ListView(
            controls=[
                page_banner(p, "AI 工具", "检测本机工具、编辑全局 MCP 配置", "ai"),
                ft.Container(
                    content=body,
                    padding=ft.padding.only(left=theme.space("6"), top=theme.space("1"), right=theme.space("6"), bottom=theme.space("6")),
                    bgcolor=p.card,
                ),
            ],
            spacing=0,
            expand=True,
        )
        view.bgcolor = p.card
        return view


__all__ = ["IdeToolsPage"]
