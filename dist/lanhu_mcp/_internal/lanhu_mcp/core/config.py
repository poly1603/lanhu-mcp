"""全局配置 - 环境变量、常量、默认值"""
import os
from pathlib import Path
from datetime import timezone, timedelta

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(override=False)
except ImportError:
    pass

# 东八区时区（北京时间）
CHINA_TZ = timezone(timedelta(hours=8))

# 蓝湖Cookie
DEFAULT_COOKIE = "your_lanhu_cookie_here"
COOKIE = os.getenv("LANHU_COOKIE", DEFAULT_COOKIE)

# API基础URL
BASE_URL = "https://lanhuapp.com"
DDS_BASE_URL = "https://dds.lanhuapp.com"
CDN_URL = "https://axure-file.lanhuapp.com"
DDS_COOKIE = os.getenv("DDS_COOKIE", COOKIE)

# 飞书机器人Webhook配置
DEFAULT_FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook-key-here"
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", DEFAULT_FEISHU_WEBHOOK)

# 数据存储目录
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# HTTP请求超时时间（秒）
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30"))

# 浏览器视口尺寸
VIEWPORT_WIDTH = int(os.getenv("VIEWPORT_WIDTH", "1920"))
VIEWPORT_HEIGHT = int(os.getenv("VIEWPORT_HEIGHT", "1080"))

# 调试模式
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# MCP传输模式
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "http").lower()
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# 角色枚举
VALID_ROLES = ["后端", "前端", "客户端", "开发", "运维", "产品", "项目经理"]

# @提醒只允许具体人名
MENTION_ROLES = [
    "张三", "李四", "王五", "赵六", "钱七", "孙八",
    "周九", "吴十", "郑十一", "冯十二", "陈十三", "褚十四",
    "卫十五", "蒋十六", "沈十七", "韩十八", "杨十九", "朱二十"
]

# 飞书用户ID映射
FEISHU_USER_ID_MAP = {
    '张三': '0000000000000000001',
    '李四': '0000000000000000002',
    '王五': '0000000000000000003',
    '赵六': '0000000000000000004',
    '钱七': '0000000000000000005',
    '孙八': '0000000000000000006',
    '周九': '0000000000000000007',
    '吴十': '0000000000000000008',
    '郑十一': '0000000000000000009',
    '冯十二': '0000000000000000010',
    '陈十三': '0000000000000000011',
    '褚十四': '0000000000000000012',
    '卫十五': '0000000000000000013',
    '蒋十六': '0000000000000000014',
    '沈十七': '0000000000000000015',
    '韩十八': '0000000000000000016',
    '杨十九': '0000000000000000017',
    '朱二十': '0000000000000000018',
}

# 角色映射规则（按优先级排序）
ROLE_MAPPING_RULES = [
    (["后端", "backend", "服务端", "server", "java", "php", "python", "go", "golang", "node", "nodejs", ".net", "c#"], "后端"),
    (["前端", "frontend", "h5", "web", "vue", "react", "angular", "javascript", "js", "ts", "typescript", "css"], "前端"),
    (["客户端", "client", "ios", "android", "安卓", "移动端", "mobile", "app", "flutter", "rn", "react native", "swift", "kotlin", "objective-c", "oc"], "客户端"),
    (["运维", "ops", "devops", "sre", "dba", "运营维护", "系统管理", "infra", "infrastructure"], "运维"),
    (["产品", "product", "pm", "产品经理", "需求"], "产品"),
    (["项目经理", "项目", "pmo", "project manager", "scrum", "敏捷"], "项目经理"),
    (["开发", "dev", "developer", "程序员", "coder", "engineer", "工程师"], "开发"),
]

# 元数据缓存配置
_metadata_cache = {}
