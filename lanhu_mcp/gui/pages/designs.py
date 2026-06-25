"""Design browser dialog — port of the legacy Tkinter ``open_design_browser``.

Opens a modal dialog that lists a project's design images (fetched from the
Lanhu API), lets the user multi-select them and generates a restoration prompt
that is copied to the clipboard. Thumbnails are downloaded in the background
(with the active account cookie) and rendered as base64 images; failures fall
back to a placeholder icon so the dialog never blocks on a single bad image.
"""

from __future__ import annotations

import base64
from typing import Dict, List, Optional

import flet as ft

from .. import theme
from ..components import run_in_background, toast
from ..state import AppContext
from ...core import accounts as accounts_core
from ...services.lanhu_api import _fetch_designs_api, _download_image_bytes

THUMB_MAX_BYTES = 2 * 1024 * 1024  # skip oversized thumbnails


class DesignBrowser:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._dialog: Optional[ft.AlertDialog] = None
        self._grid = ft.GridView(expand=True, runs_count=3, max_extent=260,
                                  child_aspect_ratio=0.8, spacing=12, run_spacing=12)
        self._status = ft.Text("正在加载设计稿…", color=ctx.palette.text_muted,
                               size=theme.font_size("sm"))
        self._designs: List[dict] = []
        self._selected: Dict[str, dict] = {}
        self._project_name = ""
        self._cookie = ""

    # -- public ---------------------------------------------------------
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
        self._grid.controls = []
        self._status.value = "正在加载设计稿…"

        self._dialog = self._build_dialog()
        self.ctx.page.open(self._dialog)
        self.ctx.page.update()

        def work():
            return _fetch_designs_api(self._cookie, project_id, team_id or "")

        def done(result):
            if not isinstance(result, dict) or result.get("status") != "success":
                msg = (result or {}).get("message", "未知错误") if isinstance(result, dict) else "请求失败"
                self._status.value = f"加载失败：{msg}"
                self.ctx.page.update()
                return
            self._designs = result.get("designs", []) or []
            self._status.value = f"共 {len(self._designs)} 张设计稿，点击卡片可多选"
            self._render_grid()
            self.ctx.page.update()
            self._load_thumbnails()

        run_in_background(self.ctx.page, work, on_done=done)

    # -- rendering ------------------------------------------------------
    def _design_key(self, design: dict) -> str:
        return str(design.get("id") or design.get("index") or design.get("name"))

    def _render_grid(self) -> None:
        p = self.ctx.palette
        controls: List[ft.Control] = []
        for design in self._designs:
            key = self._design_key(design)
            selected = key in self._selected
            dims = f"{design.get('width', '?')}×{design.get('height', '?')}"
            thumb = ft.Container(
                content=ft.Icon(ft.Icons.IMAGE, color=p.text_muted, size=40),
                bgcolor=p.surface_alt if hasattr(p, "surface_alt") else p.surface,
                border_radius=theme.radius("sm"),
                alignment=ft.alignment.center,
                height=150,
                key=f"thumb-{key}",
            )
            card = ft.Container(
                key=f"card-{key}",
                content=ft.Column(
                    [
                        thumb,
                        ft.Text(design.get("name", "未命名"), size=theme.font_size("sm"),
                                color=p.text_primary, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(dims, size=theme.font_size("xs"), color=p.text_muted),
                    ],
                    spacing=6,
                ),
                padding=theme.space("2"),
                bgcolor=p.primary_light if selected else p.surface,
                border=ft.border.all(2 if selected else 1,
                                     p.primary if selected else p.border_light),
                border_radius=theme.radius("md"),
                on_click=lambda e, d=design: self._toggle(d),
                ink=True,
            )
            controls.append(card)
        self._grid.controls = controls

    def _toggle(self, design: dict) -> None:
        key = self._design_key(design)
        if key in self._selected:
            del self._selected[key]
        else:
            self._selected[key] = design
        self._render_grid()
        # Re-apply thumbnails that were already downloaded.
        self._reapply_thumbnails()
        self._status.value = (
            f"共 {len(self._designs)} 张设计稿，已选 {len(self._selected)} 张"
        )
        self.ctx.page.update()

    def _load_thumbnails(self) -> None:
        """Download thumbnails in the background and cache them on the design dict."""
        for design in self._designs:
            url = design.get("url")
            if not url:
                continue

            def work(u=url):
                data = _download_image_bytes(u, self._cookie)
                if not data or len(data) > THUMB_MAX_BYTES:
                    return None
                return base64.b64encode(data).decode("ascii")

            def done(b64, d=design):
                if b64:
                    d["_thumb_b64"] = b64
                    self._reapply_thumbnails()
                    try:
                        self.ctx.page.update()
                    except Exception:
                        pass

            run_in_background(self.ctx.page, work, on_done=done)

    def _reapply_thumbnails(self) -> None:
        index = {self._design_key(d): d for d in self._designs}
        for card in self._grid.controls:
            if not isinstance(card, ft.Container) or not card.content:
                continue
            column = card.content
            if not isinstance(column, ft.Column) or not column.controls:
                continue
            thumb = column.controls[0]
            key = (card.key or "").replace("card-", "")
            design = index.get(key)
            if design and design.get("_thumb_b64") and isinstance(thumb, ft.Container):
                thumb.content = ft.Image(src_base64=design["_thumb_b64"], fit=ft.ImageFit.CONTAIN,
                                         height=150)

    # -- actions --------------------------------------------------------
    def _generate_prompt(self) -> None:
        if not self._selected:
            toast(self.ctx.page, "请先选择设计稿", "warn", self.ctx.palette)
            return
        designs = list(self._selected.values())
        lines: List[str] = [
            "# 设计稿还原任务",
            "",
            f"项目: {self._project_name}",
            f"选中设计稿数量: {len(designs)}",
            "",
            "## 选中的设计稿",
            "",
        ]
        for i, design in enumerate(designs, 1):
            lines.append(f"### 设计稿 {i}: {design.get('name', '未命名')}")
            lines.append(f"- 尺寸: {design.get('width', '?')}x{design.get('height', '?')}")
            if design.get("sectors"):
                lines.append(f"- 分组: {', '.join(str(s) for s in design['sectors'])}")
            if design.get("url"):
                lines.append(f"- 图片URL: {design['url']}")
            if design.get("update_time"):
                lines.append(f"- 更新时间: {design['update_time']}")
            lines.append("")
        lines += [
            "## 任务要求",
            "",
            "1. 请根据以上设计稿，生成对应的前端页面代码",
            "2. 使用 HTML + CSS 实现，保持与设计稿一致的视觉效果",
            "3. 注意响应式布局和跨浏览器兼容性",
            "4. 图片资源请使用设计稿中的 URL",
            "5. 保持设计稿中的字体、颜色、间距等细节",
            "",
            "## 设计稿图片",
            "",
        ]
        for i, design in enumerate(designs, 1):
            if design.get("url"):
                lines.append(f"设计稿 {i}: {design.get('name', '')}")
                lines.append(f"![{design.get('name', '')}]({design['url']})")
        prompt = "\n".join(lines)
        try:
            self.ctx.page.set_clipboard(prompt)
            toast(self.ctx.page, f"已复制 {len(designs)} 张设计稿提示词到剪贴板", "ok", self.ctx.palette)
        except Exception:
            toast(self.ctx.page, "复制失败", "error", self.ctx.palette)

    def _close(self) -> None:
        if self._dialog is not None:
            self.ctx.page.close(self._dialog)
            self.ctx.page.update()

    def _build_dialog(self) -> ft.AlertDialog:
        p = self.ctx.palette
        return ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Text(f"设计稿浏览 · {self._project_name}", weight=theme.WEIGHT_SEMIBOLD,
                            color=p.text_primary, expand=True),
                    self._status,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            content=ft.Container(content=self._grid, width=860, height=520),
            actions=[
                ft.TextButton("关闭", on_click=lambda e: self._close()),
                ft.FilledButton("生成提示词", icon=ft.Icons.AUTO_AWESOME,
                                on_click=lambda e: self._generate_prompt()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )


__all__ = ["DesignBrowser"]
