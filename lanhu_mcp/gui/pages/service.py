"""Service page — MCP service control with method cards and inline testing."""

from __future__ import annotations

import json
import time
from typing import List, Optional

import flet as ft

from .. import theme
from ..components import (
    section_title, card, gradient_card, page_frame, responsive_pair, StatusBadge, CountBadge,
    primary_button, secondary_button, danger_button, ghost_icon_button,
    stat_chip,
    run_in_background, toast, show_error,
)
from ..state import AppContext
from ...core import accounts as accounts_core
from ...core import projects as projects_core
from ...core.paths import is_port_in_use
from ...services.ide_config import mcp_config_snippets
from ...services.tools_registry import discover_mcp_tools, group_mcp_tools, tool_argument_specs
from lanhu_login_helper import has_valid_auth_cookie


MCP_URL_MAP: dict = {}


class ServicePage:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._status_holder = ft.Row(spacing=theme.space("2"))
        self._health_section = ft.Row(spacing=theme.space("4"), wrap=True)
        self._action_holder = ft.Row(spacing=theme.space("3"), wrap=True)
        self._url_text = ft.Text(selectable=True, size=theme.font_size("sm"))
        self._methods_container = ft.Column(spacing=theme.space("3"))
        self._busy = False
        self._started_at: Optional[float] = None
        self._test_results: dict = {}
        self._notice_holder = ft.Column(spacing=theme.space("2"))
        self._last_start_error = ""
        self._health_label = "待检查"

    def _mcp_url(self) -> str:
        try:
            cached = MCP_URL_MAP.get(self.ctx.port)
            if cached:
                return cached
            return accounts_core.current_mcp_url(self.ctx.port)
        except Exception:
            return f"http://localhost:{self.ctx.port}/mcp"

    def _display_endpoint(self) -> str:
        """Keep the main service surface readable; configs retain the full URL."""
        return f"http://localhost:{self.ctx.port}/mcp"

    def _suggest_available_port(self) -> Optional[int]:
        """Find a nearby unused local port for one-click recovery."""
        start = max(1024, min(int(self.ctx.port) + 1, 65535))
        for candidate in range(start, min(start + 16, 65536)):
            if not is_port_in_use(candidate):
                return candidate
        return None

    def _use_available_port(self) -> None:
        candidate = self._suggest_available_port()
        if candidate is None:
            toast(self.ctx.page, "附近端口均不可用，请在顶部手动设置端口。", "warn", self.ctx.palette)
            return
        previous = self.ctx.port
        self.ctx.set_port(candidate)
        self._last_start_error = ""
        self._health_label = "待检查"
        self.ctx.add_log(f"[SERVICE] 端口从 {previous} 切换为 {candidate}")
        self._render_status()
        try:
            self.ctx.page.update()
        except Exception:
            pass
        toast(self.ctx.page, f"已切换到可用端口 {candidate}", "ok", self.ctx.palette)

    def _show_logs(self) -> None:
        if self.ctx.navigate:
            self.ctx.navigate("logs")

    def _copy_endpoint(self) -> None:
        try:
            self.ctx.page.set_clipboard(self._mcp_url())
            toast(self.ctx.page, "MCP 地址已复制", "ok", self.ctx.palette)
        except Exception as exc:
            show_error(self.ctx.page, exc, "复制 MCP 地址", self.ctx.palette, self.ctx.add_log)

    def _render_notice(self) -> None:
        p = self.ctx.palette
        message = self._last_start_error.strip()
        if not message:
            self._notice_holder.controls = []
            return

        is_port_error = "端口" in message and "占用" in message
        title = "端口不可用" if is_port_error else "服务未能启动"
        actions: List[ft.Control] = [
            secondary_button("查看日志", lambda _event: self._show_logs(), icon=ft.Icons.ARTICLE_OUTLINED),
        ]
        if is_port_error:
            candidate = self._suggest_available_port()
            if candidate is not None:
                actions.insert(
                    0,
                    primary_button(f"改用 {candidate}", lambda _event: self._use_available_port(), icon=ft.Icons.SWAP_HORIZ),
                )

        self._notice_holder.controls = [
            ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.ERROR_OUTLINE, size=18, color=p.warning),
                        bgcolor=p.warning_light,
                        border_radius=theme.radius("md"),
                        width=36,
                        height=36,
                        alignment=ft.alignment.center,
                    ),
                    ft.Column([
                        ft.Text(title, size=theme.font_size("sm"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                        ft.Text(message, size=theme.font_size("xs"), color=p.text_secondary, max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=0, expand=True),
                    ft.Row(actions, spacing=theme.space("2"), wrap=True),
                ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER, wrap=True),
                bgcolor=p.warning_light,
                border=ft.border.all(1, theme.alpha(p.warning, 0x55)),
                border_radius=theme.radius("lg"),
                padding=theme.space("3"),
                animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            )
        ]

    def _uptime(self) -> str:
        if not self._started_at:
            return "—"
        elapsed = int(time.time() - self._started_at)
        if elapsed < 60:
            return f"{elapsed}s"
        if elapsed < 3600:
            return f"{elapsed // 60}m {elapsed % 60}s"
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        return f"{h}h {m}m"

    def _render_status(self) -> None:
        p = self.ctx.palette
        running = self.ctx.service.is_running()
        self._status_holder.controls = [
            StatusBadge(p, "运行中" if running else "已停止", "ok" if running else "idle"),
            StatusBadge(p, f"端口 {self.ctx.port}", "info"),
        ]
        self._url_text.value = self._display_endpoint()
        self._url_text.color = p.text_primary

        uptime = self._uptime()
        health_color = p.success if self._health_label == "可用" else (p.danger if self._health_label == "异常" else p.warning)
        try:
            active = accounts_core.get_active_account()
        except Exception:
            active = None
        account_label = accounts_core.account_primary_contact(active) if active else "未登录"
        self._health_section.controls = [
            stat_chip(p, "运行时长", uptime, icon=ft.Icons.TIMER, accent=p.accent),
            stat_chip(p, "MCP 端点", "/mcp", icon=ft.Icons.LINK, accent=p.primary),
            stat_chip(p, "地址", f"localhost:{self.ctx.port}", icon=ft.Icons.ROUTER, accent=p.warning),
            stat_chip(p, "连通性", self._health_label, icon=ft.Icons.MONITOR_HEART, accent=health_color),
            stat_chip(p, "账号", account_label[:18], icon=ft.Icons.PERSON_OUTLINE, accent=p.primary),
        ]

        if self._busy:
            self._action_holder.controls = [
                ft.Row([ft.ProgressRing(width=16, height=16),
                        ft.Text("处理中…", color=p.text_secondary)], spacing=theme.space("2"))
            ]
        elif running:
            self._action_holder.controls = [
                danger_button(p, "停止服务", lambda e: self._stop(), icon=ft.Icons.STOP),
                secondary_button("健康检查", lambda e: self._health_check(), icon=ft.Icons.MONITOR_HEART),
                secondary_button("复制接入配置", lambda e: self._show_config(), icon=ft.Icons.CONTENT_COPY),
            ]
        else:
            self._action_holder.controls = [
                primary_button("启动服务", lambda e: self._start(), icon=ft.Icons.PLAY_ARROW),
                secondary_button("复制接入配置", lambda e: self._show_config(), icon=ft.Icons.CONTENT_COPY),
            ]
        self._render_notice()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._render_status()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    # ── start / stop ──────────────────────────────────────────────
    def _start(self) -> None:
        if self._busy:
            toast(self.ctx.page, "服务正在处理中，请稍候。", "info", self.ctx.palette)
            return
        active = None
        try:
            active = accounts_core.get_active_account()
        except Exception:
            active = None
        if not active or not has_valid_auth_cookie(str(active.get("cookie") or "")):
            toast(self.ctx.page, "请先在账号页登录蓝湖账号", "warn", self.ctx.palette)
            if self.ctx.navigate:
                self.ctx.navigate("accounts")
            return
        self._set_busy(True)

        def work():
            return self.ctx.service.start(
                port=self.ctx.port,
                on_output=lambda line: self.ctx.add_log(line),
                on_error=lambda line: self.ctx.add_log(f"[ERR] {line}"),
            )

        def done(result):
            self._busy = False
            ok, msg = result if isinstance(result, tuple) else (bool(result), "")
            if ok:
                self._started_at = time.time()
                MCP_URL_MAP[self.ctx.port] = self._mcp_url()
                self._last_start_error = ""
                self._health_label = "待检查"
            else:
                self._started_at = None
                self._last_start_error = msg or "服务启动失败"
                self._health_label = "异常"
            self.ctx.add_log(msg or ("服务已启动" if ok else "服务启动失败"))
            toast(self.ctx.page, msg or ("服务已启动" if ok else "服务启动失败"),
                  "ok" if ok else "error", self.ctx.palette)
            self._render_status()
            self._build_methods()
            self.ctx.notify_state_change("service")
            self.ctx.page.update()

        def err(exc):
            self._busy = False
            self._last_start_error = str(exc)
            self._health_label = "异常"
            show_error(self.ctx.page, exc, "服务启动", self.ctx.palette, self.ctx.add_log)
            self._render_status()

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _stop(self) -> None:
        if self._busy:
            toast(self.ctx.page, "服务正在处理中，请稍候。", "info", self.ctx.palette)
            return
        self._set_busy(True)

        def work():
            return self.ctx.service.stop()

        def done(result):
            self._busy = False
            self._started_at = None
            self._last_start_error = ""
            self._health_label = "待检查"
            ok, msg = result if isinstance(result, tuple) else (bool(result), "")
            self.ctx.add_log(msg or ("服务已停止" if ok else "停止失败"))
            toast(self.ctx.page, msg or ("服务已停止" if ok else "停止失败"),
                  "ok" if ok else "error", self.ctx.palette)
            self._render_status()
            self._build_methods()
            self.ctx.notify_state_change("service")
            self.ctx.page.update()

        def err(exc):
            self._busy = False
            show_error(self.ctx.page, exc, "服务停止", self.ctx.palette, self.ctx.add_log)
            self._render_status()

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    # ── health check ──────────────────────────────────────────────
    def _health_check(self) -> None:
        url = self._mcp_url()
        self.ctx.add_log(f"健康检查: {url}")
        toast(self.ctx.page, "正在检查 MCP 服务…", "info", self.ctx.palette)

        def work():
            import httpx
            response = httpx.get(url, timeout=5.0, headers={"Accept": "text/event-stream"})
            return response.status_code

        def done(status):
            alive = isinstance(status, int) and status < 500
            self._health_label = "可用" if alive else "异常"
            message = f"服务可达 (HTTP {status})" if alive else f"服务异常 (HTTP {status})"
            self.ctx.add_log(message)
            toast(self.ctx.page, message, "ok" if alive else "error", self.ctx.palette)
            self._render_status()

        def err(exc):
            self._health_label = "异常"
            show_error(self.ctx.page, exc, "健康检查", self.ctx.palette, self.ctx.add_log)
            self._render_status()

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    # ── test a single method ──────────────────────────────────────
    def _test_method(self, method_name: str) -> None:
        if not self.ctx.service.is_running():
            toast(self.ctx.page, "请先启动 MCP 服务", "warn", self.ctx.palette)
            return
        p = self.ctx.palette
        specs = tool_argument_specs(method_name)
        try:
            active = accounts_core.get_active_account() or {}
            projects = projects_core.cached_projects_for_account(str(active.get("id") or ""))
        except Exception:
            projects = []
        project_index = {
            f"{item.get('team_id') or '-'} / {item.get('id') or '-'} / {item.get('name') or '未命名项目'}": item
            for item in projects
        }
        fields: dict[str, ft.TextField] = {}
        controls: List[ft.Control] = []
        project_selector: Optional[ft.Dropdown] = None
        if project_index:
            project_selector = ft.Dropdown(
                label="操作项目",
                hint_text="选择后自动填充 project_id 和 team_id",
                options=[ft.DropdownOption(key, key) for key in project_index],
                dense=True,
                enable_filter=True,
                width=620,
            )
            controls.append(project_selector)
        for spec in specs:
            name = str(spec["name"])
            required = bool(spec["required"])
            default = spec.get("default")
            fields[name] = ft.TextField(
                label=f"{name}{' *' if required else ''}",
                hint_text=f"{spec.get('annotation') or 'str'}" + (f"; default {default}" if default is not None else ""),
                value="" if default is None else str(default).strip("'\""),
                dense=True,
                width=620,
            )
            controls.append(fields[name])
        if not specs:
            controls.append(ft.Text("此方法没有声明参数。", size=theme.font_size("sm"), color=p.text_muted))

        def apply_project(_event) -> None:
            selected = project_index.get(str(project_selector.value or "")) if project_selector else None
            if not selected:
                return
            for field_name, project_key in (("project_id", "id"), ("pid", "id"), ("team_id", "team_id"), ("tid", "team_id")):
                if field_name in fields:
                    fields[field_name].value = str(selected.get(project_key) or "")
            self.ctx.page.update()

        if project_selector is not None:
            project_selector.on_change = apply_project

        def close_dialog() -> None:
            try:
                self.ctx.page.close(dialog)
            except Exception:
                dialog.open = False
                self.ctx.page.update()

        def submit(_event) -> None:
            arguments: dict[str, object] = {}
            missing: list[str] = []
            for spec in specs:
                name = str(spec["name"])
                value = str(fields[name].value or "").strip()
                if not value:
                    if bool(spec["required"]):
                        missing.append(name)
                    continue
                arguments[name] = self._coerce_argument(value, str(spec.get("annotation") or ""))
            if missing:
                toast(self.ctx.page, f"请填写必填参数: {', '.join(missing)}", "warn", p)
                return
            close_dialog()
            self._invoke_method(method_name, arguments)

        dialog = ft.AlertDialog(
            title=ft.Text(f"调用 {method_name}", color=p.text_primary),
            content=ft.Container(
                width=660,
                content=ft.Column([
                    ft.Text("选择操作对象，并填写其余必要参数。", size=theme.font_size("sm"), color=p.text_secondary),
                    *controls,
                ], spacing=theme.space("3"), scroll=ft.ScrollMode.AUTO, tight=True),
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda _event: close_dialog()),
                ft.FilledButton("调用方法", icon=ft.Icons.PLAY_ARROW, on_click=submit),
            ],
        )
        self.ctx.page.open(dialog)

    @staticmethod
    def _coerce_argument(value: str, annotation: str) -> object:
        normalized = annotation.lower()
        if "bool" in normalized:
            return value.lower() in {"1", "true", "yes", "on"}
        if "int" in normalized and value.lstrip("-").isdigit():
            return int(value)
        if "float" in normalized:
            try:
                return float(value)
            except ValueError:
                pass
        if any(token in normalized for token in ("list", "dict", "mapping", "sequence")):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    def _invoke_method(self, method_name: str, arguments: dict[str, object]) -> None:
        url = self._mcp_url()
        self.ctx.add_log(f"[MCP] tools/call {method_name} arguments={json.dumps(arguments, ensure_ascii=False)}")
        self._test_results[method_name] = {"status": "loading"}
        self._build_methods()
        self.ctx.page.update()

        def work():
            import httpx
            initialize_payload = {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "Lanhu MCP GUI", "version": "1.0"},
                },
            }
            call_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": method_name, "arguments": arguments},
            }
            headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
            with httpx.Client(timeout=30.0) as client:
                initialize_response = client.post(url, json=initialize_payload, headers=headers)
                if initialize_response.status_code >= 400:
                    return initialize_response.status_code, initialize_response.text[:12000]
                session_id = initialize_response.headers.get("mcp-session-id")
                if not session_id:
                    raise RuntimeError("MCP initialize did not return a session ID")
                session_headers = dict(headers)
                session_headers["Mcp-Session-Id"] = session_id
                initialized_payload = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
                initialized_response = client.post(url, json=initialized_payload, headers=session_headers)
                if initialized_response.status_code >= 400:
                    return initialized_response.status_code, initialized_response.text[:12000]
                response = client.post(url, json=call_payload, headers=session_headers)
                return response.status_code, response.text[:12000]

        def done(result) -> None:
            status_code, body = result
            rpc_error = False
            try:
                payload_candidates = [body]
                payload_candidates.extend(
                    line[5:].strip() for line in body.splitlines() if line.strip().startswith("data:")
                )
                parsed_payload = {}
                for candidate in reversed(payload_candidates):
                    try:
                        parsed_payload = json.loads(candidate)
                        break
                    except json.JSONDecodeError:
                        continue
                result_payload = parsed_payload.get("result") if isinstance(parsed_payload, dict) else {}
                rpc_error = bool(
                    isinstance(parsed_payload, dict) and parsed_payload.get("error")
                    or isinstance(result_payload, dict) and result_payload.get("isError")
                )
            except (AttributeError, TypeError):
                rpc_error = False
            ok = isinstance(status_code, int) and status_code < 400 and not rpc_error
            self._test_results[method_name] = {
                "status": "ok" if ok else "error",
                "code": status_code,
                "body": body,
            }
            self.ctx.add_log(f"[MCP] {method_name} -> HTTP {status_code} {'OK' if ok else 'ERROR'}")
            self._build_methods()
            self.ctx.notify_state_change("mcp_call")
            self.ctx.page.update()
            self._show_call_result(method_name, arguments, status_code, body, ok)

        def err(exc) -> None:
            body = str(exc)[:1000]
            self._test_results[method_name] = {"status": "error", "body": body}
            self.ctx.add_log(f"[MCP] {method_name} failed: {body}")
            self._build_methods()
            self.ctx.notify_state_change("mcp_call")
            self.ctx.page.update()
            self._show_call_result(method_name, arguments, 0, body, False)

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    def _show_call_result(self, method_name: str, arguments: dict[str, object], status_code: int, body: str, ok: bool) -> None:
        p = self.ctx.palette
        output = ft.TextField(value=body, read_only=True, multiline=True, min_lines=12, max_lines=16, text_size=theme.font_size("xs"))

        def close_dialog() -> None:
            try:
                self.ctx.page.close(dialog)
            except Exception:
                dialog.open = False
                self.ctx.page.update()

        def copy_result(_event) -> None:
            try:
                self.ctx.page.set_clipboard(body)
                toast(self.ctx.page, "已复制调用结果", "ok", p)
            except Exception as exc:
                show_error(self.ctx.page, exc, "复制 MCP 调用结果", p, self.ctx.add_log)

        dialog = ft.AlertDialog(
            title=ft.Text(f"{method_name} · {'成功' if ok else '失败'}", color=p.success if ok else p.danger),
            content=ft.Container(width=760, content=ft.Column([
                ft.Text(f"HTTP {status_code} · {json.dumps(arguments, ensure_ascii=False)}", size=theme.font_size("xs"), color=p.text_muted, selectable=True),
                output,
            ], spacing=theme.space("2"), tight=True)),
            actions=[
                ft.TextButton("关闭", on_click=lambda _event: close_dialog()),
                ft.FilledButton("复制结果", icon=ft.Icons.CONTENT_COPY, on_click=copy_result),
            ],
        )
        self.ctx.page.open(dialog)

    def _show_config(self) -> None:
        p = self.ctx.palette
        try:
            snippets = mcp_config_snippets(self.ctx.port)
        except Exception:
            snippets = []

        def copy(text: str) -> None:
            try:
                self.ctx.page.set_clipboard(text)
                toast(self.ctx.page, "配置已复制", "ok", p)
            except Exception as exc:
                show_error(self.ctx.page, exc, "复制配置", p, self.ctx.add_log)

        blocks: List[ft.Control] = []
        for label, text in snippets:
            blocks.append(ft.Column([
                ft.Row([
                    ft.Text(label, weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary, expand=True),
                    ghost_icon_button(ft.Icons.CONTENT_COPY, lambda e, t=text: copy(t), tooltip="复制"),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(
                    content=ft.Text(text, selectable=True, size=theme.font_size("xs"),
                                    color=p.text_secondary, font_family=theme.FONT_MONO),
                    bgcolor=p.surface, border=ft.border.all(1, p.border_light),
                    border_radius=theme.radius("sm"), padding=theme.space("3"),
                ),
            ], spacing=theme.space("2")))

        dlg = ft.AlertDialog(
            title=ft.Text("MCP 接入配置", color=p.text_primary),
            content=ft.Container(
                width=560,
                content=ft.Column(blocks, spacing=theme.space("4"), scroll=ft.ScrollMode.AUTO, tight=True),
            ),
            actions=[ft.TextButton("关闭", on_click=lambda e: self._close_dialog(dlg))],
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

    # ── lifecycle ─────────────────────────────────────────────────
    def refresh(self) -> None:
        self._render_status()
        self._build_methods()
        try:
            self.ctx.page.update()
        except Exception:
            pass

    def _build_methods(self) -> None:
        p = self.ctx.palette
        running = self.ctx.service.is_running()

        try:
            tools = discover_mcp_tools()
            groups = group_mcp_tools(tools)
        except Exception:
            tools, groups = [], {}

        # Keep the stopped state informative without duplicating the primary
        # start action that already lives in the service control card.
        if not running:
            group_chips: List[ft.Control] = []
            for group_name, items in groups.items():
                if not items:
                    continue
                group_chips.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text(group_name, size=theme.font_size("xs"), color=p.text_secondary),
                            CountBadge(p, len(items), "info"),
                        ], spacing=theme.space("2"), tight=True),
                        bgcolor=p.surface,
                        border=ft.border.all(1, p.border_light),
                        border_radius=theme.radius("full"),
                        padding=ft.padding.symmetric(horizontal=theme.space("3"), vertical=theme.space("2")),
                    )
                )
            self._methods_container.controls = [
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.Icons.EXTENSION_OUTLINED, size=26, color=p.primary),
                            bgcolor=p.primary_light,
                            border_radius=theme.radius("full"),
                            width=54,
                            height=54,
                            alignment=ft.alignment.center,
                        ),
                        ft.Column([
                            ft.Row([
                                ft.Text("MCP 工具目录", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                                CountBadge(p, len(tools), "info"),
                            ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Text("服务启动后即可使用、检查并测试当前账号可访问的方法。",
                                    size=theme.font_size("sm"), color=p.text_muted),
                            ft.Row(group_chips, spacing=theme.space("2"), run_spacing=theme.space("2"), wrap=True) if group_chips else ft.Container(),
                        ], spacing=theme.space("1"), expand=True),
                    ], spacing=theme.space("4"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=p.card,
                    border=ft.border.all(1, p.border_light),
                    border_radius=theme.radius("xl"),
                    padding=theme.space("4"),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=8, color=p.shadow_sm, offset=ft.Offset(0, 3)),
                ),
            ]
            return

        group_controls: List[ft.Control] = []
        for group_name, items in groups.items():
            if not items:
                continue
            method_cards: List[ft.Control] = []
            for name, summary in items:
                test_info = self._test_results.get(name, {})
                test_status = test_info.get("status", "")
                method_cards.append(self._method_card(p, name, summary, test_status, test_info))
            badge = CountBadge(p, len(items), "info")
            methods_grid = ft.ResponsiveRow(
                [ft.Container(content=card, col={"sm": 12, "md": 6, "lg": 4}) for card in method_cards],
                spacing=theme.space("2"),
                run_spacing=theme.space("2"),
            )
            group_controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(group_name, size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                            badge,
                        ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Divider(height=1, color=p.border_light),
                        methods_grid,
                    ], spacing=theme.space("3")),
                    bgcolor=p.card,
                    border=ft.border.all(1, p.border_light),
                    border_radius=theme.radius("xl"),
                    padding=theme.space("5"),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=4, color=p.shadow_sm, offset=ft.Offset(0, 2)),
                )
            )

        header = ft.Row([
            ft.Text("支持的 MCP 方法", size=theme.font_size("xl"), weight=theme.WEIGHT_BOLD, color=p.text_primary),
            ft.Container(expand=True),
            CountBadge(p, len(tools), "info"),
        ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self._methods_container.controls = [header] + group_controls

    def _method_card(self, p, name: str, summary: str, test_status: str, test_info: dict) -> ft.Container:
        # Status indicator
        if test_status == "loading":
            status_widget = ft.ProgressRing(width=16, height=16, stroke_width=2)
        elif test_status == "ok":
            status_widget = ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=p.success)
        elif test_status == "error":
            status_widget = ft.Icon(ft.Icons.ERROR_OUTLINE, size=16, color=p.danger)
        else:
            status_widget = ft.Container(width=16, height=16)

        # Short display name
        display_name = name.replace("lanhu_", "").replace("_", " ")

        test_btn = ghost_icon_button(
            ft.Icons.PLAY_CIRCLE_OUTLINE,
            lambda e, n=name: self._test_method(n),
            tooltip="测试调用",
        )

        result_text = None
        if test_info.get("body"):
            body = test_info["body"][:120]
            code = test_info.get("code", "")
            result_text = ft.Text(
                f"HTTP {code}: {body}" if code else body,
                size=theme.font_size("xs"),
                color=p.success if test_status == "ok" else p.danger,
                font_family=theme.FONT_MONO,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            )

        content_items = [
            ft.Row([
                status_widget,
                ft.Text(display_name, size=theme.font_size("sm"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary, expand=True),
                test_btn,
            ], spacing=theme.space("2"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text(summary, size=theme.font_size("xs"), color=p.text_muted, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        ]
        if result_text:
            content_items.append(result_text)

        return ft.Container(
            content=ft.Column(content_items, spacing=theme.space("1")),
            padding=ft.padding.symmetric(horizontal=theme.space("3"), vertical=theme.space("2")),
            border_radius=theme.radius("md"),
            bgcolor=p.success_light if test_status == "ok" else (p.danger_light if test_status == "error" else p.surface),
            border=ft.border.all(1, p.border_light),
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

    def _service_step(self, p, index: str, title: str, desc: str, icon: str, accent: str) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(icon, size=18, color=accent),
                    bgcolor=theme.alpha(accent, 0x16),
                    border_radius=theme.radius("md"),
                    width=38,
                    height=38,
                    alignment=ft.alignment.center,
                ),
                ft.Column([
                    ft.Text(f"{index}. {title}", size=theme.font_size("sm"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    ft.Text(desc, size=theme.font_size("xs"), color=p.text_muted, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=0, expand=True),
            ], spacing=theme.space("3"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=p.surface,
            border_radius=theme.radius("lg"),
            padding=theme.space("3"),
        )

    # ── view ──────────────────────────────────────────────────────
    def build(self) -> ft.Control:
        p = self.ctx.palette
        self._render_status()

        running = self.ctx.service.is_running()

        # ── Service control card ──────────────────────────────────
        control_card = gradient_card(
            p,
            ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.DNS if running else ft.Icons.HOURGLASS_EMPTY,
                            color="#FFFFFF", size=28,
                        ),
                        gradient=ft.LinearGradient(
                            begin=ft.alignment.top_left, end=ft.alignment.bottom_right,
                            colors=[p.success, p.primary] if running else [p.text_muted, p.surface_hover],
                        ),
                        border_radius=theme.radius("lg"),
                        padding=theme.space("3"),
                        width=52, height=52,
                        alignment=ft.alignment.center,
                    ),
                    ft.Column([
                        ft.Text("MCP 服务控制", size=theme.font_size("xl"),
                                weight=theme.WEIGHT_BOLD, color=p.text_primary),
                        ft.Row([
                            ft.Text(self._url_text.value or "", size=theme.font_size("sm"),
                                    color=p.text_muted, selectable=True, max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                            ghost_icon_button(ft.Icons.CONTENT_COPY, lambda _event: self._copy_endpoint(),
                                              tooltip="复制 MCP 地址"),
                        ], spacing=theme.space("1"), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ], spacing=theme.space("1"), expand=True),
                    ft.Column([self._status_holder], horizontal_alignment=ft.CrossAxisAlignment.END),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=theme.space("4")),
                ft.Divider(height=1, color=p.border_light),
                self._action_holder,
                self._notice_holder,
            ], spacing=theme.space("4")),
        )

        # ── Health info card ──────────────────────────────────────
        info_card = gradient_card(
            p,
            ft.Column([
                ft.Text("服务信息", size=theme.font_size("lg"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                self._health_section,
            ], spacing=theme.space("3")),
        )

        steps_card = ft.Container(
            content=ft.ResponsiveRow([
                ft.Container(content=self._service_step(p, "1", "启动服务", "确认账号有效后启动本地 MCP HTTP 服务", ft.Icons.PLAY_ARROW, p.success), col={"sm": 12, "md": 4}),
                ft.Container(content=self._service_step(p, "2", "复制配置", "把当前端点写入 Cursor、Trae、Claude 等工具", ft.Icons.CONTENT_COPY, p.primary), col={"sm": 12, "md": 4}),
                ft.Container(content=self._service_step(p, "3", "测试方法", "在服务运行后验证工具方法是否可正常调用", ft.Icons.RULE, p.accent), col={"sm": 12, "md": 4}),
            ], spacing=theme.space("3"), run_spacing=theme.space("3")),
            bgcolor=p.card,
            border=ft.border.all(1, p.border_light),
            border_radius=theme.radius("xl"),
            padding=theme.space("4"),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=8, color=p.shadow_sm, offset=ft.Offset(0, 3)),
        )

        # ── Methods section ───────────────────────────────────────
        self._build_methods()

        body = ft.Column([
            responsive_pair(control_card, info_card, spacing=theme.space("4")),
            steps_card,
            self._methods_container,
        ], spacing=theme.space("5"))

        return page_frame(p, "服务", "启动 MCP 服务 · 健康监控 · 方法清单与测试", body)


__all__ = ["ServicePage"]
