"""
Lanhu MCP Server - 管理面板 v5 (优化版)

优化内容：
1. 现代化UI设计 - 自定义配色、圆角风格、视觉层次清晰
2. 修复Cookie截断保存Bug
3. 修复服务启动/停止逻辑
4. 增加端口范围校验和DPI感知
5. 完善异常处理和线程安全
6. MCP配置代码动态跟随端口号
7. 改进IDE检测路径
8. 增加日志级别分类显示
"""
import os
import sys
import json
import time
import socket
import threading
import subprocess
import webbrowser
import traceback
from pathlib import Path
from datetime import datetime

# ============================================
# DPI 感知（高分屏适配）
# ============================================
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# 路径配置
if getattr(sys, 'frozen', False):
    APP_DIR = Path(os.path.dirname(sys.executable))
else:
    APP_DIR = Path(__file__).parent

DATA_DIR = Path(os.environ.get('APPDATA', '~')) / 'LanhuMCP'
DATA_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = DATA_DIR / '.env'
COOKIE_FILE = DATA_DIR / 'cookie.txt'
LANHU_URL = "https://lanhuapp.com/web/"

# 全局变量：待处理的Cookie（由HTTP回调服务器设置）
_pending_cookie = None

# ============================================
# 现代配色方案
# ============================================
COLORS = {
    'bg': '#F5F7FA',           # 主背景 - 浅灰蓝
    'card': '#FFFFFF',         # 卡片背景 - 白色
    'primary': '#4A6CF7',      # 主色调 - 蓝紫色
    'primary_hover': '#3B5DE7',
    'primary_light': '#E0E7FF',# 主色浅色背景
    'success': '#22C55E',      # 成功绿
    'danger': '#EF4444',       # 错误红
    'warning': '#F59E0B',      # 警告橙
    'text_primary': '#1E293B', # 主文字
    'text_secondary': '#64748B',# 次要文字
    'text_muted': '#94A3B8',   # 弱化文字
    'border': '#E2E8F0',       # 边框
    'border_light': '#F1F5F9',
    'log_bg': '#0F172A',       # 日志背景（深色终端风）
    'log_text': '#E2E8F0',
    'accent': '#8B5CF6',       # 强调紫
    'shadow': 'rgba(0, 0, 0, 0.05)',  # 卡片阴影色
}


# ============================================
# 工具函数
# ============================================

def find_server_exe():
    """在多个位置查找server exe"""
    candidates = [
        APP_DIR / 'lanhu_mcp.exe',
        APP_DIR / 'dist' / 'lanhu_mcp.exe',
        APP_DIR / 'dist' / 'lanhu_mcp' / 'lanhu_mcp.exe',
        APP_DIR / 'lanhu_mcp_server.exe',
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def find_server_dir():
    exe = find_server_exe()
    return exe.parent if exe else None


def is_port_in_use(port):
    if not (1 <= port <= 65535):
        return True  # 非法端口视为占用
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(('localhost', port)) == 0


def validate_port(port_str):
    """校验端口，返回 (valid:bool, port:int, error:str)
    valid=True 表示端口格式合法（未检查是否被占用）"""
    try:
        p = int(port_str)
        if not (1 <= p <= 65535):
            return False, 0, f"端口范围: 1-65535，当前值: {p}"
        return True, p, ""
    except ValueError:
        return False, 0, "端口必须是数字"


def load_cookie():
    """加载完整Cookie（不截断）"""
    if COOKIE_FILE.exists():
        return COOKIE_FILE.read_text(encoding='utf-8').strip()
    if ENV_FILE.exists():
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('LANHU_COOKIE='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


def save_cookie(cookie):
    """保存完整Cookie"""
    if not cookie or cookie.strip() == '':
        return
    cookie = cookie.strip()
    COOKIE_FILE.write_text(cookie, encoding='utf-8')
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
    else:
        if env_content and not env_content.endswith('\n'):
            env_content += '\n'
        env_content += f'LANHU_COOKIE={cookie}\n'
    ENV_FILE.write_text(env_content, encoding='utf-8')


# ============================================
# AI IDE 检测（增强版）
# ============================================

IDE_REGISTRY = {
    'Cursor': {
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Cursor' / 'Cursor.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'cursor' / 'Cursor.exe',
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'Cursor' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        ],
    },
    'Windsurf': {
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Windsurf' / 'Windsurf.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'windsurf' / 'Windsurf.exe',
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        ],
    },
    'Claude Desktop': {
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Claude' / 'Claude.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Claude' / 'Claude.exe',
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'Claude' / 'claude_desktop_config.json',
        ],
    },
    'VS Code + Cline': {
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Microsoft VS Code' / 'Code.exe',
            Path(os.environ.get('PROGRAMFILES', '')) / 'Microsoft VS Code' / 'Code.exe',
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        ],
    },
    'Trae': {
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Trae' / 'Trae.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Trae' / 'Trae.exe',
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'Trae' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        ],
    },
    'Cherry Studio': {
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'cherry-studio' / 'Cherry Studio.exe',
            Path(os.environ.get('APPDATA', '')) / 'cherry-studio' / 'Cherry Studio.exe',
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'cherry-studio' / 'mcp.json',
        ],
    },
    'ChatBox': {
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'chatbox' / 'Chatbox.exe',
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'chatbox' / 'config.json',
        ],
    },
    'Continue': {
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Microsoft VS Code' / 'Code.exe',
        ],
        'config': [
            Path.home() / '.continue' / 'config.yaml',
        ],
    },
    'Cline (OpenCode)': {
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'opencode' / 'OpenCode.exe',
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'opencode' / 'mcp.json',
        ],
    },
    'Junie (JetBrains)': {
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'JetBrains' / 'Toolbox' / 'apps' / 'Junie' / 'ch-0' / 'Junie.exe',
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'JetBrains' / 'Junie' / 'mcp.json',
        ],
    },
}


class IDEManager:
    @staticmethod
    def _check_ide_installed(info):
        """真实检测IDE是否已安装（检查exe文件存在性+文件大小）"""
        for exe_path in info['exe']:
            if exe_path.exists():
                # 验证是文件不是目录，且大小合理（>1MB）
                if exe_path.is_file() and exe_path.stat().st_size > 1024 * 1024:
                    return True
        return False

    @staticmethod
    def _check_config_exists(info):
        """检查IDE的MCP配置目录是否存在"""
        for config_path in info['config']:
            if config_path.parent.exists():
                return True
        return False

    @staticmethod
    def detect_all():
        results = {}
        for name, info in IDE_REGISTRY.items():
            installed = IDEManager._check_ide_installed(info)
            results[name] = installed
        return results

    @staticmethod
    def get_detection_details():
        """获取详细的检测信息（用于调试）"""
        details = {}
        for name, info in IDE_REGISTRY.items():
            exe_found = None
            for exe_path in info['exe']:
                if exe_path.exists() and exe_path.is_file():
                    exe_found = exe_path
                    break
            
            config_found = None
            for config_path in info['config']:
                if config_path.parent.exists():
                    config_found = config_path
                    break
            
            details[name] = {
                'installed': exe_found is not None,
                'exe_path': str(exe_found) if exe_found else None,
                'config_dir': str(config_found.parent) if config_found else None,
                'config_path': str(config_found) if config_found else None,
            }
        return details

    @staticmethod
    def configure(ide_name, port=8000):
        if ide_name not in IDE_REGISTRY:
            return False, "未知IDE"

        config_path = None
        for p in IDE_REGISTRY[ide_name]['config']:
            if p.parent.exists():
                config_path = p
                break

        if not config_path:
            return False, f"{ide_name} 配置目录不存在"

        config = {}
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        # YAML格式特殊处理
                        if str(config_path).endswith('.yaml') or str(config_path).endswith('.yml'):
                            import yaml
                            config = yaml.safe_load(content) or {}
                        else:
                            config = json.loads(content)
            except json.JSONDecodeError:
                config = {}
            except ImportError:
                # yaml模块可能不存在，尝试简单解析
                pass
            except Exception:
                config = {}

        if 'mcpServers' not in config:
            config['mcpServers'] = {}

        config['mcpServers']['lanhu'] = {
            'url': f'http://localhost:{port}/mcp',
            'disabled': False,
        }

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            if str(config_path).endswith('.yaml') or str(config_path).endswith('.yml'):
                import yaml
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            else:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
            return True, f"已配置 {ide_name}"
        except PermissionError:
            return False, f"权限不足，无法写入 {config_path}"
        except Exception as e:
            return False, f"写入失败: {e}"

    @staticmethod
    def configure_all(port=8000):
        results = []
        detected = IDEManager.detect_all()
        for name, installed in detected.items():
            if installed:
                ok, msg = IDEManager.configure(name, port)
                results.append((name, ok, msg))
        return results


# ============================================
# 服务管理（子进程）- 增强版
# ============================================

class ServiceManager:
    _process = None
    _running = False
    _port = 8000
    _stop_event = threading.Event()
    _lock = threading.Lock()

    @staticmethod
    def is_running():
        with ServiceManager._lock:
            if ServiceManager._process is None:
                return False
            if ServiceManager._process.poll() is not None:
                ServiceManager._running = False
                return False
            return ServiceManager._running

    @staticmethod
    def start(port=8000, on_output=None, on_error=None):
        with ServiceManager._lock:
            if ServiceManager.is_running():
                return False, "服务已在运行"

            valid, p, err = validate_port(str(port))
            if not valid:
                return False, err
            if is_port_in_use(p):
                return False, f"端口 {port} 已被占用，请更换端口或关闭占用程序"

        server_exe = find_server_exe()
        if not server_exe:
            return False, (
                "未找到 lanhu_mcp.exe\n"
                "请确保以下位置之一存在该文件:\n"
                "  • 同目录下 lanhu_mcp.exe\n"
                "  • dist/lanhu_mcp.exe\n"
                "  • dist/lanhu_mcp/lanhu_mcp.exe"
            )

        server_dir = server_exe.parent

        # 准备环境变量
        env = os.environ.copy()
        if ENV_FILE.exists():
            try:
                with open(ENV_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            k, v = line.split('=', 1)
                            env[k.strip()] = v.strip().strip('"').strip("'")
            except Exception as e:
                if on_error:
                    on_error(f"读取环境变量失败: {e}")

        env['SERVER_PORT'] = str(port)
        env['MCP_TRANSPORT'] = 'http'

        ServiceManager._stop_event.clear()

        try:
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW

            ServiceManager._process = subprocess.Popen(
                [str(server_exe)],
                cwd=str(server_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            ServiceManager._running = True
            ServiceManager._port = port

            # 读取输出线程
            def read_output():
                try:
                    for line in iter(ServiceManager._process.stdout.readline, b''):
                        if ServiceManager._stop_event.is_set():
                            break
                        if on_output:
                            decoded = line.decode('utf-8', errors='replace').rstrip('\n\r')
                            on_output(decoded)
                except Exception:
                    pass

            threading.Thread(target=read_output, daemon=True).start()

            # 等待启动（最多15秒）
            for i in range(30):
                time.sleep(0.5)
                if ServiceManager._stop_event.is_set():
                    return False, "已取消启动"
                if is_port_in_use(port):
                    return True, "服务已启动"

            # 检查进程是否退出
            if ServiceManager._process.poll() is not None:
                ServiceManager._running = False
                rc = ServiceManager._process.returncode
                return False, f"服务启动失败（进程退出码: {rc}，请检查日志）"

            return True, "服务启动中..."

        except OSError as e:
            ServiceManager._running = False
            return False, f"启动失败(权限/路径): {e}"
        except Exception as e:
            ServiceManager._running = False
            return False, f"启动失败: {type(e).__name__}: {e}"

    @staticmethod
    def stop():
        if ServiceManager._process is None:
            return False, "服务未运行"

        ServiceManager._stop_event.set()
        ServiceManager._running = False

        try:
            ServiceManager._process.terminate()
            try:
                ServiceManager._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ServiceManager._process.kill()
                ServiceManager._process.wait(timeout=3)
        except Exception:
            try:
                ServiceManager._process.kill()
            except Exception:
                pass

        ServiceManager._process = None
        return True, "服务已停止"


# ============================================
# Cookie获取（自动获取）
# ============================================

import http.server
import socketserver
import urllib.parse

# 全局变量：Cookie回调服务器
_cookie_server = None
_cookie_server_port = None


class CookieCallbackHandler(http.server.BaseHTTPRequestHandler):
    """处理Cookie回调的HTTP处理器"""
    
    def log_message(self, format, *args):
        pass  # 禁用HTTP服务器日志
    
    def do_GET(self):
        if self.path.startswith('/callback'):
            # 解析URL中的cookie参数
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            cookie = params.get('cookie', [''])[0]
            
            if cookie:
                # 发送成功响应
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = '''
                <html><body>
                <h2>Cookie获取成功！</h2>
                <p>请返回Lanhu MCP Server查看。</p>
                <script>setTimeout(function(){window.close();}, 2000);</script>
                </body></html>
                '''
                self.wfile.write(response.encode('utf-8'))
                
                # 通过全局变量传递cookie
                global _pending_cookie
                _pending_cookie = cookie
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write('Cookie为空'.encode('utf-8'))
        else:
            # 主页面：显示使用说明和bookmarket
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            page = '''
            <html><head><meta charset="utf-8"><title>Lanhu MCP - Cookie获取</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; 
                       max-width: 600px; margin: 50px auto; padding: 20px;
                       background: #f5f7fa; color: #1e293b; }
                .card { background: white; border-radius: 12px; padding: 24px; 
                        box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
                h1 { color: #4a6cf7; margin-top: 0; }
                .step { background: #f8fafc; border-left: 4px solid #4a6cf7;
                        padding: 12px 16px; margin: 12px 0; border-radius: 0 8px 8px 0; }
                .step-num { color: #4a6cf7; font-weight: bold; margin-right: 8px; }
                .btn { display: inline-block; background: #4a6cf7; color: white;
                       padding: 12px 24px; border-radius: 8px; text-decoration: none;
                       font-weight: bold; margin-top: 16px; cursor: pointer; }
                .btn:hover { background: #3b5de7; }
                .success { color: #22c55e; font-weight: bold; }
            </style>
            </head><body>
            <div class="card">
                <h1>Lanhu MCP - Cookie自动获取</h1>
                <p>请按以下步骤操作：</p>
                <div class="step">
                    <span class="step-num">1.</span> 点击下方按钮打开蓝湖登录页面
                </div>
                <div class="step">
                    <span class="step-num">2.</span> 在蓝湖页面完成登录
                </div>
                <div class="step">
                    <span class="step-num">3.</span> 登录成功后，点击下方「获取Cookie」按钮
                </div>
                <div class="step">
                    <span class="step-num">4.</span> Cookie将自动保存，可关闭此页面
                </div>
                <a class="btn" href="https://lanhuapp.com/web/" target="_blank">打开蓝湖登录</a>
                <a class="btn" id="getCookieBtn" style="background:#22c55e;margin-left:12px;">获取Cookie</a>
                <div id="status" style="margin-top:16px;"></div>
            </div>
            <script>
            document.getElementById('getCookieBtn').onclick = function() {
                var cookie = document.cookie;
                if (!cookie || cookie.length < 10) {
                    document.getElementById('status').innerHTML = '<span style="color:red">未检测到Cookie，请先登录蓝湖</span>';
                    return;
                }
                var xhr = new XMLHttpRequest();
                xhr.open('GET', '/callback?cookie=' + encodeURIComponent(cookie), true);
                xhr.onload = function() {
                    if (xhr.status === 200) {
                        document.getElementById('status').innerHTML = '<span class="success">Cookie获取成功！可关闭此页面。</span>';
                        document.getElementById('getCookieBtn').style.background = '#94a3b8';
                    }
                };
                xhr.send();
            };
            </script>
            </body></html>
            '''
            self.wfile.write(page.encode('utf-8'))


def _start_cookie_server():
    """启动Cookie回调服务器"""
    global _cookie_server, _cookie_server_port
    if _cookie_server is not None:
        return _cookie_server_port
    
    try:
        # 尝试绑定到随机可用端口
        handler = CookieCallbackHandler
        _cookie_server = socketserver.TCPServer(("127.0.0.1", 0), handler)
        _cookie_server_port = _cookie_server.server_address[1]
        
        # 在后台线程运行服务器
        server_thread = threading.Thread(target=_cookie_server.serve_forever, daemon=True)
        server_thread.start()
        
        return _cookie_server_port
    except Exception:
        _cookie_server = None
        _cookie_server_port = None
        return None


def open_lanhu_login():
    """打开蓝湖登录页面"""
    webbrowser.open(LANHU_URL)


# ============================================
# 现代化 GUI
# ============================================

def apply_modern_style(root):
    """应用现代主题样式"""
    style = ttk.Style()

    # 尝试使用 clam 主题作为基础（比默认好看）
    available_themes = style.theme_names()
    if 'clam' in available_themes:
        style.theme_use('clam')

    # ===== 全局配置 =====
    style.configure('.', background=COLORS['bg'], foreground=COLORS['text_primary'])
    style.map('.', background=[('active', COLORS['primary_hover'])])

    # ===== Frame =====
    style.configure('TFrame', background=COLORS['bg'])
    style.configure('Card.TFrame', background=COLORS['card'])

    # ===== Label =====
    style.configure('TLabel', background=COLORS['bg'], foreground=COLORS['text_primary'],
                    font=('Segoe UI', 9))
    style.configure('Title.TLabel', background=COLORS['bg'], foreground=COLORS['text_primary'],
                    font=('Segoe UI', 24, 'bold'))
    style.configure('Subtitle.TLabel', background=COLORS['bg'], foreground=COLORS['text_secondary'],
                    font=('Segoe UI', 10))
    style.configure('Status.TLabel', background=COLORS['card'], foreground=COLORS['text_primary'],
                    font=('Segoe UI', 11, 'bold'))
    style.configure('StatusRunning.TLabel', background=COLORS['card'], foreground=COLORS['success'],
                    font=('Segoe UI', 11, 'bold'))
    style.configure('StatusError.TLabel', background=COLORS['card'], foreground=COLORS['danger'],
                    font=('Segoe UI', 11, 'bold'))
    style.configure('StatusWarn.TLabel', background=COLORS['card'], foreground=COLORS['warning'],
                    font=('Segoe UI', 11, 'bold'))
    style.configure('Hint.TLabel', background=COLORS['card'], foreground=COLORS['text_muted'],
                    font=('Segoe UI', 8))

    # ===== LabelFrame（卡片容器）=====
    style.configure('Card.TLabelframe', background=COLORS['card'], foreground=COLORS['text_primary'])
    style.configure('Card.TLabelframe.Label', background=COLORS['card'],
                    foreground=COLORS['primary'], font=('Segoe UI', 10, 'bold'),
                    padding=(10, 5, 0, 5))
    style.configure('TLabelframe', background=COLORS['card'], foreground=COLORS['text_primary'])
    style.configure('TLabelframe.Label', background=COLORS['card'],
                    foreground=COLORS['primary'], font=('Segoe UI', 10, 'bold'))

    # ===== Button =====
    style.configure('TButton', font=('Segoe UI', 9), padding=(12, 6),
                    background='#FFFFFF', foreground=COLORS['text_primary'],
                    borderwidth=1, relief='solid')
    style.map('TButton',
              background=[('active', COLORS['primary_light'] if 'primary_light' in COLORS else '#E0E7FF'),
                         ('pressed', COLORS['primary'])],
              foreground=[('active', COLORS['primary']), ('pressed', '#FFFFFF')],
              bordercolor=[('focus', COLORS['primary'])])

    style.configure('Primary.TButton', font=('Segoe UI', 10, 'bold'), padding=(16, 8),
                    background=COLORS['primary'], foreground='#FFFFFF',
                    borderwidth=0, relief='flat')
    style.map('Primary.TButton',
              background=[('active', COLORS['primary_hover']), ('pressed', '#2D4BD4')],
              foreground=[('active', '#FFFFFF'), ('pressed', '#FFFFFF')])

    style.configure('Success.TButton', font=('Segoe UI', 9), padding=(12, 6),
                    background=COLORS['success'], foreground='#FFFFFF',
                    borderwidth=0, relief='flat')
    style.map('Success.TButton',
              background=[('active', '#16A34A'), ('pressed', '#15803D')])

    style.configure('Danger.TButton', font=('Segoe UI', 9), padding=(12, 6),
                    background=COLORS['danger'], foreground='#FFFFFF',
                    borderwidth=0, relief='flat')
    style.map('Danger.TButton',
              background=[('active', '#DC2626'), ('pressed', '#B91C1C')])

    style.configure('Small.TButton', font=('Segoe UI', 8), padding=(8, 4),
                    background=COLORS['border_light'], foreground=COLORS['text_secondary'],
                    borderwidth=0, relief='flat')

    # ===== Entry =====
    style.configure('TEntry', font=('Consolas', 9), padding=(8, 6),
                    fieldbackground='#FFFFFF', insertcolor=COLORS['text_primary'])

    # ===== ScrolledText =====
    style.configure('Log.TFrame', background=COLORS['log_bg'])

    return style


def create_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox, scrolledtext
    except ImportError:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "需要安装 tkinter", "错误", 0)
        return

    root = tk.Tk()
    root.title("Lanhu MCP Server")
    # 设置窗口图标（如果存在）
    icon_path = APP_DIR / 'icon.ico'
    if icon_path.exists():
        try:
            root.iconbitmap(str(icon_path))
        except Exception:
            pass
    root.geometry("960x780")
    root.minsize(860, 680)
    root.configure(bg=COLORS['bg'])

    # 应用样式
    style = apply_modern_style(root)

    # 变量
    port_var = tk.StringVar(value="8000")
    cookie_var = tk.StringVar()
    full_cookie = ''  # 存储完整Cookie（不截断）

    # ========== 主容器 ==========
    main = ttk.Frame(root, padding=20, style='TFrame')
    main.pack(fill=tk.BOTH, expand=True)

    # ---- 标题区域 ----
    header = ttk.Frame(main, style='TFrame')
    header.pack(fill=tk.X, pady=(0, 20))

    title_frame = ttk.Frame(header, style='TFrame')
    title_frame.pack(side=tk.LEFT)

    # Logo/图标文字
    ttk.Label(title_frame, text="🎨", font=('Segoe UI Emoji', 32),
              background=COLORS['bg']).pack(side=tk.LEFT, padx=(0, 12))

    texts = ttk.Frame(title_frame, style='TFrame')
    texts.pack(side=tk.LEFT, anchor='w')
    ttk.Label(texts, text="Lanhu MCP Server", style='Title.TLabel').pack(anchor='w')
    ttk.Label(texts, text="让所有 AI 助手都能读取蓝湖设计稿",
              style='Subtitle.TLabel').pack(anchor='w', pady=(2, 0))

    # 版本信息
    ver_label = ttk.Label(header, text="v5.0", style='Hint.TLabel')
    ver_label.pack(side=tk.RIGHT, anchor='se', pady=(10, 0))

    # ==================== 服务状态卡片 ====================
    sf = ttk.LabelFrame(main, text=" ⚡ 服务状态 ", style='Card.TLabelframe', padding=18)
    sf.pack(fill=tk.X, pady=(0, 14))

    status_row = ttk.Frame(sf, style='Card.TFrame')
    status_row.pack(fill=tk.X)

    # 状态指示器
    status_lbl = ttk.Label(status_row, text="● 未运行", style='StatusError.TLabel')
    status_lbl.pack(side=tk.LEFT)

    # 分隔线效果
    sep = tk.Frame(status_row, width=1, height=24, bg=COLORS['border'])
    sep.pack(side=tk.LEFT, padx=(20, 20))

    # 端口设置
    ttk.Label(status_row, text="端口:", style='TLabel',
              background=COLORS['card']).pack(side=tk.LEFT)
    port_entry = ttk.Entry(status_row, textvariable=port_var, width=7, font=('Consolas', 11, 'bold'))
    port_entry.pack(side=tk.LEFT, padx=(6, 20))

    # 按钮组
    btn_group = ttk.Frame(status_row, style='Card.TFrame')
    btn_group.pack(side=tk.LEFT)

    start_btn = ttk.Button(btn_group, text="▶ 启动服务", style='Primary.TButton', width=12)
    start_btn.pack(side=tk.LEFT, padx=(0, 8))

    stop_btn = ttk.Button(btn_group, text="■ 停止", style='Danger.TButton', width=8,
                          state=tk.DISABLED)
    stop_btn.pack(side=tk.LEFT)

    # 右侧按钮
    right_btns = ttk.Frame(status_row, style='Card.TFrame')
    right_btns.pack(side=tk.RIGHT)

    ttk.Button(right_btns, text="🔗 打开MCP页面", style='Small.TButton',
               command=lambda: webbrowser.open(f"http://localhost:{port_var.get()}/mcp")).pack(side=tk.LEFT)

    # ==================== 日志卡片 ====================
    log_sf = ttk.LabelFrame(main, text=" 📋 运行日志 ", style='Card.TLabelframe', padding=12)
    log_sf.pack(fill=tk.BOTH, expand=True, pady=(0, 14))

    # 日志工具栏
    log_toolbar = ttk.Frame(log_sf, style='Card.TFrame')
    log_toolbar.pack(fill=tk.X, pady=(0, 8))

    ttk.Label(log_toolbar, text="日志自动滚动  |  ", style='Hint.TLabel',
              background=COLORS['card']).pack(side=tk.LEFT)
    clear_log_btn = ttk.Button(log_toolbar, text="🗑 清空日志", style='Small.TButton', width=10)
    clear_log_btn.pack(side=tk.LEFT)

    # 日志文本框（深色终端风格）
    log_container = ttk.Frame(log_sf, style='Log.TFrame')
    log_container.pack(fill=tk.BOTH, expand=True)

    log_scrollbar = tk.Scrollbar(log_container, bg=COLORS['log_bg'],
                                  troughcolor=COLORS['log_bg'],
                                  activebackground=COLORS['text_muted'],
                                  highlightthickness=0, relief='flat')
    log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    log_text = tk.Text(log_container, height=10, font=('Consolas', 9),
                       bg=COLORS['log_bg'], fg=COLORS['log_text'],
                       insertbackground=COLORS['log_text'],
                       selectbackground=COLORS['primary'],
                       wrap=tk.WORD, state=tk.DISABLED,
                       padx=10, pady=8, relief='flat',
                       borderwidth=0, highlightthickness=0,
                       yscrollcommand=log_scrollbar.set)
    log_scrollbar.config(command=log_text.yview)
    log_text.pack(fill=tk.BOTH, expand=True)

    # 配置日志文本标签颜色
    log_text.tag_configure('timestamp', foreground=COLORS['text_muted'])
    log_text.tag_configure('info', foreground='#93C5FD')
    log_text.tag_configure('success', foreground=COLORS['success'])
    log_text.tag_configure('error', foreground='#FCA5A5')
    log_text.tag_configure('warn', foreground=COLORS['warning'])
    log_text.tag_configure('server', foreground='#C4B5FD')

    # 日志函数
    def log(msg, level='info'):
        ts = datetime.now().strftime("%H:%M:%S")
        log_text.config(state=tk.NORMAL)
        log_text.insert(tk.END, f"[{ts}] ", 'timestamp')
        log_text.insert(tk.END, f"{msg}\n", level)
        log_text.see(tk.END)
        log_text.config(state=tk.DISABLED)

    def on_server_output(line):
        root.after(0, lambda l=line: log(f"[server] {l}", 'server'))

    def on_server_error(err):
        root.after(0, lambda e=err: log(f"[ERROR] {e}", 'error'))

    # 清空日志
    def do_clear_log():
        log_text.config(state=tk.NORMAL)
        log_text.delete(1.0, tk.END)
        log_text.config(state=tk.DISABLED)
        log("日志已清空", 'info')

    clear_log_btn.config(command=do_clear_log)

    # ==================== 启动/停止逻辑 ====================
    def do_start():
        valid, p, err = validate_port(port_var.get())
        if err:
            messagebox.showerror("端口错误", err)
            return

        start_btn.config(state=tk.DISABLED)
        stop_btn.config(state=tk.DISABLED)
        status_lbl.config(text="● 启动中...", style='StatusWarn.TLabel')
        root.update()

        def _start():
            ok, msg = ServiceManager.start(p, on_server_output, on_server_error)
            root.after(0, lambda: _on_result(ok, msg))

        threading.Thread(target=_start, daemon=True).start()

    def _on_result(ok, msg):
        if ok:
            status_lbl.config(text=f"● 运行中 (:{port_var.get()})", style='StatusRunning.TLabel')
            start_btn.config(state=tk.DISABLED)
            stop_btn.config(state=tk.NORMAL)
            log(f"✅ {msg} → http://localhost:{port_var.get()}/mcp", 'success')
            update_mcp_code()
        else:
            status_lbl.config(text="● 启动失败", style='StatusError.TLabel')
            start_btn.config(state=tk.NORMAL)
            stop_btn.config(state=tk.DISABLED)
            log(f"❌ {msg}", 'error')
            messagebox.showerror("启动失败", msg)

    def do_stop():
        ok, msg = ServiceManager.stop()
        status_lbl.config(text="● 未运行", style='StatusError.TLabel')
        start_btn.config(state=tk.NORMAL)
        stop_btn.config(state=tk.DISABLED)
        log(f"⏹ {msg}", 'info')

    start_btn.config(command=do_start)
    stop_btn.config(command=do_stop)

    # ==================== 蓝湖登录卡片 ====================
    cf = ttk.LabelFrame(main, text=" 🔐 蓝湖 Cookie 配置 ", style='Card.TLabelframe', padding=18)
    cf.pack(fill=tk.X, pady=(0, 14))

    cookie_row = ttk.Frame(cf, style='Card.TFrame')
    cookie_row.pack(fill=tk.X)

    ttk.Label(cookie_row, text="Cookie:", style='TLabel',
              background=COLORS['card']).pack(side=tk.LEFT)

    # 加载完整Cookie
    saved = load_cookie()
    full_cookie = saved  # 保存完整版本
    display_cookie = saved[:60] + '...' if len(saved) > 60 else saved
    cookie_var.set(display_cookie)

    cookie_entry = ttk.Entry(cookie_row, textvariable=cookie_var, width=50)
    cookie_entry.pack(side=tk.LEFT, padx=(8, 12), fill=tk.X, expand=True)

    def do_open_lanhu():
        """启动Cookie自动获取服务器并打开蓝湖登录"""
        port = _start_cookie_server()
        if port:
            # 打开本地回调页面
            callback_url = f"http://127.0.0.1:{port}"
            webbrowser.open(callback_url)
            log(f"🌐 已打开Cookie获取页面，请在浏览器中登录蓝湖", 'info')
            log(f"💡 登录后点击页面上的「获取Cookie」按钮", 'info')
            # 启动定时检查线程
            def check_cookie():
                global _pending_cookie
                for _ in range(120):  # 最多等待2分钟
                    time.sleep(1)
                    if _pending_cookie:
                        cookie = _pending_cookie
                        _pending_cookie = None
                        root.after(0, lambda c=cookie: _on_cookie_received(c))
                        return
                root.after(0, lambda: log("⚠️ Cookie获取超时，请重试", 'warn'))
            threading.Thread(target=check_cookie, daemon=True).start()
        else:
            # 服务器启动失败，降级到手动模式
            open_lanhu_login()
            log("⚠️ 自动获取服务启动失败，请手动复制Cookie", 'warn')
    
    def _on_cookie_received(cookie):
        """Cookie获取成功回调"""
        nonlocal full_cookie
        if cookie and len(cookie) > 10:
            full_cookie = cookie
            cookie_var.set(cookie[:80] + '...' if len(cookie) > 80 else cookie)
            save_cookie(cookie)
            log(f"✅ Cookie 自动获取成功 ({len(cookie)} 字符)", 'success')
        else:
            log("⚠️ 获取的Cookie无效，请重试", 'warn')

    def do_save_cookie():
        c = cookie_var.get().strip()
        # 如果用户没有修改（还是截断状态），使用完整保存的Cookie
        if '...' in c:
            c = full_cookie
        if not c or c.strip() == '':
            messagebox.showwarning("提示", "Cookie 为空，请先输入或从浏览器复制")
            return
        save_cookie(c)
        full_cookie = c  # 更新完整Cookie缓存
        log(f"✅ Cookie 已保存 ({len(c)} 字符)", 'success')
        messagebox.showinfo("成功", f"Cookie 已保存！\n长度: {len(c)} 字符")

    def do_paste_cookie():
        """从剪贴板粘贴Cookie"""
        nonlocal full_cookie
        try:
            clip = root.clipboard_get()
            if clip and len(clip) > 10:
                cookie_var.set(clip[:80] + '...' if len(clip) > 80 else clip)
                full_cookie = clip
                log(f"📋 从剪贴板粘贴了 Cookie ({len(clip)} 字符)", 'info')
        except tk.TclError:
            log("剪贴板为空或无法访问", 'warn')

    btn_row = ttk.Frame(cf, style='Card.TFrame')
    btn_row.pack(fill=tk.X, pady=(10, 0))

    ttk.Button(btn_row, text="🌐 一键获取Cookie", style='Primary.TButton',
               command=do_open_lanhu).pack(side=tk.LEFT)
    ttk.Button(btn_row, text="📋 粘贴Cookie", style='TButton',
               command=do_paste_cookie).pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(btn_row, text="💾 保存Cookie", style='Success.TButton',
               command=do_save_cookie).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Label(cf,
              text="💡 点击「一键获取Cookie」→ 浏览器打开后登录蓝湖 → 登录成功后点击页面上的「获取Cookie」按钮 → 自动保存",
              style='Hint.TLabel').pack(anchor='w', pady=(10, 0))

    # ==================== AI IDE 配置卡片 ====================
    ide_f = ttk.LabelFrame(main, text=" 🤖 AI IDE 一键配置（自动检测已安装）", style='Card.TLabelframe', padding=18)
    ide_f.pack(fill=tk.X, pady=(0, 14))

    ide_grid = ttk.Frame(ide_f, style='Card.TFrame')
    ide_grid.pack(fill=tk.X)

    def refresh_ides():
        for w in ide_grid.winfo_children():
            w.destroy()

        detected = IDEManager.detect_all()
        col, row = 0, 0
        max_cols = 4

        for name, installed in detected.items():
            if col >= max_cols:
                col = 0
                row += 1

            cell = ttk.Frame(ide_grid, style='Card.TFrame')
            cell.grid(row=row, column=col, sticky='w', padx=(0, 20), pady=4)

            if installed:
                status_icon = "✅"
                fg = 'success'
                lbl_text = name
                # 配置按钮
                def make_cfg(ide=name):
                    try:
                        p = int(port_var.get())
                    except ValueError:
                        messagebox.showerror("错误", "请先输入有效端口号")
                        return
                    ok, msg = IDEManager.configure(ide, p)
                    if ok:
                        log(f"✅ {msg}", 'success')
                    else:
                        log(f"⚠️ {msg}", 'warn')
                        messagebox.showwarning("配置提示", msg)

                ttk.Label(cell, text=status_icon + " " + lbl_text,
                          foreground=COLORS[fg], background=COLORS['card'],
                          font=('Segoe UI', 9)).pack(side=tk.LEFT)
                cfg_btn = ttk.Button(cell, text="配置", style='Small.TButton', width=5)
                cfg_btn.config(command=make_cfg)
                cfg_btn.pack(side=tk.LEFT, padx=(6, 0))
            else:
                ttk.Label(cell, text="⬜ " + name,
                          foreground=COLORS['text_muted'], background=COLORS['card'],
                          font=('Segoe UI', 9)).pack(side=tk.LEFT)

            col += 1

        count = sum(1 for v in detected.values() if v)
        log(f"检测到 {count}/{len(detected)} 个已安装的 AI IDE", 'info')

    refresh_ides()

    # IDE 操作按钮行
    ide_btn_row = ttk.Frame(ide_f, style='Card.TFrame')
    ide_btn_row.pack(fill=tk.X, pady=(12, 0))

    ttk.Button(ide_btn_row, text="🚀 一键配置全部已安装 IDE", style='Primary.TButton',
               command=lambda: _config_all()).pack(side=tk.LEFT)
    ttk.Button(ide_btn_row, text="🔄 重新检测", style='TButton',
               command=refresh_ides).pack(side=tk.LEFT, padx=(10, 0))

    def _config_all():
        try:
            p = int(port_var.get())
        except ValueError:
            messagebox.showerror("错误", "请先输入有效端口号")
            return
        results = IDEManager.configure_all(p)
        msgs = []
        for n, ok, m in results:
            icon = "✅" if ok else "❌"
            msgs.append(f"{icon} {n}: {m}")
            if ok:
                log(f"{icon} {n}: {m}", 'success')
            else:
                log(f"{icon} {n}: {m}", 'error')
        if msgs:
            messagebox.showinfo("配置结果", "\n".join(msgs))
        else:
            messagebox.showinfo("提示", "未检测到已安装的 AI IDE")

    # ==================== MCP 配置代码卡片 ====================
    mcp_f = ttk.LabelFrame(main, text=" 📝 MCP 配置代码（手动配置时复制）", style='Card.TLabelframe', padding=18)
    mcp_f.pack(fill=tk.X, pady=(0, 10))

    mcp_code = tk.Text(mcp_f, height=5, font=('Consolas', 9),
                       bg='#1E293B', fg='#E2E8F0',
                       insertbackground='#E2E8F0',
                       selectbackground=COLORS['primary'],
                       wrap=tk.NONE, state=tk.DISABLED,
                       padx=12, pady=10, relief='flat',
                       borderwidth=1, highlightthickness=1,
                       highlightbackground=COLORS['border'])
    mcp_code.pack(fill=tk.X)

    def update_mcp_code():
        try:
            p = int(port_var.get())
        except ValueError:
            p = 8000
        code = '{\n  "mcpServers": {\n    "lanhu": {\n'
        code += f'      "url": "http://localhost:{p}/mcp"\n'
        code += '    }\n  }\n}'
        mcp_code.config(state=tk.NORMAL)
        mcp_code.delete(1.0, tk.END)
        mcp_code.insert(tk.END, code)
        mcp_code.config(state=tk.DISABLED)

    # 初始化MCP代码
    update_mcp_code()

    # 端口变化时更新MCP代码
    def on_port_change(*args):
        update_mcp_code()

    port_var.trace_add('write', on_port_change)

    def copy_code():
        try:
            p = int(port_var.get())
        except ValueError:
            p = 8000
        code = '{\n  "mcpServers": {\n    "lanhu": {\n'
        code += f'      "url": "http://localhost:{p}/mcp"\n'
        code += '    }\n  }\n}'
        root.clipboard_clear()
        root.clipboard_append(code)
        log("📋 MCP 配置代码已复制到剪贴板", 'success')

    copy_btn = ttk.Button(mcp_f, text="📋 复制配置代码", style='Small.TButton', width=14)
    copy_btn.pack(pady=(10, 0))
    copy_btn.config(command=copy_code)

    # ==================== 底部状态栏 ====================
    statusbar = ttk.Frame(main, style='TFrame')
    statusbar.pack(fill=tk.X, pady=(10, 0))

    # 状态栏内容
    status_info = ttk.Frame(statusbar, style='TFrame')
    status_info.pack(fill=tk.X)

    status_left = ttk.Frame(status_info, style='TFrame')
    status_left.pack(side=tk.LEFT)

    ttk.Label(status_left, text="💡 提示: 启动服务后，在AI IDE的MCP配置中添加上方的配置代码即可使用",
              style='Hint.TLabel', background=COLORS['bg']).pack(side=tk.LEFT)

    status_right = ttk.Frame(status_info, style='TFrame')
    status_right.pack(side=tk.RIGHT)

    ttk.Label(status_right, text="Lanhu MCP Server v5.0",
              style='Hint.TLabel', background=COLORS['bg']).pack(side=tk.RIGHT)

    # 初始化日志
    server_exe = find_server_exe()
    if server_exe:
        log(f"✅ 找到服务端: {server_exe.name} ({server_exe.parent})", 'success')
    else:
        log("⚠️ 未找到 lanhu_mcp.exe — 请将服务端放在同目录下", 'warn')

    log(f"📁 数据目录: {DATA_DIR}", 'info')
    if saved:
        log(f"🔑 Cookie: 已配置 ({len(saved)} 字符)", 'success')
    else:
        log("🔑 Cookie: 未配置 — 请先配置蓝湖Cookie", 'warn')

    count = sum(1 for v in IDEManager.detect_all().values() if v)
    log(f"🤖 检测到 {count} 个已安装的 AI IDE", 'info')
    log("💡 点击「启动服务」开始使用", 'info')

    # ==================== 窗口关闭处理 ====================
    def on_close():
        if ServiceManager.is_running():
            ServiceManager.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == '__main__':
    create_gui()
