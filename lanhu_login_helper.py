#!/usr/bin/env python3
"""蓝湖 WebView 登录辅助进程。"""

import json
import os
import sys
import time
from pathlib import Path


DEFAULT_LANHU_URL = "https://lanhuapp.com/web/"
LOGIN_TIMEOUT_SECONDS = 300
EDGE_ERROR_KEYWORDS = (
    "ERR_TIMED_OUT",
    "ERR_CONNECTION",
    "无法访问此页面",
    "无法访问该页面",
    "This site can't be reached",
    "took too long to respond",
)
ANONYMOUS_COOKIE_NAMES = {"serverid", "_bl_uid", "supportwebp"}
INVALID_AUTH_VALUES = {"", "undefined", "null", "none", "false", "nan"}
STRICT_AUTH_COOKIE_NAMES = {
    "sid",
    "session",
    "sessionid",
    "uid",
    "userid",
    "user_id",
    "memberid",
    "member_id",
    "user_token",
    "access_token",
    "authorization",
}


LOADING_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>蓝湖登录</title>
  <style>
    :root {
      color-scheme: light;
      font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
      background: #f4f6f8;
      color: #172033;
    }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #f4f6f8;
    }
    .login-shell {
      width: min(520px, calc(100vw - 48px));
      padding: 32px;
      border: 1px solid #d7dee7;
      border-radius: 10px;
      background: #ffffff;
      box-shadow: 0 16px 36px rgba(23, 32, 51, 0.10);
    }
    .login-shell__icon {
      width: 42px;
      height: 42px;
      display: grid;
      place-items: center;
      border-radius: 8px;
      background: #dbeafe;
      color: #1d4ed8;
      font-size: 22px;
      font-weight: 700;
    }
    .login-shell__title {
      margin: 18px 0 8px;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: 0;
    }
    .login-shell__text {
      margin: 0;
      color: #526070;
      font-size: 14px;
      line-height: 1.7;
    }
    .login-shell__bar {
      height: 4px;
      margin-top: 24px;
      overflow: hidden;
      border-radius: 999px;
      background: #eef2f6;
    }
    .login-shell__bar::before {
      content: "";
      display: block;
      width: 38%;
      height: 100%;
      border-radius: inherit;
      background: #1d4ed8;
      animation: loading 1.2s ease-in-out infinite;
    }
    @keyframes loading {
      0% { transform: translateX(-110%); }
      100% { transform: translateX(280%); }
    }
  </style>
</head>
<body>
  <main class="login-shell">
    <div class="login-shell__icon">L</div>
    <h1 class="login-shell__title">正在打开蓝湖登录</h1>
    <p class="login-shell__text">
      如果页面长时间没有出现，请确认当前电脑已安装 Microsoft Edge WebView2 Runtime，
      并检查网络是否可以访问 lanhuapp.com。
    </p>
    <div class="login-shell__bar" aria-hidden="true"></div>
  </main>
</body>
</html>
"""


def format_cookie(raw_cookie: object) -> str:
    """把 pywebview 返回的 Cookie 对象统一转换成 HTTP Cookie 字符串。"""
    if isinstance(raw_cookie, str):
        return raw_cookie.strip()
    if isinstance(raw_cookie, list):
        pairs: list[str] = []
        for item in raw_cookie:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            value = item.get("value")
            if name and value is not None:
                pairs.append(f"{name}={value}")
        return "; ".join(pairs)
    if isinstance(raw_cookie, dict):
        pairs: list[str] = []
        for name, value in raw_cookie.items():
            if value is not None:
                pairs.append(f"{name}={value}")
        return "; ".join(pairs)
    return ""


def normalize_login_url(login_url: str) -> str:
    """规范化登录地址，避免用户输入空值或缺少协议。"""
    value = (login_url or DEFAULT_LANHU_URL).strip()
    if not value:
        return DEFAULT_LANHU_URL
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value


def is_lanhu_url(current_url: str) -> bool:
    """判断地址是否仍在蓝湖域名下。"""
    lowered = (current_url or "").lower()
    return "lanhuapp.com" in lowered or "lanhuapp.cn" in lowered


def parse_cookie_pairs(cookie: str) -> dict[str, str]:
    """把 HTTP Cookie 字符串解析成键值字典。"""
    pairs: dict[str, str] = {}
    for part in (cookie or "").split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        normalized_name = name.strip()
        if normalized_name:
            pairs[normalized_name] = value.strip()
    return pairs


def has_valid_auth_cookie(cookie: str) -> bool:
    """判断 Cookie 中是否包含真实登录令牌，而不是匿名追踪 Cookie。"""
    for name, value in parse_cookie_pairs(cookie).items():
        lowered_name = name.lower()
        lowered_value = value.strip().lower()
        if lowered_name in ANONYMOUS_COOKIE_NAMES:
            continue
        if lowered_value in INVALID_AUTH_VALUES:
            continue
        if lowered_name in STRICT_AUTH_COOKIE_NAMES and len(value.strip()) >= 6:
            return True
    return False


def storage_value_has_identity(value: object) -> bool:
    """检查 storage 值里是否包含可证明登录的用户身份字段。"""
    if value in (None, ""):
        return False
    parsed = value
    if isinstance(value, str):
        stripped_value = value.strip()
        if stripped_value.lower() in INVALID_AUTH_VALUES:
            return False
        try:
            parsed = json.loads(stripped_value)
        except json.JSONDecodeError:
            return len(stripped_value) >= 8
    if isinstance(parsed, dict):
        identity_keys = (
            "id",
            "uid",
            "userId",
            "user_id",
            "memberId",
            "member_id",
            "name",
            "email",
            "mobile",
            "phone",
        )
        return any(parsed.get(key) not in (None, "") for key in identity_keys)
    return False


def has_valid_storage_auth(browser_state: dict[str, object]) -> bool:
    """判断 localStorage 是否包含真实用户信息或登录令牌。"""
    user_payload = browser_state.get("user", {})
    if storage_value_has_identity(user_payload):
        return True
    for storage_name in ("storage", "sessionStorage"):
        storage = browser_state.get(storage_name, {})
        if not isinstance(storage, dict):
            continue
        for key, value in storage.items():
            lowered_key = str(key).lower()
            lowered_value = str(value).strip().lower()
            if lowered_value in INVALID_AUTH_VALUES:
                continue
            is_user_key = lowered_key in {
                "user",
                "userinfo",
                "user_info",
                "loginuser",
                "login_user",
                "currentuser",
                "current_user",
                "accountinfo",
                "member",
            }
            if ("token" in lowered_key or "auth" in lowered_key) and len(str(value).strip()) >= 8:
                return True
            if is_user_key and storage_value_has_identity(value):
                return True
    return False


def collect_browser_state(window: object) -> dict[str, object]:
    """从蓝湖页面读取 Cookie、localStorage 和基础页面状态。"""
    state_script = """
    (function () {
      var result = {
        user: {},
        storage: {},
        sessionStorage: {},
        appState: {},
        documentCookie: "",
        title: document.title || "",
        bodyText: document.body ? (document.body.innerText || "") : ""
      };
      try {
        result.documentCookie = document.cookie || "";
      } catch (error) {}
      try {
        for (var index = 0; index < localStorage.length; index += 1) {
          var key = localStorage.key(index);
          result.storage[key] = localStorage.getItem(key);
        }
      } catch (error) {}
      try {
        for (var sessionIndex = 0; sessionIndex < sessionStorage.length; sessionIndex += 1) {
          var sessionKey = sessionStorage.key(sessionIndex);
          result.sessionStorage[sessionKey] = sessionStorage.getItem(sessionKey);
        }
      } catch (error) {}
      try {
        var stateKeys = [
          "__INITIAL_STATE__",
          "__NUXT__",
          "__NEXT_DATA__",
          "__APOLLO_STATE__",
          "__LANHU_STATE__",
          "initialState"
        ];
        for (var stateIndex = 0; stateIndex < stateKeys.length; stateIndex += 1) {
          var stateKey = stateKeys[stateIndex];
          var stateValue = window[stateKey];
          if (stateValue) {
            result.appState[stateKey] = stateValue;
          }
        }
      } catch (error) {}
      var userKeys = [
        "user",
        "userInfo",
        "USER_INFO",
        "currentUser",
        "current_user",
        "loginUser",
        "login_user",
        "member",
        "account",
        "accountInfo",
        "profile",
        "lanhu_user",
        "data"
      ];
      for (var i = 0; i < userKeys.length; i += 1) {
        var itemKey = userKeys[i];
        var itemValue = result.storage[itemKey] || result.sessionStorage[itemKey];
        if (!itemValue) {
          continue;
        }
        try {
          result.user = JSON.parse(itemValue);
          break;
        } catch (error) {
          result.user = { name: itemValue };
          break;
        }
      }
      if (!result.user || Object.keys(result.user).length === 0) {
        var stores = [result.storage, result.sessionStorage];
        for (var storeIndex = 0; storeIndex < stores.length; storeIndex += 1) {
          var store = stores[storeIndex];
          var keys = Object.keys(store);
          for (var keyIndex = 0; keyIndex < keys.length; keyIndex += 1) {
            var scanKey = keys[keyIndex];
            var lowerKey = String(scanKey).toLowerCase();
            if (lowerKey.indexOf("user") === -1 && lowerKey.indexOf("member") === -1 && lowerKey.indexOf("account") === -1) {
              continue;
            }
            try {
              var parsed = JSON.parse(store[scanKey]);
              if (parsed && typeof parsed === "object") {
                result.user = parsed;
                result.userStorageKey = scanKey;
                break;
              }
            } catch (error) {}
          }
          if (result.user && Object.keys(result.user).length > 0) {
            break;
          }
        }
      }
      return result;
    })();
    """
    browser_state = window.evaluate_js(state_script)
    if isinstance(browser_state, dict):
        return browser_state
    if isinstance(browser_state, str):
        try:
            parsed_state = json.loads(browser_state)
            if isinstance(parsed_state, dict):
                return parsed_state
        except json.JSONDecodeError:
            return {"user": {}, "storage": {}, "documentCookie": browser_state}
    return {"user": {}, "storage": {}, "documentCookie": ""}


def collect_cookie(window: object, browser_state: dict[str, object]) -> str:
    """优先使用 pywebview Cookie API，失败时退回 document.cookie。"""
    try:
        cookie_value = format_cookie(window.get_cookies())
        if cookie_value:
            return cookie_value
    except Exception:
        pass
    return format_cookie(browser_state.get("documentCookie", ""))


def is_lanhu_logged_in(
    current_url: str,
    cookie: str,
    browser_state: dict[str, object],
    elapsed_seconds: int = 0,
) -> bool:
    """判断当前窗口是否已经进入蓝湖登录态。"""
    if elapsed_seconds < 4:
        return False
    if not is_lanhu_url(current_url):
        return False
    has_auth_cookie = has_valid_auth_cookie(cookie)
    has_storage_auth = has_valid_storage_auth(browser_state)
    is_authed_route = "/item/" in current_url or "/team/" in current_url or "/project/" in current_url
    return bool(has_auth_cookie and (has_storage_auth or is_authed_route))


def detect_edge_error(browser_state: dict[str, object]) -> str:
    """从 Edge WebView 错误页里提取可读错误信息。"""
    page_text = " ".join(
        str(browser_state.get(key, ""))
        for key in ("title", "bodyText")
    )
    for keyword in EDGE_ERROR_KEYWORDS:
        if keyword.lower() in page_text.lower():
            return keyword
    return ""


def write_result(result_file: Path, result: dict[str, object]) -> None:
    """把登录结果写入 GUI 约定的 JSON 文件。"""
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def cleanup_old_sessions(storage_root: Path) -> None:
    """清理旧的临时 WebView 会话目录，避免缓存锁导致黑屏。"""
    if not storage_root.exists():
        return
    cutoff = time.time() - 24 * 60 * 60
    for item in storage_root.glob("session-*"):
        try:
            if item.is_dir() and item.stat().st_mtime < cutoff:
                import shutil

                shutil.rmtree(item, ignore_errors=True)
        except OSError:
            continue


def prepare_storage_dir(storage_root: Path) -> Path:
    """为本次登录创建独立的 WebView2 用户目录。"""
    storage_root.mkdir(parents=True, exist_ok=True)
    cleanup_old_sessions(storage_root)
    session_dir = storage_root / f"session-{os.getpid()}-{int(time.time())}"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def build_webview_error(error: Exception) -> str:
    """生成给主界面展示的 WebView 启动错误。"""
    return (
        "蓝湖登录窗口启动失败。\n"
        f"原因: {error}\n\n"
        "请确认已安装 Microsoft Edge WebView2 Runtime，"
        "并关闭残留的 LanhuMCP 登录窗口后重试。"
    )


def main() -> int:
    """打开蓝湖登录窗口并等待用户完成登录。"""
    result_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        os.environ.get("APPDATA", ".")
    ) / "LanhuMCP" / ".login_result.json"
    storage_root = Path(sys.argv[2]) if len(sys.argv) > 2 else result_file.parent / "webview"
    login_url = normalize_login_url(sys.argv[3] if len(sys.argv) > 3 else os.environ.get("LANHU_LOGIN_URL", ""))
    storage_dir = prepare_storage_dir(storage_root)
    smoke_mode = os.environ.get("LANHU_LOGIN_HELPER_SMOKE") == "1"
    result: dict[str, object] = {
        "status": "cancelled",
        "cookies": "",
        "user": {},
        "storage": {},
        "url": "",
        "login_url": login_url,
        "error": "",
        "diagnostics": [],
        "storage_dir": str(storage_dir),
    }

    try:
        import webview
    except Exception as error:
        result["status"] = "error"
        result["error"] = f"pywebview 加载失败: {error}"
        write_result(result_file, result)
        return 1

    def remember(message: str) -> None:
        """记录辅助进程诊断信息，方便主界面展示和日志定位。"""
        diagnostics = result.setdefault("diagnostics", [])
        if isinstance(diagnostics, list):
            diagnostics.append(message)

    def on_loaded(window: object) -> None:
        """轮询登录状态，检测成功后关闭窗口。"""
        nonlocal result
        remember("WebView 线程已启动")
        shown = window.events.shown.wait(15)
        if not shown:
            remember("登录窗口 15 秒内未触发 shown 事件")
        time.sleep(1)

        if smoke_mode:
            result["status"] = "success"
            result["url"] = "about:blank"
            result["diagnostics"] = result.get("diagnostics", [])
            time.sleep(1.5)
            try:
                window.destroy()
            except Exception:
                pass
            return

        try:
            window.load_url(login_url)
            remember(f"已导航到蓝湖登录地址: {login_url}")
        except Exception as error:
            result["status"] = "error"
            result["error"] = build_webview_error(error)
            remember(f"导航蓝湖登录地址失败: {error}")
            try:
                window.destroy()
            except Exception:
                pass
            return

        last_url = ""
        for index in range(LOGIN_TIMEOUT_SECONDS):
            time.sleep(1)
            try:
                current_url = window.get_current_url() or ""
                browser_state = collect_browser_state(window)
                cookie = collect_cookie(window, browser_state)
                last_url = current_url or last_url
                if index in (3, 10, 25) and cookie and not has_valid_auth_cookie(cookie):
                    remember("已读取到蓝湖匿名 Cookie，继续等待用户完成登录")
                if index == 20 and not current_url:
                    result["status"] = "error"
                    result["error"] = build_webview_error(RuntimeError("WebView2 页面地址为空"))
                    remember("WebView2 20 秒内没有可读取页面地址")
                    try:
                        window.destroy()
                    except Exception:
                        pass
                    return
                edge_error = detect_edge_error(browser_state)
                if edge_error and index >= 12:
                    result["status"] = "error"
                    result["url"] = current_url
                    result["error"] = (
                        f"WebView2 无法访问蓝湖登录地址: {login_url}\n"
                        f"页面错误: {edge_error}\n\n"
                        "请检查系统代理、DNS 或网络连通性；也可以在主界面改用浏览器打开登录页后手动保存 Cookie。"
                    )
                    remember(f"WebView2 页面错误: {edge_error}")
                    try:
                        window.destroy()
                    except Exception:
                        pass
                    return
                if index in (10, 25) and not is_lanhu_url(current_url):
                    window.load_url(login_url)
                    remember("检测到页面未进入蓝湖，已重新导航")
                if is_lanhu_logged_in(current_url, cookie, browser_state, index):
                    result = {
                        "status": "success",
                        "cookies": cookie,
                        "user": browser_state.get("user", {}),
                        "storage": browser_state.get("storage", {}),
                        "sessionStorage": browser_state.get("sessionStorage", {}),
                        "appState": browser_state.get("appState", {}),
                        "url": current_url,
                        "login_url": login_url,
                        "error": "",
                        "diagnostics": result.get("diagnostics", []),
                        "storage_dir": str(storage_dir),
                    }
                    window.destroy()
                    return
            except Exception as error:
                result["error"] = str(error)
                remember(f"轮询登录状态失败: {error}")
        result["url"] = last_url

    window = webview.create_window(
        "蓝湖登录",
        html=LOADING_HTML,
        width=1200,
        height=820,
        min_size=(920, 640),
        background_color="#FFFFFF",
    )
    try:
        webview.start(
            on_loaded,
            (window,),
            gui="edgechromium",
            private_mode=False,
            storage_path=str(storage_dir),
        )
    except Exception as error:
        result["status"] = "error"
        result["error"] = build_webview_error(error)
        remember(f"WebView 启动异常: {error}")
        return_code = 1
    else:
        return_code = 0 if result.get("status") == "success" else 1
    finally:
        if result.get("status") == "cancelled" and not result.get("error"):
            result["status"] = "error"
            result["error"] = (
                "蓝湖登录窗口未返回登录结果。"
                "如果窗口没有正常显示，请重试或使用系统浏览器打开登录页。"
            )
        write_result(result_file, result)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
