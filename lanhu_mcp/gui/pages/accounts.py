"""Accounts page — account management with profile display, login, Cookie input."""

from __future__ import annotations

import threading
import time
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
        self._login_result_holder = ft.Container()
        self._profile_section = ft.Column(spacing=theme.space("2"))
        self._accounts_list = ft.Column(spacing=theme.space("2"))
        self._busy = False

    # ── profile area ──────────────────────────────────────────────
    def _render_profile(self, active: dict) -> None:
        p = self.ctx.palette
        if not active:
            self._profile_section.controls = [
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=48, color=p.text_muted),
                        ft.Text("未登录", size=theme.font_size("lg"), weight=theme.WEIGHT_MEDIUM, color=p.text_secondary),
                        ft.Text("请添加蓝湖账号或使用 Cookie 登录", size=theme.font_size("sm"), color=p.text_muted),
                    ], spacing=theme.space("2"), horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=theme.space("8"),
                ),
            ]
            return

        email = active.get("email", "") or active.get("user_email", "")
        name = active.get("name", "") or active.get("user_name", "")
        username = active.get("username", "") or active.get("login_name", "")
        company = active.get("company", "") or active.get("company_name", "")
        team = active.get("team", "") or active.get("team_name", "")
        role = active.get("role", "")
        avatar_url = active.get("avatar_url", "") or active.get("picture", "")
        label = accounts_core.account_primary_contact(active) or "蓝湖用户"
        avatar_url = accounts_core.avatar_url(active) or avatar_url

        info_items: List[ft.Control] = []
        if name and name != "蓝湖用户":
            info_items.append(field_row(p, "姓名", name))
        if username:
            info_items.append(field_row(p, "用户名", username))
        if email:
            info_items.append(field_row(p, "邮箱", email))
        if company:
            info_items.append(field_row(p, "公司", company))
        if team:
            info_items.append(field_row(p, "团队", team))
        if role:
            info_items.append(field_row(p, "角色", role))

        header = ft.Row([
            avatar(avatar_url, p, size=56),
            ft.Column([
                ft.Text(label, size=theme.font_size("xl"), weight=theme.WEIGHT_BOLD, color=p.text_primary),
                ft.Text(f"角色: {role}" if role else "已登录", size=theme.font_size("sm"), color=p.text_muted),
            ], spacing=theme.space("1"), expand=True),
            StatusBadge(p, "已登录", "ok"),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=theme.space("4"))

        self._profile_section.controls = [header, card(p, ft.Column(info_items, spacing=theme.space("3")))] if info_items else [header]

    # ── accounts list ─────────────────────────────────────────────
    def _render_accounts(self, accounts: List[dict]) -> None:
        p = self.ctx.palette
        if not accounts:
            self._accounts_list.controls = [
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.GROUP_OUTLINED, size=36, color=p.text_muted),
                        ft.Text("暂无账号", size=theme.font_size("base"), color=p.text_secondary),
                        ft.Text("点击上方按钮添加蓝湖账号", size=theme.font_size("sm"), color=p.text_muted),
                    ], spacing=theme.space("2"), horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=theme.space("6"),
                ),
            ]
            return

        items: List[ft.Control] = []
        for acc in accounts:
            label = accounts_core.account_primary_contact(acc) or "蓝湖用户"
            avatar_url = accounts_core.avatar_url(acc)
            aid = acc.get("id", "")
            is_active = aid == self.ctx.active_account_id
            contact_parts: List[str] = []
            if acc.get("email"):
                contact_parts.append(acc["email"])
            if acc.get("username"):
                contact_parts.append(acc["username"])
            contact_line = " · ".join(contact_parts[:2]) or "手动添加"

            item = ft.Container(
                content=ft.Row([
                    avatar(avatar_url, p, size=36),
                    ft.Column([
                        ft.Text(label, size=theme.font_size("base"), weight=theme.WEIGHT_MEDIUM, color=p.text_primary),
                        ft.Text(contact_line, size=theme.font_size("xs"), color=p.text_muted),
                    ], spacing=theme.space("1"), expand=True),
                    StatusBadge(p, "使用中", "ok") if is_active else ghost_icon_button(
                        ft.Icons.CHECK_CIRCLE_OUTLINE,
                        lambda e, a=aid: self._switch(a),
                        tooltip="切换到此账号",
                    ),
                    ghost_icon_button(ft.Icons.DELETE_OUTLINE,
                                      lambda e, a=aid: self._remove(a),
                                      tooltip="退出此账号"),
                ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=theme.space("3"),
                border=ft.border.all(1, p.border_light if not is_active else p.primary),
                border_radius=theme.radius("lg"),
                bgcolor=p.bg if not is_active else p.primary_light,
            )
            items.append(item)

        self._accounts_list.controls = items

    # ── lifecycle ─────────────────────────────────────────────────
    def refresh(self) -> None:
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
        self._render_profile(active)
        self._render_accounts(accounts)
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
                self.ctx.login_port,
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

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _add_manual_cookie(self) -> None:
        p = self.ctx.palette
        input_field = ft.TextField(
            label="粘贴 Cookie", multiline=True, min_lines=3, max_lines=6, expand=True,
        )
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
                try:
                    self.ctx.page.close(dlg)
                except Exception:
                    pass
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
                ft.TextButton("取消", on_click=lambda e: self.ctx.page.close(dlg)),
                ft.ElevatedButton("保存", on_click=do_save),
            ],
        )
        self.ctx.page.open(dlg)

    def _switch(self, account_id: str) -> None:
        if self.ctx.service.is_running():
            toast(self.ctx.page, "服务运行中，请先停止服务再切换账号", "warn", self.ctx.palette)
            return
        accounts_core.switch_account(account_id)
        self.ctx.add_log(f"[ACCOUNT] 已切换账号")
        toast(self.ctx.page, "已切换账号", "ok", self.ctx.palette)
        self.refresh()

    def _remove(self, account_id: str) -> None:
        if self.ctx.service.is_running():
            toast(self.ctx.page, "服务运行中，请先停止服务再退出账号", "warn", self.ctx.palette)
            return
        accounts_core.remove_account(account_id)
        self.ctx.add_log("[ACCOUNT] 已退出账号")
        toast(self.ctx.page, "已退出账号", "ok", self.ctx.palette)
        self.refresh()

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
        self._render_profile(active)
        self._render_accounts(accounts)

        # ── Action buttons card ───────────────────────────────────
        action_card = gradient_card(
            p,
            ft.Column([
                ft.Text("账号操作", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Row([
                    primary_button("一键登录", lambda e: self._add_account(), icon=ft.Icons.LOGIN),
                    secondary_button("手动 Cookie", lambda e: self._add_manual_cookie(), icon=ft.Icons.COOKIE),
                    ghost_icon_button(ft.Icons.OPEN_IN_NEW, lambda e: self._open_login_url(), tooltip="打开蓝湖登录页"),
                ], spacing=theme.space("3"), wrap=True),
            ], spacing=theme.space("3")),
        )

        # ── Profile card ──────────────────────────────────────────
        profile_card = gradient_card(
            p,
            ft.Column([
                ft.Text("账号信息", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                self._profile_section,
            ], spacing=theme.space("3")),
        )

        # ── Accounts list card ────────────────────────────────────
        list_card = gradient_card(
            p,
            ft.Column([
                ft.Row([
                    ft.Text("已登录账号", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Container(expand=True),
                    CountBadge(p, len(accounts), "info"),
                ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self._accounts_list,
            ], spacing=theme.space("3")),
        )

        return ft.ListView(
            controls=[
                ft.Container(
                    content=section_title(p, "账号", "登录管理 · 账号切换 · 资料查看"),
                    padding=ft.padding.symmetric(horizontal=theme.space("6"), vertical=theme.space("4")),
                ),
                ft.Container(
                    content=ft.Column([
                        action_card,
                        ft.Row([profile_card, list_card], spacing=theme.space("4"),
                               vertical_alignment=ft.CrossAxisAlignment.START),
                    ], spacing=theme.space("5")),
                    padding=ft.padding.symmetric(horizontal=theme.space("6"), vertical=theme.space("2")),
                ),
            ],
            spacing=0,
            expand=True,
        )


__all__ = ["AccountsPage"]
