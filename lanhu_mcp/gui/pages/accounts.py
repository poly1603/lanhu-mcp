"""Accounts page — login URL, manual cookie, multi-account switch/remove, profile."""

from __future__ import annotations

import webbrowser
from typing import List, Optional

import flet as ft

from .. import theme
from ..components import (
    section_title,
    card,
    StatusBadge,
    primary_button,
    secondary_button,
    danger_button,
    field_row,
    empty_state,
    run_in_background,
    toast,
)
from ..state import AppContext
from ...core import accounts as accounts_core
from ...services.lanhu_api import fetch_lanhu_user_profile


class AccountsPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._login_url_field = ft.TextField(label="登录地址", dense=True, expand=True)
        self._cookie_field = ft.TextField(
            label="手动 Cookie", dense=True, multiline=True, min_lines=2, max_lines=4, expand=True
        )
        self._account_list = ft.Column(spacing=theme.space("2"))
        self._detail_holder = ft.Column(spacing=theme.space("2"))

    # -- data -----------------------------------------------------------
    def _safe(self, fn, default):
        try:
            return fn()
        except Exception:
            return default

    def _render_accounts(self) -> None:
        p = self.ctx.palette
        account_list = self._safe(accounts_core.get_accounts, [])
        active = self._safe(accounts_core.get_active_account, None)
        active_id = (active or {}).get("id", "") if active else ""

        if not account_list:
            self._account_list.controls = [
                empty_state(p, "尚未添加账号，请粘贴 Cookie 或前往登录", icon=ft.Icons.PERSON_OFF)
            ]
        else:
            rows: List[ft.Control] = []
            for acc in account_list:
                acc_id = acc.get("id", "")
                is_active = acc_id == active_id
                contact = accounts_core.account_primary_contact(acc)
                detail = accounts_core.account_detail_line(acc)
                actions: List[ft.Control] = []
                if is_active:
                    actions.append(StatusBadge(p, "使用中", "ok"))
                else:
                    actions.append(secondary_button("切换", lambda e, i=acc_id: self._switch(i),
                                                     icon=ft.Icons.SWAP_HORIZ))
                actions.append(danger_button(p, "退出", lambda e, i=acc_id: self._remove(i),
                                              icon=ft.Icons.LOGOUT))
                rows.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.ACCOUNT_CIRCLE, color=p.primary if is_active else p.text_muted),
                                ft.Column(
                                    [
                                        ft.Text(contact or "蓝湖用户", weight=theme.WEIGHT_MEDIUM,
                                                color=p.text_primary),
                                        ft.Text(detail, size=theme.font_size("xs"), color=p.text_muted),
                                    ],
                                    spacing=2, expand=True,
                                ),
                                ft.Row(actions, spacing=theme.space("2")),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=theme.space("3"),
                        ),
                        bgcolor=p.primary_light if is_active else p.surface,
                        border=ft.border.all(1, p.border_focus if is_active else p.border_light),
                        border_radius=theme.radius("md"),
                        padding=theme.space("3"),
                    )
                )
            self._account_list.controls = rows

        # Active account detail panel.
        if active:
            self._detail_holder.controls = [
                ft.Text("账号资料", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD,
                        color=p.text_primary),
                field_row(p, "联系方式", accounts_core.account_primary_contact(active)),
                field_row(p, "资料", accounts_core.account_profile_line(active)),
                field_row(p, "Cookie", accounts_core.account_cookie_line(active)),
                field_row(p, "MCP URL", self._safe(lambda: accounts_core.current_mcp_url(self.ctx.port), "")),
            ]
        else:
            self._detail_holder.controls = [
                empty_state(p, "登录后显示账号资料", icon=ft.Icons.BADGE)
            ]

    def refresh(self) -> None:
        self._render_accounts()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # -- actions --------------------------------------------------------
    def _switch(self, account_id: str) -> None:
        if self.ctx.service.is_running():
            toast(self.ctx.page, "服务运行中，无法切换账号", "warn", self.ctx.palette)
            return
        if self._safe(lambda: accounts_core.set_active_account(account_id), False):
            toast(self.ctx.page, "已切换账号", "ok", self.ctx.palette)
        self.refresh()

    def _remove(self, account_id: str) -> None:
        if self.ctx.service.is_running():
            toast(self.ctx.page, "服务运行中，无法退出账号", "warn", self.ctx.palette)
            return
        self._safe(lambda: accounts_core.remove_account(account_id), None)
        toast(self.ctx.page, "已退出账号", "ok", self.ctx.palette)
        self.refresh()

    def _save_login_url(self) -> None:
        url = (self._login_url_field.value or "").strip()
        if url:
            self._safe(lambda: accounts_core.save_login_url(url), None)
            toast(self.ctx.page, "登录地址已保存", "ok", self.ctx.palette)

    def _open_login(self) -> None:
        url = (self._login_url_field.value or "").strip() or self._safe(accounts_core.get_saved_login_url, "")
        if url:
            try:
                webbrowser.open(url)
                toast(self.ctx.page, "已在浏览器打开登录页，登录后复制 Cookie 粘贴到下方", "info", self.ctx.palette)
            except Exception:
                toast(self.ctx.page, "无法打开浏览器", "error", self.ctx.palette)

    def _save_cookie(self) -> None:
        cookie = (self._cookie_field.value or "").strip()
        if not cookie:
            toast(self.ctx.page, "请粘贴 Cookie", "warn", self.ctx.palette)
            return
        account = self._safe(lambda: accounts_core.upsert_account(cookie), None)
        if not account:
            toast(self.ctx.page, "Cookie 解析失败", "error", self.ctx.palette)
            return
        self._cookie_field.value = ""
        toast(self.ctx.page, "账号已保存，正在读取资料…", "ok", self.ctx.palette)
        self.refresh()

        # Enrich profile in background.
        def work():
            return fetch_lanhu_user_profile(cookie)

        def done(result):
            ok, msg, info = result if isinstance(result, tuple) and len(result) == 3 else (False, "", {})
            if ok and info:
                self._safe(lambda: accounts_core.upsert_account(cookie, info), None)
                self.ctx.add_log("已补全蓝湖用户资料")
            else:
                self.ctx.add_log(f"读取用户资料失败: {msg}")
            self.refresh()

        run_in_background(self.ctx.page, work, on_done=done)

    # -- view -----------------------------------------------------------
    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._login_url_field.value = self._safe(accounts_core.get_saved_login_url, "")
        self._render_accounts()

        login_card = card(
            p,
            ft.Column(
                [
                    ft.Text("登录", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Row([self._login_url_field,
                            secondary_button("保存", lambda e: self._save_login_url(), icon=ft.Icons.SAVE),
                            primary_button("打开登录页", lambda e: self._open_login(), icon=ft.Icons.OPEN_IN_NEW)],
                           spacing=theme.space("2")),
                    ft.Divider(height=1, color=p.border_light),
                    self._cookie_field,
                    ft.Row([primary_button("保存 Cookie", lambda e: self._save_cookie(), icon=ft.Icons.ADD)],
                           spacing=theme.space("2")),
                ],
                spacing=theme.space("3"),
            ),
        )
        accounts_card = card(
            p,
            ft.Column(
                [ft.Text("已登录账号", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD,
                         color=p.text_primary), self._account_list],
                spacing=theme.space("3"),
            ),
        )
        detail_card = card(p, self._detail_holder)

        return ft.Column(
            [
                section_title(p, "账号", "登录、切换与管理蓝湖账号"),
                login_card,
                accounts_card,
                detail_card,
            ],
            spacing=theme.space("6"),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )


__all__ = ["AccountsPage"]
