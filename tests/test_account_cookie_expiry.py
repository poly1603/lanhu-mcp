"""单元测试：账号 Cookie 过期检测逻辑（无第三方依赖）。"""

import base64
import json
import time
import unittest

from lanhu_mcp.core import accounts as accounts_core


def _make_jwt(exp: int) -> str:
    """构造一个仅含 ``exp`` 的最小 JWT（签名占位，无需校验）。"""
    def b64(obj: dict) -> str:
        raw = json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = b64({"alg": "none", "typ": "JWT"})
    payload = b64({"exp": exp})
    return f"{header}.{payload}.sig"


class CookieExpiryTests(unittest.TestCase):
    def test_unknown_when_no_jwt(self):
        info = accounts_core.account_cookie_expiry({"cookie": "SERVERID=abc; _bl_uid=1"})
        self.assertEqual(info["status"], "unknown")
        self.assertIsNone(info["expires_at"])

    def test_valid_far_future(self):
        exp = int(time.time()) + 30 * 86400
        info = accounts_core.account_cookie_expiry({"cookie": f"user_token={_make_jwt(exp)}"})
        self.assertEqual(info["status"], "valid")
        self.assertEqual(info["expires_at"], exp)

    def test_expiring_within_three_days(self):
        exp = int(time.time()) + 2 * 86400
        info = accounts_core.account_cookie_expiry({"cookie": f"auth_token={_make_jwt(exp)}"})
        self.assertEqual(info["status"], "expiring")

    def test_expired_past(self):
        exp = int(time.time()) - 3600
        info = accounts_core.account_cookie_expiry({"cookie": f"jwt={_make_jwt(exp)}"})
        self.assertEqual(info["status"], "expired")

    def test_non_token_cookie_ignored(self):
        exp = int(time.time()) + 86400
        # 字段名不含 token/auth/jwt，应被忽略 -> unknown
        info = accounts_core.account_cookie_expiry({"cookie": f"sessiondata={_make_jwt(exp)}"})
        self.assertEqual(info["status"], "unknown")

    def test_status_line_strings(self):
        exp = int(time.time()) + 30 * 86400
        line = accounts_core.account_cookie_status_line({"cookie": f"user_token={_make_jwt(exp)}"})
        self.assertIn("登录有效", line)
        expired = accounts_core.account_cookie_status_line({"cookie": f"user_token={_make_jwt(int(time.time()) - 10)}"})
        self.assertIn("过期", expired)


if __name__ == "__main__":
    unittest.main()
