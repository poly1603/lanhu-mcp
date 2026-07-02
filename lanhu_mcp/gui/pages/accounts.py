"""Accounts page — merged info + actions, popup account switcher (2+ accounts)."""

from __future__ import annotations

from typing import List, Optional

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, StatusBadge, CountBadge,
    primary_button, secondary_button, danger_button, ghost_icon_button,
    avatar, stat_chip, field_row, toast, show_error,
)
from ..state import AppContext
from ...core import accounts as accounts_core


class AccountsPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._profile_card_content = ft.Column(spacing=theme.space("3"))
        self._busy = False

    # ── profile card (info + actions merged) ──────────────────────
    def _render_profile_card(self, active: Optional[dict], accounts: list) -> None:
        p = self.ctx.palette
        account_count = len(accounts)

        if not active:
            self._profile_card_content.controls = [
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=56, color=p.text_muted),
                        ft.Text("未登录", size=theme.font_size("xl"), weight=theme.WEIGHT_BOLD, color=p.text_secondary),
                        ft.Text("请添加蓝湖账号或使用 Cookie 登录", size=theme.font_size("sm"), color=p.text_muted),
                        ft.Container(height=theme.space("2")),
                        ft.Row([
                            primary_button("一键登录", lambda e: self._add_account(), icon=ft.Icons.LOGIN),
                            secondary_button("手动 Cookie", lambda e: self._add_manual_cookie(), icon=ft.Icons.COOKIE),
                        ], spacing=theme.space("3")),
                    ], spacing=theme.space("3"), horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=theme.space("8"),
                ),
            ]
            return

        # ── Build profile info ───────────────────────────────────
        name = active.get("name", "") or "蓝湖用户"
        username = active.get("username", "") or active.get("nickname", "")
        email = active.get("email", "") or ""
        mobile = active.get("mobile", "") or ""
        company = active.get("company", "") or ""
        team = active.get("team", "") or ""
        role = active.get("role", "")
        avatar_url = accounts_core.avatar_url(active)
        label = accounts_core.account_primary_contact(active) or name

        # Avatar + name header
        header = ft.Row([
            avatar(avatar_url, p, size=64),
            ft.Column([
                ft.Text(name, size=theme.font_size("xl"), weight=theme.WEIGHT_BOLD, color=p.text_primary),
                ft.Text(label, size=theme.font_size("sm"), color=p.text_muted),
            ], spacing=theme.space("1"), expand=True),
        ], spacing=theme.space("4"), vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # Info grid (2 columns)
        info_items: List[ft.Control] = []
        if email:
            info_items.append(field_row(p, "邮箱", email))
        if mobile:
            info_items.append(field_row(p, "手机", mobile))
        if username:
            info_items.append(field_row(p, "用户名", username))
        if company:
            info_items.append(field_row(p, "公司", company))
        if team:
            info_items.append(field_row(p, "团队", team))
        if role:
            info_items.append(field_row(p, "角色", role))

        # Action buttons row
        action_buttons: List[ft.Control] = [
            primary_button("一键登录", lambda e: self._add_account(), icon=ft.Icons.LOGIN),
            secondary_button("手动 Cookie", lambda e: self._add_manual_cookie(), icon=ft.Icons.COOKIE),
            ghost_icon_button(ft.Icons.OPEN_IN_NEW, lambda e: self._open_login_url(), tooltip="打开蓝湖登录页"),
        ]

        # Add switch account button only when 2+ accounts
        if account_count >= 2:
            action_buttons.append(
                secondary_button("切换账号", lambda e: self._show_switch_dialog(accounts), icon=ft.Icons.SWAP_HORIZ),
            )

        controls = [header]
        if info_items:
            controls.append(ft.Divider(height=1, color=p.border_light))
            controls.append(ft.Column(info_items, spacing=theme.space("2")))
        controls.append(ft.Divider(height=1, color=p.border_light))
        controls.append(
            ft.Row(action_buttons, spacing=theme.space("3"), wrap=True),
        )
        self._profile_card_content.controls = controls

    # ── switch account dialog ─────────────────────────────────────
    def _show_switch_dialog(self, accounts: list) -> None:
        p = self.ctx.palette
        active_id = self.ctx.active_account_id

        def do_switch(account_id: str):
            if self.ctx.service.is_running():
                toast(self.ctx.page, "服务运行中，请先停止服务再切换账号", "warn", p)
                return
            accounts_core.switch_account(account_id)
            self.ctx.add_log("[ACCOUNT] 已切换账号")
            toast(self.ctx.page, "已切换账号", "ok", p)
            self._close_dialog_and_refresh(dlg)

        items: List[ft.Control] = []
        for acc in accounts:
            aid = acc.get("id", "")
            is_active = aid == active_id
            name = acc.get("name", "") or "蓝湖用户"
            email = acc.get("email", "") or acc.get("username", "") or ""
            avatar_url = accounts_core.avatar_url(acc)

            row = ft.Container(
                content=ft.Row([
                    avatar(avatar_url, p, size=36),
                    ft.Column([
                        ft.Text(name, size=theme.font_size("base"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                        ft.Text(email, size=theme.font_size("xs"), color=p.text_muted),
                    ], spacing=theme.space("1"), expand=True),
                    StatusBadge(p, "当前", "ok") if is_active else
                    ft.ElevatedButton("切换", on_click=lambda e, a=aid: do_switch(a), dense=True),
                ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=theme.space("3"),
                border=ft.border.all(1, p.primary if is_active else p.border_light),
                border_radius=theme.radius("lg"),
                bgcolor=p.primary_light if is_active else None,
            )
            items.append(row)

        dlg = ft.AlertDialog(
            title=ft.Text("切换账号", color=p.text_primary),
            content=ft.Container(
                width=420,
                content=ft.Column(items, spacing=theme.space("3"), scroll=ft.ScrollMode.AUTO, tight=True),
            ),
            actions=[ft.TextButton("关闭", on_click=lambda e: self._close_dialog(dlg))],
        )
        self.ctx.page.open(dlg)

    def _close_dialog_and_refresh(self, dlg: ft.AlertDialog) -> None:
        self._close_dialog(dlg)
        self.refresh()

    def _close_dialog(self, dlg: ft.AlertDialog) -> None:
        try:
            self.ctx.page.close(dlg)
        except Exception:
            try:
                dlg.open = False
                self.ctx.page.update()
            except Exception:
                pass

    # ── account stats ─────────────────────────────────────────────
    def _render_stats(self, accounts: list, active: Optional[dict]) -> ft.Control:
        p = self.ctx.palette
        return ft.Row([
            stat_chip(p, "已登录", str(len(accounts)), icon=ft.Icons.GROUP, accent=p.primary),
            stat_chip(p, "当前账号", accounts_core.account_primary_contact(active)[:12] if active else "无",
                      icon=ft.Icons.PERSON, accent=p.success),
        ], spacing=theme.space("4"), wrap=True)

    # ── lifecycle ─────────────────────────────────────────────────
    def refresh(self) -> None:
        try:
            accounts = accounts_core.get_accounts()
        except Exception:
            accounts = []
        try:
            active = accounts_core.get_active_account()
        except Exception:
            active = None
        self.ctx.active_account_id = (active or {}).get("id", "") if active else ""
        self._render_profile_card(active, accounts)
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # ── actions ───────────────────────────────────────────────────
    def _add_account(self) -> None:
        p = self.ctx.palette
        self.ctx.add_log("[LOGIN] 启动蓝湖一键登录…")

        def work():
            return accounts_core.launch_login_helper(
                0,
                on_output=lambda line: self.ctx.add_log(line),
                on_error=lambda line: self.ctx.add_log(f"[ERR] {line}"),
            )

        def done(result):
            if not result:
                toast(self.ctx.page, "登录未完成", "warn", p)
                return
            ok = result.get("ok") if isinstance(result, dict) else bool(result)
            if ok:
                self.ctx.add_log("[LOGIN] 登录成功")
                toast(self.ctx.page, "登录成功", "ok", p)
            else:
                error = (result or {}).get("error") or "登录失败"
                self.ctx.add_log(f"[ERR] [LOGIN] {error}")
                toast(self.ctx.page, error, "error", p)
            self.refresh()

        def err(exc):
            show_error(self.ctx.page, exc, "蓝湖登录", p, self.ctx.add_log)

        from ..components import run_in_background
        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _add_manual_cookie(self) -> None:
        p = self.ctx.palette
        input_field = ft.TextField(label="粘贴 Cookie", multiline=True, min_lines=3, max_lines=6, expand=True)
        name_field = ft.TextField(label="备注名称", hint_text="例如：工作账号", expand=True)

        def do_save(e):
            cookie = (input_field.value or "").strip()
            name = (name_field.value or "").strip() or "手动账号"
            if not cookie:
                toast(self.ctx.page, "请输入 Cookie", "warn", p)
                return
            try:
                accounts_core.add_manual_account(cookie, display_name=name)
                self.ctx.add_log(f"[ACCOUNT] 已保存手动账号: {name}")
                toast(self.ctx.page, f"账号「{name}」已保存", "ok", p)
                self._close_dialog(dlg)
                self.refresh()
            except Exception as exc:
                show_error(self.ctx.page, exc, "保存 Cookie", p, self.ctx.add_log)

        dlg = ft.AlertDialog(
            title=ft.Text("手动添加 Cookie", color=p.text_primary),
            content=ft.Container(
                width=480,
                content=ft.Column([name_field, input_field], spacing=theme.space("3")),
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda e: self._close_dialog(dlg)),
                ft.ElevatedButton("保存", on_click=do_save),
            ],
        )
        self.ctx.page.open(dlg)

    def _open_login_url(self) -> None:
        import webbrowser
        try:
            url = accounts_core.get_login_url()
        except Exception:
            url = "https://lanhuapp.com/web/"
        webbrowser.open(url)

    # ── view ──────────────────────────────────────────────────────
    def build(self) -> ft.Control:
        p = self.ctx.palette

        try:
            accounts = accounts_core.get_accounts()
        except Exception:
            accounts = []
        try:
            active = accounts_core.get_active_account()
        except Exception:
            active = None
        self.ctx.active_account_id = (active or {}).get("id", "") if active else ""
        self._render_profile_card(active, accounts)

        # Stats bar
        stats_bar = gradient_card(p, self._render_stats(accounts, active), padding=theme.space("4"))

        # Profile card (merged info + actions)
        profile_card = gradient_card(
            p,
            ft.Column([
                ft.Row([
                    ft.Text("账号信息", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Container(expand=True),
                    CountBadge(p, len(accounts), "info") if len(accounts) > 0 else ft.Container(),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self._profile_card_content,
            ], spacing=theme.space("3")),
        )

        return ft.ListView(
            controls=[
                ft.Container(
                    content=section_title(p, "账号", "登录管理 · 资料查看 · 账号切换"),
                    padding=ft.padding.only(left=theme.space("4"), top=theme.space("3"), right=theme.space("4"), bottom=theme.space("3")),
                ),
                ft.Container(
                    content=ft.Column([stats_bar, profile_card], spacing=theme.space("4")),
                    padding=ft.padding.only(left=theme.space("4"), top=theme.space("1"), right=theme.space("4")),
                ),
            ],
            spacing=0,
            expand=True,
        )


__all__ = ["AccountsPage"]
