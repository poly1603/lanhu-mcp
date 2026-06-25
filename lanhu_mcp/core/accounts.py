"""多账号管理与用户资料解析（无 Tkinter / 无网络依赖）。

从 ``lanhu_mcp_gui.py`` 抽取的纯逻辑：Cookie/JWT 解析、用户资料候选收集与
合并、多账号读写/迁移/激活、账号展示行拼接、登录地址读写。仅依赖标准库，可
在无第三方依赖的环境中导入与测试，供 Tkinter / Flet GUI 以及 CLI 复用。
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from typing import Optional
from urllib.parse import quote, unquote

from .paths import (
    ACCOUNTS_FILE,
    COOKIE_FILE,
    DATA_DIR,
    DEFAULT_LANHU_LOGIN_URL,
    ENV_FILE,
    now_text,
)

__all__ = [
    "USER_CONTAINER_KEYS",
    "cookie_fingerprint",
    "normalize_cookie_value",
    "parse_cookie_pairs",
    "decode_jwt_payload",
    "parse_cookie_json_value",
    "user_info_from_cookie",
    "mask_cookie_value",
    "get_saved_login_url",
    "save_login_url",
    "parse_json_object",
    "collect_user_candidates",
    "user_candidate_score",
    "merge_user_candidates",
    "text_from_detail",
    "first_detail_value",
    "merge_identity_info",
    "parse_user_payload",
    "read_accounts_data",
    "write_accounts_data",
    "migrate_legacy_cookie",
    "get_accounts",
    "get_active_account",
    "set_active_account",
    "upsert_account",
    "remove_account",
    "load_cookie",
    "save_cookie",
    "active_user_query_suffix",
    "current_mcp_url",
    "account_primary_contact",
    "account_detail_line",
    "account_profile_line",
    "account_cookie_line",
    "account_cookie_expiry",
    "account_cookie_status_line",
]


def cookie_fingerprint(cookie: str) -> str:
    """根据Cookie生成稳定账号ID，避免保存明文ID依赖。"""
    normalized = (cookie or "").strip()
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def normalize_cookie_value(cookie: object) -> str:
    """把 pywebview 或 document.cookie 返回值统一转换为 Cookie 字符串。"""
    if isinstance(cookie, str):
        return cookie.strip()
    if isinstance(cookie, list):
        parts = []
        for item in cookie:
            if isinstance(item, dict) and item.get("name") and item.get("value") is not None:
                parts.append(f"{item.get('name')}={item.get('value')}")
        return "; ".join(parts)
    if isinstance(cookie, dict):
        parts = []
        for name, value in cookie.items():
            if value is not None:
                parts.append(f"{name}={value}")
        return "; ".join(parts)
    return ""


def parse_cookie_pairs(cookie: str) -> dict[str, str]:
    """把 Cookie 字符串解析成键值映射，便于提取非敏感资料。"""
    pairs: dict[str, str] = {}
    for part in (cookie or "").split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        normalized_name = name.strip()
        if normalized_name:
            pairs[normalized_name] = value.strip()
    return pairs


def decode_jwt_payload(token: str) -> dict:
    """解析 JWT payload；只用于展示资料，不做安全鉴权。"""
    parts = (token or "").split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1].strip()
    if not payload:
        return {}
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(f"{payload}{padding}".encode("utf-8"))
        parsed = json.loads(raw.decode("utf-8", errors="replace"))
    except (ValueError, json.JSONDecodeError, OSError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_cookie_json_value(value: str) -> object:
    """解析 Cookie 中可能 URL 编码或 Base64 编码的 JSON 资料。"""
    candidates = [value, unquote(value or "")]
    stripped = (value or "").strip()
    if stripped and len(stripped) % 4 in (0, 2, 3):
        padding = "=" * (-len(stripped) % 4)
        try:
            decoded = base64.urlsafe_b64decode(f"{stripped}{padding}".encode("utf-8"))
            candidates.append(decoded.decode("utf-8", errors="replace"))
        except (ValueError, OSError):
            pass
    for candidate in candidates:
        parsed = parse_json_object(candidate)
        if isinstance(parsed, (dict, list)):
            return parsed
    return value


def user_info_from_cookie(cookie: str) -> dict:
    """从 Cookie 的 JWT 或用户资料字段里提取可展示账号信息。"""
    candidates: list[dict] = []
    for name, value in parse_cookie_pairs(cookie).items():
        lowered_name = name.lower()
        if any(word in lowered_name for word in ("token", "auth", "jwt")):
            payload = decode_jwt_payload(value)
            if payload:
                candidates.append(payload)
        if any(word in lowered_name for word in ("user", "member", "account", "profile")):
            parsed_value = parse_cookie_json_value(value)
            collect_user_candidates(parsed_value, candidates)
    if not candidates:
        return {}
    user_info = parse_user_payload({"cookie": candidates})
    if user_info.get("name") == "蓝湖用户" and not any(
        user_info.get(key) for key in ("email", "mobile", "username", "avatar", "id")
    ):
        return {}
    if user_info:
        user_info["source_url"] = "Cookie/JWT"
    return user_info


def mask_cookie_value(cookie: str) -> str:
    """生成仅用于界面展示的 Cookie 摘要，避免把密钥长时间明文铺在屏幕上。"""
    normalized = (cookie or "").strip()
    if not normalized:
        return ""
    if len(normalized) <= 32:
        return normalized
    return f"{normalized[:16]}...{normalized[-12:]}"


def get_saved_login_url() -> str:
    """读取用户保存的蓝湖登录地址，默认使用官网 Web 入口。"""
    if not ENV_FILE.exists():
        return DEFAULT_LANHU_LOGIN_URL
    try:
        for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
            if line.startswith('LANHU_LOGIN_URL='):
                value = line.split('=', 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    except OSError:
        return DEFAULT_LANHU_LOGIN_URL
    return DEFAULT_LANHU_LOGIN_URL


def save_login_url(login_url: str) -> None:
    """把登录地址保存到环境文件，方便用户处理网络代理或企业私有入口。"""
    normalized = (login_url or DEFAULT_LANHU_LOGIN_URL).strip()
    if not normalized:
        normalized = DEFAULT_LANHU_LOGIN_URL
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env_content = ENV_FILE.read_text(encoding='utf-8') if ENV_FILE.exists() else ''
    if 'LANHU_LOGIN_URL=' in env_content:
        lines = env_content.split('\n')
        for index, line in enumerate(lines):
            if line.startswith('LANHU_LOGIN_URL='):
                lines[index] = f'LANHU_LOGIN_URL={normalized}'
        env_content = '\n'.join(lines)
    else:
        if env_content and not env_content.endswith('\n'):
            env_content += '\n'
        env_content += f'LANHU_LOGIN_URL={normalized}\n'
    ENV_FILE.write_text(env_content, encoding='utf-8')


USER_CONTAINER_KEYS = (
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
    "data",
    "result",
    "payload",
    "state",
    "props",
    "initialState",
    "initial_state",
    "currentTeam",
    "current_team",
    "workspace",
    "organization",
)


def parse_json_object(value: object) -> object:
    """把可能是 JSON 字符串的字段解析成对象。"""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "{[":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def collect_user_candidates(value: object, candidates: list[dict], depth: int = 0) -> None:
    """递归收集登录结果里可能代表用户资料的字典。"""
    if depth > 8:
        return
    parsed = parse_json_object(value)
    if isinstance(parsed, dict):
        candidates.append(parsed)
        for key in USER_CONTAINER_KEYS:
            if key in parsed:
                collect_user_candidates(parsed.get(key), candidates, depth + 1)
        for storage_key in ("storage", "sessionStorage", "localStorage"):
            storage_value = parsed.get(storage_key)
            if isinstance(storage_value, dict):
                for item_value in storage_value.values():
                    collect_user_candidates(item_value, candidates, depth + 1)
        for item_value in parsed.values():
            if isinstance(item_value, (dict, list)):
                collect_user_candidates(item_value, candidates, depth + 1)
        return
    if isinstance(parsed, list):
        for item_value in parsed[:20]:
            collect_user_candidates(item_value, candidates, depth + 1)


def user_candidate_score(candidate: dict) -> int:
    """按字段特征给候选用户资料打分，优先选择真正的用户对象。"""
    score = 0
    for key, value in candidate.items():
        if value in (None, ""):
            continue
        lowered_key = str(key).lower()
        if lowered_key in {
            "id",
            "uid",
            "userid",
            "user_id",
            "memberid",
            "member_id",
            "accountid",
            "account_id",
            "uuid",
        }:
            score += 4
        if lowered_key in {
            "name",
            "nickname",
            "nick",
            "realname",
            "real_name",
            "displayname",
            "display_name",
            "username",
            "user_name",
            "preferred_username",
            "loginname",
            "login_name",
        }:
            score += 3
        if lowered_key in {
            "email",
            "mail",
            "mobile",
            "phone",
            "telephone",
            "avatar",
            "avatarurl",
            "avatar_url",
            "picture",
            "image",
            "headimg",
            "headimgurl",
            "portrait",
        }:
            score += 2
        if lowered_key in {
            "company",
            "companyname",
            "company_name",
            "team",
            "teamname",
            "team_name",
            "rolename",
            "role_name",
            "role",
            "position",
            "department",
            "departmentname",
            "deptname",
        }:
            score += 1
    return score


def merge_user_candidates(candidates: list[dict]) -> dict:
    """把多个候选用户对象合并为一个稳定的资料字典。"""
    merged: dict = {}
    scored_candidates = [
        (user_candidate_score(item), item)
        for item in candidates
    ]
    positive_candidates = [item for score, item in scored_candidates if score > 0]
    sorted_candidates = sorted(positive_candidates, key=user_candidate_score, reverse=True)
    for item in sorted_candidates:
        for key, value in item.items():
            if value in (None, "") or key in merged:
                continue
            merged[key] = value
    return merged


def text_from_detail(value: object) -> str:
    """把嵌套对象里的名称字段转换为适合界面展示的文本。"""
    parsed = parse_json_object(value)
    if parsed in (None, ""):
        return ""
    if isinstance(parsed, dict):
        for key in (
            "name",
            "title",
            "label",
            "nickname",
            "nickName",
            "realName",
            "displayName",
            "userName",
            "teamName",
            "companyName",
            "roleName",
            "departmentName",
            "value",
        ):
            nested_value = parsed.get(key)
            if nested_value not in (None, ""):
                return str(nested_value)
        return ""
    if isinstance(parsed, list):
        parts = [text_from_detail(item) for item in parsed[:3]]
        return "、".join(part for part in parts if part)
    return str(parsed)


def first_detail_value(source: dict, keys: tuple[str, ...]) -> str:
    """按别名顺序读取第一个非空字段。"""
    for key in keys:
        if key in source:
            text = text_from_detail(source.get(key))
            if text:
                return text
    lowered_map = {str(key).lower(): value for key, value in source.items()}
    for key in keys:
        value = lowered_map.get(key.lower())
        text = text_from_detail(value)
        if text:
            return text
    return ""


def merge_identity_info(primary: dict, secondary: dict) -> dict:
    """合并两份账号资料，优先保留 primary 里的非空字段。"""
    merged = dict(secondary or {})
    for key, value in (primary or {}).items():
        if value not in (None, ""):
            merged[key] = value
    return merged


def parse_user_payload(user_payload: object) -> dict:
    """从蓝湖 localStorage 结果中提取尽量稳定的用户信息。"""
    payload = parse_json_object(user_payload)
    candidates: list[dict] = []
    collect_user_candidates(payload, candidates)
    positive_candidates = [
        item for item in candidates
        if user_candidate_score(item) > 0
    ]
    sorted_candidates = sorted(positive_candidates, key=user_candidate_score, reverse=True)
    primary = sorted_candidates[0] if sorted_candidates else {}
    merged = merge_user_candidates(candidates)

    def read_identity(keys: tuple[str, ...]) -> str:
        """优先从最高分用户对象读取字段，再回退到合并资料。"""
        return first_detail_value(primary, keys) or first_detail_value(merged, keys)

    name = (
        read_identity((
            "name",
            "nickname",
            "nickName",
            "nick",
            "realName",
            "real_name",
            "displayName",
            "display_name",
            "fullName",
            "full_name",
            "username",
            "userName",
            "preferred_username",
            "loginName",
            "login_name",
        ))
        or read_identity(("mobile", "phone", "email", "mail"))
        or "蓝湖用户"
    )
    email = read_identity(("email", "mail", "emailAddress", "email_address"))
    mobile = read_identity(("mobile", "phone", "tel", "telephone", "cellphone"))
    username = read_identity(("username", "userName", "preferred_username", "account", "loginName", "login_name"))
    nickname = read_identity(("nickname", "nickName", "nick"))
    user_id = read_identity((
        "id",
        "userId",
        "uid",
        "user_id",
        "memberId",
        "member_id",
        "accountId",
        "account_id",
        "uuid",
        "sub",
        "subject",
    ))
    avatar = read_identity((
        "avatar",
        "avatarUrl",
        "avatar_url",
        "headImg",
        "head_img",
        "headimgurl",
        "portrait",
        "photo",
        "photoUrl",
        "picture",
        "image",
    ))
    company = read_identity((
        "company",
        "companyName",
        "company_name",
        "enterprise",
        "organization",
        "orgName",
        "corpName",
    ))
    team = read_identity((
        "team",
        "teamName",
        "team_name",
        "space",
        "workspace",
        "projectTeam",
        "department",
        "departmentName",
        "deptName",
    ))
    role = read_identity(("role", "roleName", "role_name", "identity", "permission", "position", "jobTitle"))
    source_url = ""
    if isinstance(payload, dict):
        source_url = str(payload.get("url") or payload.get("login_url") or "")

    return {
        "id": str(user_id) if user_id else "",
        "name": str(name),
        "email": str(email) if email else "",
        "mobile": str(mobile) if mobile else "",
        "username": str(username) if username else "",
        "nickname": str(nickname) if nickname else "",
        "avatar": str(avatar) if avatar else "",
        "company": str(company) if company else "",
        "team": str(team) if team else "",
        "role": str(role) if role else "",
        "source_url": source_url,
        "raw": payload,
    }


def read_accounts_data() -> dict:
    """读取多用户账号文件，并兼容文件损坏时的空状态。"""
    if not ACCOUNTS_FILE.exists():
        return {"active_id": "", "accounts": []}
    try:
        data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"active_id": "", "accounts": []}
    accounts = data.get("accounts", [])
    if not isinstance(accounts, list):
        accounts = []
    return {
        "active_id": str(data.get("active_id", "")),
        "accounts": [item for item in accounts if isinstance(item, dict)],
    }


def write_accounts_data(data: dict) -> None:
    """保存多用户账号文件。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate_legacy_cookie() -> dict:
    """把旧版 cookie.txt 迁移成默认账号，确保老用户升级后无需重登。"""
    data = read_accounts_data()
    if data["accounts"] or not COOKIE_FILE.exists():
        return data
    legacy_cookie = COOKIE_FILE.read_text(encoding="utf-8").strip()
    if not legacy_cookie:
        return data
    account_id = cookie_fingerprint(legacy_cookie)
    account = {
        "id": account_id,
        "name": "已登录账号",
        "email": "",
        "mobile": "",
        "company": "",
        "team": "",
        "role": "Developer",
        "cookie": legacy_cookie,
        "cookie_fingerprint": account_id,
        "created_at": now_text(),
        "updated_at": now_text(),
    }
    data = {"active_id": account_id, "accounts": [account]}
    write_accounts_data(data)
    return data


def get_accounts() -> list:
    """返回当前所有蓝湖登录账号。"""
    return migrate_legacy_cookie().get("accounts", [])


def get_active_account() -> Optional[dict]:
    """返回当前选中的蓝湖账号。"""
    data = migrate_legacy_cookie()
    active_id = data.get("active_id", "")
    accounts = data.get("accounts", [])
    for account in accounts:
        if account.get("id") == active_id:
            return account
    return accounts[0] if accounts else None


def set_active_account(account_id: str) -> bool:
    """切换当前蓝湖账号，并同步服务环境文件。"""
    data = migrate_legacy_cookie()
    if not any(account.get("id") == account_id for account in data["accounts"]):
        return False
    data["active_id"] = account_id
    write_accounts_data(data)
    active = get_active_account()
    if active:
        save_cookie(active.get("cookie", ""))
    return True


def upsert_account(cookie: object, user_info: Optional[dict] = None) -> Optional[dict]:
    """新增或更新蓝湖账号，并自动设为当前账号。"""
    cookie = normalize_cookie_value(cookie)
    if not cookie:
        return None
    cookie_user_info = user_info_from_cookie(cookie)
    provided_user_info = dict(user_info or {})
    if provided_user_info.get("name") == "蓝湖用户" and cookie_user_info.get("name"):
        provided_user_info.pop("name", None)
    user_info = merge_identity_info(provided_user_info, cookie_user_info)
    fallback_id = cookie_fingerprint(cookie)
    account_id = str(user_info.get("id") or fallback_id)
    data = migrate_legacy_cookie()
    accounts = data["accounts"]
    existing = next(
        (
            item for item in accounts
            if item.get("id") == account_id or item.get("cookie_fingerprint") == fallback_id
        ),
        None,
    )
    account = existing or {"id": account_id, "created_at": now_text()}
    account["id"] = account_id
    account.update({
        "name": user_info.get("name") or account.get("name") or "蓝湖用户",
        "email": user_info.get("email") or account.get("email") or "",
        "mobile": user_info.get("mobile") or account.get("mobile") or "",
        "username": user_info.get("username") or account.get("username") or "",
        "nickname": user_info.get("nickname") or account.get("nickname") or "",
        "avatar": user_info.get("avatar") or account.get("avatar") or "",
        "company": user_info.get("company") or account.get("company") or "",
        "team": user_info.get("team") or account.get("team") or "",
        "role": user_info.get("role") or account.get("role") or "Developer",
        "source_url": user_info.get("source_url") or account.get("source_url") or "",
        "raw": user_info.get("raw") or account.get("raw") or {},
        "cookie": cookie,
        "cookie_fingerprint": fallback_id,
        "updated_at": now_text(),
    })
    if existing is None:
        accounts.append(account)
    data["active_id"] = account_id
    write_accounts_data(data)
    save_cookie(cookie)
    return account


def remove_account(account_id: str) -> Optional[dict]:
    """退出指定蓝湖账号。"""
    data = migrate_legacy_cookie()
    accounts = [account for account in data["accounts"] if account.get("id") != account_id]
    data["accounts"] = accounts
    if data.get("active_id") == account_id:
        data["active_id"] = accounts[0].get("id", "") if accounts else ""
    write_accounts_data(data)
    active = get_active_account()
    if active:
        save_cookie(active.get("cookie", ""))
    else:
        save_cookie("")
    return active


def load_cookie() -> str:
    """加载完整Cookie（不截断）"""
    active = get_active_account()
    if active and active.get("cookie"):
        return active.get("cookie", "").strip()
    if COOKIE_FILE.exists():
        return COOKIE_FILE.read_text(encoding='utf-8').strip()
    if ENV_FILE.exists():
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('LANHU_COOKIE='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


def save_cookie(cookie: str) -> None:
    """保存完整Cookie"""
    cookie = (cookie or "").strip()
    if cookie:
        COOKIE_FILE.write_text(cookie, encoding='utf-8')
    elif COOKIE_FILE.exists():
        COOKIE_FILE.write_text("", encoding='utf-8')
    # 确保DATA_DIR存在
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env_content = ''
    if ENV_FILE.exists():
        env_content = ENV_FILE.read_text(encoding='utf-8')
    if 'LANHU_COOKIE=' in env_content:
        lines = env_content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('LANHU_COOKIE='):
                lines[i] = f'LANHU_COOKIE={cookie}'
        env_content = '\n'.join(lines)
    elif cookie:
        if env_content and not env_content.endswith('\n'):
            env_content += '\n'
        env_content += f'LANHU_COOKIE={cookie}\n'
    ENV_FILE.write_text(env_content, encoding='utf-8')


def active_user_query_suffix() -> str:
    """生成 MCP URL 上的当前用户查询参数。"""
    active = get_active_account()
    if not active:
        return ""
    name = quote(active.get("name") or "LanhuUser")
    role = quote(active.get("role") or "Developer")
    return f"?role={role}&name={name}"


def current_mcp_url(port: int) -> str:
    """生成当前端口和当前用户身份对应的 MCP 地址。"""
    return f"http://localhost:{port}/mcp{active_user_query_suffix()}"


def account_primary_contact(account: dict) -> str:
    """返回账号最适合展示的联系方式。"""
    return (
        str(account.get("email") or "")
        or str(account.get("mobile") or "")
        or str(account.get("username") or "")
        or "未读取联系方式"
    )


def account_detail_line(account: dict) -> str:
    """生成账号详细资料行，避免界面重复拼接。"""
    parts = [
        f"ID {account.get('id') or '-'}",
        f"联系 {account_primary_contact(account)}",
        f"用户名 {account.get('username') or account.get('nickname') or '未读取到'}",
    ]
    if account.get("company"):
        parts.append(f"公司 {account.get('company')}")
    if account.get("team"):
        parts.append(f"团队 {account.get('team')}")
    if account.get("role"):
        parts.append(f"角色 {account.get('role')}")
    return "  |  ".join(parts)


def account_profile_line(account: dict) -> str:
    """生成账号个人资料补充行。"""
    avatar = str(account.get("avatar") or "")
    avatar_text = "已读取" if avatar else "未读取到"
    if avatar and len(avatar) > 44:
        avatar_text = f"{avatar[:28]}...{avatar[-12:]}"
    return (
        f"邮箱 {account.get('email') or '未读取到'}  |  "
        f"手机号 {account.get('mobile') or '未读取到'}  |  "
        f"头像 {avatar_text}"
    )


def account_cookie_line(account: dict) -> str:
    """生成账号 Cookie 和来源摘要，不展示完整 Cookie。"""
    cookie = str(account.get("cookie") or "")
    fingerprint = str(account.get("cookie_fingerprint") or cookie_fingerprint(cookie) or "-")
    parts = [
        f"Cookie {len(cookie)} 字符",
        f"指纹 {fingerprint}",
        f"更新 {account.get('updated_at', '-')}",
    ]
    if account.get("source_url"):
        parts.append(f"来源 {account.get('source_url')}")
    return "  |  ".join(parts)


def account_cookie_expiry(account: dict) -> dict:
    """根据 Cookie 内 JWT 的 ``exp`` 推断登录有效期。

    返回字段：``status``（valid/expiring/expired/unknown）、``expires_at``
    （epoch 秒，可能为 None）、``remaining``（剩余秒数，可能为 None）。仅用于
    展示提醒，不做安全鉴权。
    """
    cookie = str((account or {}).get("cookie") or "")
    exp_values: list[int] = []
    for name, value in parse_cookie_pairs(cookie).items():
        lowered = name.lower()
        if not any(word in lowered for word in ("token", "auth", "jwt")):
            continue
        payload = decode_jwt_payload(value)
        exp = payload.get("exp")
        if isinstance(exp, (int, float)) and exp > 0:
            exp_values.append(int(exp))
    if not exp_values:
        return {"status": "unknown", "expires_at": None, "remaining": None}
    expires_at = max(exp_values)
    remaining = expires_at - int(time.time())
    if remaining <= 0:
        status = "expired"
    elif remaining <= 3 * 24 * 3600:  # 3 天内提醒
        status = "expiring"
    else:
        status = "valid"
    return {"status": status, "expires_at": expires_at, "remaining": remaining}


def account_cookie_status_line(account: dict) -> str:
    """生成登录状态/过期提醒展示行。"""
    info = account_cookie_expiry(account)
    status = info.get("status")
    if status == "unknown":
        return "登录状态：未知（Cookie 未含可解析的有效期）"
    expires_at = info.get("expires_at")
    when = "-"
    if isinstance(expires_at, int):
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(expires_at))
    if status == "expired":
        return f"登录已过期（{when}），请重新登录"
    remaining = info.get("remaining") or 0
    days = remaining // 86400
    hours = (remaining % 86400) // 3600
    if status == "expiring":
        return f"登录即将过期：{when}（剩余 {days} 天 {hours} 小时），建议尽快重新登录"
    return f"登录有效，到期 {when}（剩余 {days} 天 {hours} 小时）"
