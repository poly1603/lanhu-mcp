"""Human-friendly error explanations with actionable suggestions.

Pure / dependency-free so it can be unit-tested without Flet, httpx or any
network stack. The GUI layer (:mod:`lanhu_mcp.gui.components.widgets`) wraps
:func:`describe_error` to render toasts and write logs.

The goal is to turn raw exceptions (``httpx.ConnectError``, ``TimeoutException``,
``JSONDecodeError`` …) and HTTP status codes into a short Chinese message plus a
concrete next step the user can take.
"""
from __future__ import annotations

from typing import NamedTuple, Optional

__all__ = ["FriendlyError", "describe_error", "describe_status"]


class FriendlyError(NamedTuple):
    """A user-facing error: a short message and an actionable hint."""

    message: str
    hint: str

    def as_line(self) -> str:
        return f"{self.message} {self.hint}".strip()


# HTTP status -> (message, hint). 401/403 dominate the Lanhu cookie flow.
_STATUS_MAP: dict[int, FriendlyError] = {
    400: FriendlyError("请求无效 (400)", "请检查项目链接或参数是否正确。"),
    401: FriendlyError("登录已失效 (401)", "请在账号页重新登录蓝湖。"),
    403: FriendlyError("没有访问权限 (403)", "请确认当前账号有该项目/团队的权限，或重新登录。"),
    404: FriendlyError("资源不存在 (404)", "请检查项目 ID / 团队 ID 是否正确。"),
    408: FriendlyError("请求超时 (408)", "请检查网络后重试。"),
    429: FriendlyError("请求过于频繁 (429)", "请稍候片刻再重试。"),
    500: FriendlyError("蓝湖服务器错误 (500)", "稍后重试；若持续出现请联系蓝湖。"),
    502: FriendlyError("网关错误 (502)", "蓝湖服务暂时不可用，请稍后重试。"),
    503: FriendlyError("服务不可用 (503)", "蓝湖服务暂时不可用，请稍后重试。"),
    504: FriendlyError("网关超时 (504)", "请检查网络后重试。"),
}


def describe_status(status: int) -> FriendlyError:
    """Map an HTTP status code to a friendly error."""
    if status in _STATUS_MAP:
        return _STATUS_MAP[status]
    if 500 <= status < 600:
        return FriendlyError(f"服务器错误 ({status})", "请稍后重试。")
    if 400 <= status < 500:
        return FriendlyError(f"请求被拒绝 ({status})", "请检查登录状态与请求参数。")
    return FriendlyError(f"未知响应 ({status})", "请重试或查看日志了解详情。")


def _exc_name(exc: BaseException) -> str:
    """Fully-qualified class name, e.g. ``httpx.ConnectTimeout``."""
    cls = type(exc)
    module = getattr(cls, "__module__", "") or ""
    name = getattr(cls, "__name__", "") or ""
    return f"{module}.{name}" if module and module != "builtins" else name


def describe_error(exc: BaseException, context: str = "") -> FriendlyError:
    """Translate an exception into a friendly message + actionable hint.

    Matching is duck-typed on class name so we never need to import ``httpx``
    here (keeping this module import-light and testable in isolation).
    ``context`` is an optional short prefix, e.g. ``"读取项目"``.
    """
    name = _exc_name(exc).lower()
    raw = str(exc).strip()

    # An httpx.HTTPStatusError usually carries a `.response.status_code`.
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        base = describe_status(status)
    elif "timeout" in name or "timedout" in name or "timed out" in raw.lower():
        base = FriendlyError("请求超时", "请检查网络连接后重试。")
    elif "connect" in name or "connection" in name:
        base = FriendlyError("无法连接服务器", "请检查网络或代理设置后重试。")
    elif "ssl" in name or "certificate" in name:
        base = FriendlyError("安全连接失败", "请检查系统时间与网络证书设置。")
    elif "jsondecode" in name or "json" in name:
        base = FriendlyError("无法解析返回数据", "接口格式可能已变化，请查看日志或重新登录。")
    elif "permission" in name:
        base = FriendlyError("文件权限不足", "请确认目标目录可写后重试。")
    elif "filenotfound" in name:
        base = FriendlyError("找不到文件", "请确认路径是否存在。")
    elif "proxy" in name or "proxy" in raw.lower():
        base = FriendlyError("代理连接失败", "请检查系统代理设置后重试。")
    else:
        msg = raw or "发生未知错误"
        if len(msg) > 120:
            msg = msg[:117] + "…"
        base = FriendlyError(msg, "请重试，或查看日志了解详情。")

    if context:
        return FriendlyError(f"{context}失败：{base.message}", base.hint)
    return base
