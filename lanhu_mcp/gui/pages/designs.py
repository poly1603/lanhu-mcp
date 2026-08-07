"""Design browser dialog (v2) — enriched with progress bar, checkmark selection."""

from __future__ import annotations

import base64
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import flet as ft

from .. import theme
from ..components import run_in_background, toast, show_error
from ..state import AppContext
from ...core import accounts as accounts_core
from ...services.lanhu_api import _fetch_designs_api, _download_image_bytes

THUMB_MAX_BYTES = 2 * 1024 * 1024
THUMB_CONCURRENCY = 4


class DesignBrowser:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._dialog: Optional[ft.AlertDialog] = None
        self._grid = ft.GridView(expand=True, runs_count=3, max_extent=260,
                                  child_aspect_ratio=0.8, spacing=12, run_spacing=12)
        self._status = ft.Text("正在加载设计稿…", color=ctx.palette.text_muted,
                               size=theme.font_size("sm"))
        self._progress = ft.ProgressBar(width=200, visible=False)
        self._designs: List[dict] = []
        self._selected: Dict[str, dict] = {}
        self._project_name = ""
        self._cookie = ""
        self._thumb_cache: Dict[str, str] = {}
        self._thumb_pool: Optional[ThreadPoolExecutor] = None
        self._thumb_lock = threading.Lock()
        self._pending_update = False
        self._thumb_total = 0
        self._thumb_done = 0
        self._sector_filter = "__all__"
        self._sector_bar = ft.Row(spacing=theme.space("2"), wrap=True)

    # ── public ────────────────────────────────────────────────────
    def open_for(self, project_id: str, team_id: str, project_name: str) -> None:
        try:
            active = accounts_core.get_active_account()
        except Exception:
            active = None
        if not active or not active.get("cookie"):
            toast(self.ctx.page, "请先登录蓝湖账号", "warn", self.ctx.palette)
            return
        self._cookie = active["cookie"]
        self._project_name = project_name or "设计稿"
        self._designs = []
        self._selected = {}
        self._thumb_total = 0
        self._thumb_done = 0
        self._sector_filter = "__all__"
        self._sector_bar = ft.Row(spacing=theme.space("2"), wrap=True)
        self._grid.controls = []
        self._status.value = "正在加载设计稿…"
        self._progress.visible = True
        self._progress.value = None  # indeterminate

        self._dialog = self._build_dialog()
        self.ctx.page.open(self._dialog)
        self.ctx.page.update()

        def work():
            return _fetch_designs_api(self._cookie, project_id, team_id or "")

        def done(result):
            if not isinstance(result, dict) or result.get("status") != "success":
                msg = (result or {}).get("message", "未知错误") if isinstance(result, dict) else "请求失败"
                self._status.value = f"加载失败：{msg}"
                self._progress.visible = False
                self.ctx.add_log(f"设计稿加载失败: {msg}")
                self.ctx.page.update()
                return
            self._designs = result.get("designs", []) or []
            self._render_sector_bar()
            self._status.value = f"共 {len(self._designs)} 张设计稿，选择分组后点击卡片查看设计细节"
            self._progress.visible = False
            self._render_grid()
            self.ctx.page.update()
            self._load_thumbnails()

        def err(exc):
            self._status.value = "加载失败，请查看日志"
            self._progress.visible = False
            show_error(self.ctx.page, exc, "加载设计稿", self.ctx.palette, self.ctx.add_log)

        run_in_background(self.ctx.page, work, on_done=done, on_error=err)

    # ── key ───────────────────────────────────────────────────────
    def _design_key(self, design: dict) -> str:
        return str(design.get("id") or design.get("index") or design.get("name"))

    # ── grid ──────────────────────────────────────────────────────
    def _visible_designs(self) -> List[dict]:
        if self._sector_filter == "__all__":
            return list(self._designs)
        return [
            design for design in self._designs
            if self._sector_filter in {str(value) for value in design.get("sectors", [])}
        ]

    def _render_sector_bar(self) -> None:
        p = self.ctx.palette
        sector_names = sorted({str(name) for design in self._designs for name in design.get("sectors", []) if str(name).strip()})
        options = [("__all__", f"全部 ({len(self._designs)})")] + [
            (name, f"{name} ({sum(name in design.get('sectors', []) for design in self._designs)})")
            for name in sector_names
        ]
        if self._sector_filter not in {value for value, _label in options}:
            self._sector_filter = "__all__"
        controls: List[ft.Control] = [
            ft.Text("设计分组", size=theme.font_size("xs"), color=p.text_muted)
        ]
        for value, label in options:
            active = value == self._sector_filter
            controls.append(
                ft.Container(
                    content=ft.Text(label, size=theme.font_size("xs"), color=p.text_on_primary if active else p.text_secondary),
                    bgcolor=p.primary if active else p.surface,
                    border=ft.border.all(1, p.primary if active else p.border_light),
                    border_radius=theme.radius("full"),
                    padding=ft.padding.symmetric(horizontal=theme.space("3"), vertical=theme.space("1")),
                    on_click=lambda _event, group=value: self._set_sector_filter(group),
                    ink=True,
                )
            )
        self._sector_bar.controls = controls

    def _set_sector_filter(self, sector: str) -> None:
        self._sector_filter = sector
        self._render_sector_bar()
        self._render_grid()
        self._reapply_thumbnails()
        visible = len(self._visible_designs())
        self._status.value = f"显示 {visible} / {len(self._designs)} 张设计稿，点击图片查看设计细节"
        self._safe_update()
    def _render_grid(self) -> None:
        p = self.ctx.palette
        controls: List[ft.Control] = []
        for design in self._visible_designs():
            key = self._design_key(design)
            dims = f"{design.get('width', '?')}×{design.get('height', '?')}"
            thumb = ft.Container(
                content=ft.Icon(ft.Icons.IMAGE, color=p.text_muted, size=40),
                bgcolor=p.surface_alt if hasattr(p, "surface_alt") else p.surface,
                border_radius=theme.radius("sm"),
                alignment=ft.alignment.center,
                height=150,
                key=f"thumb-{key}",
            )
            stacked_thumb = ft.Stack([thumb], expand=False)
            card = ft.Container(
                key=f"card-{key}",
                content=ft.Column(
                    [
                        stacked_thumb,
                        ft.Text(
                            str(design.get("name") or "Design page"),
                            size=theme.font_size("sm"),
                            color=p.text_primary,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(dims, size=theme.font_size("xs"), color=p.text_muted),
                    ],
                    spacing=6,
                ),
                padding=theme.space("2"),
                bgcolor=p.card,
                border=ft.border.all(1, p.border_light),
                border_radius=theme.radius("md"),
                on_click=lambda _event, item=design: self._show_design_detail(item),
                ink=True,
                animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            )
            controls.append(card)
        self._grid.controls = controls

    def _load_thumbnails(self) -> None:
        applied_cached = False
        for design in self._designs:
            url = design.get("url")
            if url and url in self._thumb_cache and not design.get("_thumb_b64"):
                design["_thumb_b64"] = self._thumb_cache[url]
                applied_cached = True
        if applied_cached:
            self._reapply_thumbnails()
            self._safe_update()

        pending = [d for d in self._designs if d.get("url") and not d.get("_thumb_b64")]
        if not pending:
            self._thumb_total = 0
            self._thumb_done = 0
            self._progress.visible = False
            self._safe_update()
            return

        self._thumb_total = len(pending)
        self._thumb_done = 0
        self._progress.visible = True
        self._progress.value = 0.0
        self._safe_update()

        self._thumb_pool = ThreadPoolExecutor(max_workers=THUMB_CONCURRENCY)

        def fetch(design: dict) -> None:
            url = design.get("url")
            try:
                data = _download_image_bytes(url, self._cookie, max_bytes=THUMB_MAX_BYTES)
            except Exception:
                data = b""
            if data:
                b64 = base64.b64encode(data).decode("ascii")
                with self._thumb_lock:
                    self._thumb_cache[url] = b64
                    design["_thumb_b64"] = b64
            with self._thumb_lock:
                self._thumb_done += 1
                self._progress.value = min(1.0, self._thumb_done / max(self._thumb_total, 1))
                self._status.value = f"加载缩略图 {self._thumb_done}/{self._thumb_total} · 已选 {len(self._selected)}"
                should_schedule = not self._pending_update
                self._pending_update = True
            if should_schedule:
                self._schedule_thumbnail_refresh()

        for design in pending:
            self._thumb_pool.submit(fetch, design)

    def _schedule_thumbnail_refresh(self) -> None:
        def flush() -> None:
            with self._thumb_lock:
                self._pending_update = False
            self._reapply_thumbnails()
            if self._thumb_total > 0 and self._thumb_done >= self._thumb_total:
                self._progress.visible = False
                self._status.value = f"共 {len(self._designs)} 张设计稿，已选 {len(self._selected)} · 缩略图已就绪"
            self._safe_update()

        timer = threading.Timer(0.15, flush)
        timer.daemon = True
        timer.start()

    def _safe_update(self) -> None:
        try:
            self.ctx.page.update()
        except Exception:
            pass

    def _reapply_thumbnails(self) -> None:
        index = {self._design_key(d): d for d in self._designs}
        for card in self._grid.controls:
            if not isinstance(card, ft.Container) or not card.content:
                continue
            column = card.content
            if not isinstance(column, ft.Column) or not column.controls:
                continue
            # The first control in Column is a Stack
            stack = column.controls[0]
            if not isinstance(stack, ft.Stack) or not stack.controls:
                continue
            thumb = stack.controls[0]
            key = (card.key or "").replace("card-", "")
            design = index.get(key)
            if design and design.get("_thumb_b64") and isinstance(thumb, ft.Container):
                thumb.content = ft.Image(src_base64=design["_thumb_b64"], fit=ft.ImageFit.CONTAIN, height=150)

    # ── prompt ────────────────────────────────────────────────────
    def _prompt_for_design(self, design: dict) -> str:
        """Build a copy-ready implementation brief for one design page."""
        groups = ", ".join(str(value) for value in design.get("sectors", []) if value) or "Uncategorized"
        lines = [
            "# Design implementation brief",
            "",
            f"Project: {self._project_name}",
            f"Design page: {design.get('name') or 'Untitled'}",
            f"Canvas: {design.get('width') or '?'} x {design.get('height') or '?'}",
            f"Group: {groups}",
            f"Design image: {design.get('url') or 'Unavailable'}",
            "",
            "## Implementation requirements",
            "1. Inspect the linked design image before writing code; it is the visual source of truth.",
            "2. Reproduce layout, typography, colors, spacing, borders, and component states accurately.",
            "3. Implement responsive behavior deliberately and preserve the information hierarchy on narrow screens.",
            "4. Use semantic, maintainable components and do not invent content that is absent from the design.",
            "5. List any visual ambiguity before making a product decision.",
        ]
        if design.get("update_time"):
            lines.insert(7, f"Updated: {design['update_time']}")
        return "\n".join(lines)

    def _show_design_detail(self, design: dict) -> None:
        """Open a read-only design page with its individual AI prompt."""
        p = self.ctx.palette
        prompt = self._prompt_for_design(design)
        if design.get("_thumb_b64"):
            preview = ft.Image(src_base64=design["_thumb_b64"], fit=ft.ImageFit.CONTAIN, height=360)
        elif design.get("url"):
            preview = ft.Image(src=str(design["url"]), fit=ft.ImageFit.CONTAIN, height=360)
        else:
            preview = ft.Container(content=ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED, size=56, color=p.text_muted), height=220, alignment=ft.alignment.center)
        prompt_field = ft.TextField(value=prompt, read_only=True, multiline=True, min_lines=12, max_lines=12, text_size=theme.font_size("xs"))

        def close_dialog() -> None:
            try:
                self.ctx.page.close(dialog)
            except Exception:
                dialog.open = False
                self._safe_update()

        def copy_prompt(_event) -> None:
            try:
                self.ctx.page.set_clipboard(prompt)
                toast(self.ctx.page, "Design prompt copied", "ok", p)
            except Exception as exc:
                show_error(self.ctx.page, exc, "Copy design prompt", p, self.ctx.add_log)

        dialog = ft.AlertDialog(
            title=ft.Text(str(design.get("name") or "Design page"), color=p.text_primary),
            content=ft.Container(
                width=760,
                content=ft.Column([
                    ft.Container(content=preview, height=380, alignment=ft.alignment.center, bgcolor=p.surface, border_radius=theme.radius("md")),
                    ft.Text("AI implementation prompt", size=theme.font_size("sm"), weight=theme.WEIGHT_SEMIBOLD, color=p.text_primary),
                    prompt_field,
                ], spacing=theme.space("3"), scroll=ft.ScrollMode.AUTO, tight=True),
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda _event: close_dialog()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.ctx.page.open(dialog)

    def _close(self) -> None:
        if self._thumb_pool is not None:
            self._thumb_pool.shutdown(wait=False, cancel_futures=True)
            self._thumb_pool = None
        if self._dialog is not None:
            try:
                self.ctx.page.close(self._dialog)
            finally:
                self._dialog = None
            self._safe_update()

    # ── dialog ────────────────────────────────────────────────────
    def _build_dialog(self) -> ft.AlertDialog:
        p = self.ctx.palette
        return ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Text(f"设计稿浏览 · {self._project_name}", weight=theme.WEIGHT_SEMIBOLD,
                            color=p.text_primary, expand=True),
                    self._status,
                    self._progress,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                wrap=True,
            ),
            content=ft.Container(
                content=ft.Column([
                    self._sector_bar,
                    ft.Divider(height=1, color=p.border_light),
                    self._grid,
                ], spacing=theme.space("2"), expand=True),
                width=860,
                height=540,
            ),
            actions=[
                ft.TextButton("关闭", on_click=lambda _event: self._close()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )


__all__ = ["DesignBrowser"]
