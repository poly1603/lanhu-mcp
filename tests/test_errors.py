"""Unit tests for friendly error descriptions."""
from __future__ import annotations

import json
import unittest

from lanhu_mcp.core.errors import describe_error, describe_status


class _Response:
    status_code = 401


class _StatusError(Exception):
    def __init__(self) -> None:
        super().__init__("Unauthorized")
        self.response = _Response()


class FriendlyErrorTests(unittest.TestCase):
    def test_describe_status_auth(self) -> None:
        err = describe_status(401)
        self.assertIn("登录已失效", err.message)
        self.assertIn("重新登录", err.hint)

    def test_describe_status_generic_5xx(self) -> None:
        err = describe_status(599)
        self.assertIn("服务器错误", err.message)
        self.assertIn("稍后重试", err.hint)

    def test_describe_http_status_exception(self) -> None:
        err = describe_error(_StatusError(), "读取项目")
        self.assertIn("读取项目失败", err.message)
        self.assertIn("登录已失效", err.message)

    def test_describe_timeout_by_name(self) -> None:
        class ConnectTimeout(Exception):
            pass

        err = describe_error(ConnectTimeout("timed out"))
        self.assertEqual(err.message, "请求超时")
        self.assertIn("网络", err.hint)

    def test_describe_json_decode(self) -> None:
        err = describe_error(json.JSONDecodeError("bad", "{", 0))
        self.assertIn("无法解析", err.message)
        self.assertIn("接口格式", err.hint)

    def test_fallback_is_truncated(self) -> None:
        err = describe_error(RuntimeError("x" * 200))
        self.assertLessEqual(len(err.message), 120)
        self.assertIn("查看日志", err.hint)


if __name__ == "__main__":
    unittest.main()
