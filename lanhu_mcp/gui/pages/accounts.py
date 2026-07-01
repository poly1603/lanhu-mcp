"""Accounts page (v2) — enriched login card, avatar avatar list, detail with status."""

from __future__ import annotations

import hashlib
import webbrowser
from typing import List, Optional

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, StatusBadge, CountBadge, stat_chip,
    primary_button, secondary_button, danger_button, field_row, empty_state,
    run_in_background, toast, show_error,
)
from ..state import AppContext
from ...core import accounts as accounts_core
from ...services.lanhu_api import fetch_lanhu_user_profile
from ...services.login_helper import run_login_helper


def _avatar_color(name: str) -> str:
    """Stable pastel color from name for avatar circles."""
    colors = ["#0052D9", "#00A870", "#ED7B2F", "#E34D59", "#00809A", "#F59D0A", "#7446D8", "#D9407A"]
    h = hashlib.md5(name.encode("utf-8")).hexdigest()
    idx = int(h[:2], 16) % len(colors)
    return colors[idx]


def _avatar_initial(name: str) -> str:
    return (name or "?")[0].upper()


class AccountsPage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._login_url_field = ft.TextField(label="登录地址", dense=True, expand=True)
        self._cookie_field = ft.TextField(
            label="手动 Cookie", dense=True, multiline=True, min_lines=2, max_lines=4, expand=True
        )
        self._account_list = ft.Column(spacing=theme.space("2"))
        self._detail_holder = ft.Column(spacing=theme.space("2"))
        self._render_sig = None

    # ── data ──────────────────────────────────────────────────────
    def _safe(self, fn, default):
        try:
            return fn()
        except Exception:
            return default

    def _accounts_signature(self, account_list, active, active_id: str) -> str:
        parts: List[str] = [f"active={active_id}", f"port={self.ctx.port}"]
        for acc in account_list or []:
            acc_id = acc.get("id", "")
            parts.append("|".join([
                str(acc_id),
                "1" if acc_id == active_id else "0",
                str(accounts_core.account_primary_contact(acc)),
                str(accounts_core.account_detail_line(acc)),
            ]))
        if active:
            parts.append("detail|" + "|".join(str(x) for x in (
                accounts_core.account_primary_contact(active),
                accounts_core.account_profile_line(active),
                accounts_core.account_cookie_line(active),
                accounts_core.account_cookie_expiry(active).get("status"),
            )))
        return "\n".join(parts)

    def _render_accounts(self) -> None:
        p = self.ctx.palette
        account_list = self._safe(accounts_core.get_accounts, [])
        active = self._safe(accounts_core.get_active_account, None)
        active_id = (active or {}).get("id", "") if active else ""

        signature = self._accounts_signature(account_list, active, active_id)
        if signature == self._render_sig and self._account_list.controls and self._detail_holder.controls:
            return
        self._render_sig = signature

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
                avatar_color = _avatar_color(contact or acc_id)
                actions: List[ft.Control] = []
                if is_active:
                    actions.append(StatusBadge(p, "使用中", "ok"))
                else:
                    actions.append(secondary_button("切换", lambda e, i=acc_id: self._switch(i), icon=ft.Icons.SWAP_HORIZ))
                actions.append(danger_button(p, "退出", lambda e, i=acc_id: self._remove(i), icon=ft.Icons.LOGOUT))

                # Avatar circle
                avatar = ft.Container(
                    content=ft.Text(_avatar_initial(contact or "L"), color="#FFFFFF",
                                    weight=theme.WEIGHT_BOLD, size=theme.font_size("lg")),
                    width=40, height=40, bgcolor=avatar_color,
                    border_radius=theme.radius("full"),
                    alignment=ft.alignment.center,
                )

                rows.append(
                    ft.Container(
                        content=ft.Row([
                            avatar,
                            ft.Column([
                                ft.Text(contact or "蓝湖用户", weight=theme.WEIGHT_MEDIUM, color=p.text_primary),
                                ft.Text(detail, size=theme.font_size("xs"), color=p.text_muted),
                            ], spacing=2, expand=True),
                            ft.Row(actions, spacing=theme.space("2")),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=theme.space("3")),
                        bgcolor=p.primary_light if is_active else None,
                        border=ft.border.all(1, p.primary if is_active else p.border_light),
                        border_radius=theme.radius("xl"),
                        padding=theme.space("4"),
                        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                    )
                )
            self._account_list.controls = rows

        # Active detailed panel
        if active:
            expiry = accounts_core.account_cookie_expiry(active)
            status_kind = {"valid": "ok", "expiring": "warn", "expired": "error"}.get(
                expiry.get("status"), "info")
            self._detail_holder.controls = [
                ft.Row([
                    ft.Text("账号资料", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Container(expand=True),
                    StatusBadge(p, accounts_core.account_cookie_status_line(active), status_kind),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
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

    # ── actions ───────────────────────────────────────────────────
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
            except Exception as exc:
                show_error(self.ctx.page, exc, "打开浏览器", self.ctx.palette, self.ctx.add_log)

    def _quick_login(self) -> None:
        url = (self._login_url_field.value or "").strip() or self._safe(accounts_core.get_saved_login_url, "")
        self._save_login_url()
        toast(self.ctx.page, "正在打开蓝湖登录窗口…", "info", self.ctx.palette)
        self.ctx.add_log("=== 一键登录开始 ===")

        def work():
            return run_login_helper(url)

        def done(result):
            if not isinstance(result, dict):
                self.ctx.add_log("登录助手未返回有效结果")
                toast(self.ctx.page, "登录失败", "error", self.ctx.palette)
                return
            diagnostics = result.get("diagnostics")
            if isinstance(diagnostics, list):
                for item in diagnostics[-4:]:
                    self.ctx.add_log(f"登录诊断: {item}")
            if result.get("status") == "success" and result.get("cookies"):
                cookie = str(result.get("cookies", ""))
                user_info = self._safe(lambda: accounts_core.parse_user_payload(result), {})
                account = self._safe(lambda: accounts_core.upsert_account(cookie, user_info), None)
                name = (user_info or {}).get("name") or "蓝湖用户"
                self.ctx.add_log(f"[OK] 登录成功，用户: {name}")
                toast(self.ctx.page, f"登录成功：{name}", "ok", self.ctx.palette)
                self.refresh()
                self._enrich_profile(cookie)
                return
            error = str(result.get("error") or "").strip()
            if error:
                self.ctx.add_log(f"登录失败: {error}")
                toast(self.ctx.page, f"登录失败：{error}", "error", self.ctx.palette)
                if url:
                    try:
                        webbrowser.open(url)
                    except Exception:
                        pass
                return
            self.ctx.add_log("未检测到蓝湖登录，登录窗口已关闭或超时")
            toast(self.ctx.page, "未检测到登录，窗口已关闭或超时", "warn", self.ctx.palette)

        def err(exc):
            show_error(self.ctx.page, exc, "一键登录", self.ctx.palette, self.ctx.add_log)

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _enrich_profile(self, cookie: str) -> None:
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

        def err(exc):
            show_error(self.ctx.page, exc, "读取用户资料", self.ctx.palette, self.ctx.add_log)
            self.refresh()

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

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
        self._enrich_profile(cookie)

    # ── view ──────────────────────────────────────────────────────
    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._login_url_field.value = self._safe(accounts_core.get_saved_login_url, "")
        self._render_accounts()

        # ── Login card ──
        login_card = gradient_card(
            p,
            ft.Column([
                ft.Text("登录", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                ft.Row([
                    self._login_url_field,
                    secondary_button("保存", lambda e: self._save_login_url(), icon=ft.Icons.SAVE),
                ], spacing=theme.space("2")),
                ft.Row([
                    primary_button("一键登录", lambda e: self._quick_login(), icon=ft.Icons.LOGIN),
                    secondary_button("浏览器登录", lambda e: self._open_login(), icon=ft.Icons.OPEN_IN_NEW),
                    ft.Container(expand=True),
                    secondary_button("清空缓存", lambda e: self._clear_cache(), icon=ft.Icons.DELETE_OUTLINE,
                                    disabled=True),  # not yet implemented
                ], spacing=theme.space("2")),
                ft.Divider(height=1, color=p.border_light),
                self._cookie_field,
                ft.Row([primary_button("保存 Cookie", lambda e: self._save_cookie(), icon=ft.Icons.ADD),
                        ft.Text("或粘贴已登录的 Cookie 数据", size=theme.font_size("xs"), color=p.text_muted)],
                       spacing=theme.space("2")),
            ], spacing=theme.space("3")),
        )

        # ── Account list card ──
        n_accounts = len(self._safe(accounts_core.get_accounts, []))
        accounts_header = ft.Row([
            ft.Text("已登录账号", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
            ft.Container(expand=True),
            CountBadge(p, n_accounts, "info"),
        ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER)

        accounts_card = card(p, ft.Column([accounts_header, self._account_list], spacing=theme.space("3")))

        # ── Detail card ──
        detail_card = card(p, self._detail_holder)

        return ft.Column(
            [
                section_title(p, "账号", "登录 · 切换 · 管理蓝湖账号"),
                login_card,
                accounts_card,
                detail_card,
            ],
            spacing=theme.space("6"),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _clear_cache(self) -> None:
        toast(self.ctx.page, "缓存已清空（功能待实现）", "info", self.ctx.palette)


__all__ = ["AccountsPage"]
