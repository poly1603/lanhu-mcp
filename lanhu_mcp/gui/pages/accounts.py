"""Accounts page — merged info + actions, popup account switcher (2+ accounts)."""

from __future__ import annotations

from typing import List, Optional

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, page_frame, StatusBadge, CountBadge,
    primary_button, secondary_button, danger_button, ghost_icon_button,
    avatar, stat_chip, field_row, toast, show_error,
    page_banner,
)
from ..state import AppContext
from ...core import accounts as accounts_core
from ...services.browser_login import read_default_browser_cookie
from ...services.lanhu_api import fetch_lanhu_user_profile
from lanhu_login_helper import has_valid_auth_cookie


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
            waiting = ft.Row([
                ft.ProgressRing(width=16, height=16, stroke_width=2),
                ft.Text("正在等待登录窗口完成验证…", size=theme.font_size("sm"), color=p.text_secondary),
            ], spacing=theme.space("2")) if self._busy else StatusBadge(p, "等待登录", "info")
            self._profile_card_content.controls = [
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=56, color=p.text_muted),
                        ft.Text("未登录", size=theme.font_size("xl"), weight=theme.WEIGHT_BOLD, color=p.text_secondary),
                        ft.Text("通过顶部操作添加蓝湖账号，登录完成后会自动读取账号资料。",
                                size=theme.font_size("sm"), color=p.text_muted),
                        waiting,
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
        cookie_valid = has_valid_auth_cookie(str(active.get("cookie") or ""))

        # Avatar + name header
        header = ft.Row([
            avatar(avatar_url, p, size=64),
            ft.Column([
                ft.Text(name, size=theme.font_size("xl"), weight=theme.WEIGHT_BOLD, color=p.text_primary),
                ft.Text(label, size=theme.font_size("sm"), color=p.text_muted),
            ], spacing=theme.space("1"), expand=True),
            StatusBadge(p, "登录有效" if cookie_valid else "需要重新登录", "ok" if cookie_valid else "warn"),
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

        action_buttons: List[ft.Control] = [
            secondary_button("同步浏览器 Cookie", lambda e: self._sync_default_browser_cookie(), icon=ft.Icons.SYNC),
        ]
        if account_count >= 2:
            action_buttons.append(
                secondary_button("切换账号", lambda e: self._show_switch_dialog(accounts), icon=ft.Icons.SWAP_HORIZ),
            )
        action_buttons.append(
            danger_button(p, "退出登录", lambda e: self._logout_active(active), icon=ft.Icons.LOGOUT),
        )

        controls = [header]
        if info_items:
            controls.append(ft.Divider(height=1, color=p.border_light))
            controls.append(ft.Column(info_items, spacing=theme.space("2")))
        else:
            controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=p.primary),
                        ft.Text("当前账号资料较少，可通过重新登录或手动 Cookie 补全。",
                                size=theme.font_size("xs"), color=p.text_muted, expand=True),
                    ], spacing=theme.space("2")),
                    bgcolor=p.primary_light,
                    border_radius=theme.radius("md"),
                    padding=theme.space("3"),
                )
            )
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
            self.ctx.notify_state_change("account")
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

    def _logout_active(self, active: Optional[dict]) -> None:
        p = self.ctx.palette
        if not active:
            return
        if self.ctx.service.is_running():
            toast(self.ctx.page, "服务运行中，请先停止服务再退出账号", "warn", p)
            return
        account_id = active.get("id", "")
        name = active.get("name") or accounts_core.account_primary_contact(active) or "蓝湖用户"
        accounts_core.remove_account(account_id)
        self.ctx.notify_state_change("account")
        self.ctx.add_log(f"[ACCOUNT] 已退出账号: {name}")
        toast(self.ctx.page, "已退出登录", "ok", p)
        self.refresh()

    # ── account stats ─────────────────────────────────────────────
    def _render_stats(self, accounts: list, active: Optional[dict]) -> ft.Control:
        p = self.ctx.palette
        valid = bool(active and has_valid_auth_cookie(str(active.get("cookie") or "")))
        return ft.Row([
            stat_chip(p, "已登录", str(len(accounts)), icon=ft.Icons.GROUP, accent=p.primary),
            stat_chip(p, "当前账号", accounts_core.account_primary_contact(active)[:12] if active else "无",
                      icon=ft.Icons.PERSON, accent=p.success),
            stat_chip(p, "会话", "有效" if valid else "待登录",
                      icon=ft.Icons.VERIFIED_USER, accent=p.success if valid else p.warning),
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
    def _sync_default_browser_cookie(self) -> None:
        """Read an already authenticated default-browser session without opening a new tab."""
        p = self.ctx.palette
        if self._busy:
            toast(self.ctx.page, "登录或同步正在进行，请稍候。", "info", p)
            return
        self._busy = True
        self.ctx.add_log("[LOGIN] 正在同步默认浏览器 Cookie")
        self.refresh()

        def work():
            cookie, browser_name, diagnostics = read_default_browser_cookie()
            if not cookie or not has_valid_auth_cookie(cookie):
                detail = "; ".join(diagnostics[-2:])
                return {
                    "ok": False,
                    "error": detail or "未在默认浏览器中读取到有效的蓝湖登录 Cookie。",
                }
            profile = accounts_core.user_info_from_cookie(cookie)
            _ok, message, api_profile = fetch_lanhu_user_profile(cookie)
            if api_profile:
                profile = accounts_core.merge_identity_info(api_profile, profile)
            return {
                "ok": True,
                "cookie": cookie,
                "profile": profile,
                "browser": browser_name,
                "profile_message": message,
            }

        def done(result):
            self._busy = False
            if result.get("ok"):
                account = accounts_core.upsert_account(result["cookie"], result.get("profile") or {})
                self.ctx.notify_state_change("account")
                label = accounts_core.account_primary_contact(account or {})
                browser_name = result.get("browser") or "默认浏览器"
                self.ctx.add_log(f"[LOGIN] 已从 {browser_name} 同步账号: {label}")
                toast(self.ctx.page, "浏览器登录状态已同步", "ok", p)
            else:
                error = str(result.get("error") or "未读取到有效浏览器 Cookie")
                self.ctx.add_log(f"[WARN] [LOGIN] {error}")
                toast(self.ctx.page, error, "warn", p)
            self.refresh()

        def err(exc):
            self._busy = False
            show_error(self.ctx.page, exc, "同步浏览器 Cookie", p, self.ctx.add_log)
            self.refresh()

        from ..components import run_in_background
        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _add_account(self) -> None:
        p = self.ctx.palette
        if self._busy:
            toast(self.ctx.page, "登录窗口正在运行，请先完成当前登录。", "info", p)
            return
        self._busy = True
        self.ctx.add_log("[LOGIN] 启动蓝湖一键登录…")
        self.refresh()

        def work():
            result = accounts_core.launch_login_helper(
                0,
                on_output=lambda line: self.ctx.add_log(line),
                on_error=lambda line: self.ctx.add_log(f"[ERR] {line}"),
            )
            if not isinstance(result, dict):
                return result
            cookie = str(result.get("cookies") or "")
            if result.get("status") == "success" and cookie:
                _ok, message, profile = fetch_lanhu_user_profile(cookie)
                login_profile = accounts_core.parse_user_payload(result)
                if profile:
                    merged_profile = accounts_core.merge_identity_info(profile, login_profile)
                    merged_profile["raw"] = {
                        key: value for key, value in result.items() if key != "user"
                    }
                    result["user"] = merged_profile
                result["profile_message"] = message
            return result

        def done(result):
            self._busy = False
            if not result:
                toast(self.ctx.page, "登录未完成", "warn", p)
                self.refresh()
                return
            status = str(result.get("status") or "") if isinstance(result, dict) else ""
            cookie = str(result.get("cookies") or "") if isinstance(result, dict) else ""
            if status == "success" and cookie:
                profile = accounts_core.parse_user_payload(result)
                account = accounts_core.upsert_account(cookie, profile)
                self.ctx.notify_state_change("account")
                label = accounts_core.account_primary_contact(account or profile) or "蓝湖用户"
                self.ctx.add_log(f"[LOGIN] 登录成功: {label}")
                toast(self.ctx.page, "登录成功，账号已保存", "ok", p)
            else:
                error = (result or {}).get("error") or "未检测到有效登录态，请在登录窗口完成登录后再关闭。"
                self.ctx.add_log(f"[ERR] [LOGIN] {error}")
                toast(self.ctx.page, error, "error", p)
            self.refresh()

        def err(exc):
            self._busy = False
            show_error(self.ctx.page, exc, "蓝湖登录", p, self.ctx.add_log)
            self.refresh()

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
                self.ctx.notify_state_change("account")
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

        top_actions = ft.Row([
            primary_button("一键登录", lambda e: self._add_account(), icon=ft.Icons.LOGIN),
            secondary_button("手动 Cookie", lambda e: self._add_manual_cookie(), icon=ft.Icons.COOKIE),
        ], spacing=theme.space("2"), wrap=True)

        header = ft.Container(
            content=ft.Column([
                page_banner(p, "账号", "登录管理 · 资料查看 · 账号切换", "accounts"),
                ft.Row([ft.Container(expand=True), top_actions], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=theme.space("3")),
            bgcolor=p.card,
        )
        body = ft.Column([stats_bar, profile_card], spacing=theme.space("4"))
        view = ft.ListView(
            controls=[
                header,
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


__all__ = ["AccountsPage"]
