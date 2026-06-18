"""
Lanhu MCP Server - 可视化管理界面 v3

修复：
1. 通过子进程启动server（不再内嵌import）
2. 浏览器自动获取Cookie
3. 支持所有主流AI IDE
"""
import os
import sys
import json
import time
import signal
import socket
import threading
import subprocess
import webbrowser
import urllib.request
from pathlib import Path
from datetime import datetime

# 路径
if getattr(sys, 'frozen', False):
    APP_DIR = Path(os.path.dirname(sys.executable))
else:
    APP_DIR = Path(__file__).parent

DATA_DIR = Path(os.environ.get('APPDATA', '~')) / 'LanhuMCP'
DATA_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = DATA_DIR / '.env'
COOKIE_FILE = DATA_DIR / 'cookie.txt'

LANHU_URL = "https://lanhuapp.com/web/"


# ============================================
# 工具函数
# ============================================

def find_server_exe():
    """查找server可执行文件"""
    candidates = [
        APP_DIR / 'lanhu_mcp.exe',
        APP_DIR / 'dist' / 'lanhu_mcp' / 'lanhu_mcp.exe',
        APP_DIR / 'lanhu_mcp_server.py',
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def load_cookie():
    if COOKIE_FILE.exists():
        return COOKIE_FILE.read_text(encoding='utf-8').strip()
    if ENV_FILE.exists():
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('LANHU_COOKIE='):
                    return line.split('=', 1)[1].strip().strip('"')
    return ''


def save_cookie(cookie):
    COOKIE_FILE.write_text(cookie, encoding='utf-8')
    # 同时写入.env
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
        env_content += f'\nLANHU_COOKIE={cookie}\n'
    ENV_FILE.write_text(env_content, encoding='utf-8')


# ============================================
# AI IDE 检测与配置
# ============================================

IDE_REGISTRY = {
    'Cursor': {
        'check_paths': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Cursor' / 'Cursor.exe',
            Path(os.environ.get('PROGRAMFILES', '')) / 'Cursor' / 'Cursor.exe',
            Path(os.environ.get('PROGRAMFILES(X86)', '')) / 'Cursor' / 'Cursor.exe',
        ],
        'config_paths': [
            Path(os.environ.get('APPDATA', '')) / 'Cursor' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        ],
        'mcp_type': 'sse',
    },
    'Windsurf': {
        'check_paths': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Windsurf' / 'Windsurf.exe',
            Path(os.environ.get('PROGRAMFILES', '')) / 'Windsurf' / 'Windsurf.exe',
        ],
        'config_paths': [
            Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        ],
        'mcp_type': 'sse',
    },
    'Claude Desktop': {
        'check_paths': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Claude' / 'Claude.exe',
            Path(os.environ.get('PROGRAMFILES', '')) / 'Claude' / 'Claude.exe',
        ],
        'config_paths': [
            Path(os.environ.get('APPDATA', '')) / 'Claude' / 'claude_desktop_config.json',
        ],
        'mcp_type': 'sse',
    },
    'VS Code + Cline': {
        'check_paths': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Microsoft VS Code' / 'Code.exe',
            Path(os.environ.get('PROGRAMFILES', '')) / 'Microsoft VS Code' / 'Code.exe',
        ],
        'config_paths': [
            Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        ],
        'mcp_type': 'sse',
    },
    'Trae': {
        'check_paths': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Trae' / 'Trae.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Trae' / 'Trae.exe',
        ],
        'config_paths': [
            Path(os.environ.get('APPDATA', '')) / 'Trae' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        ],
        'mcp_type': 'sse',
    },
    'Cherry Studio': {
        'check_paths': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'cherry-studio' / 'Cherry Studio.exe',
            Path(os.environ.get('APPDATA', '')) / 'cherry-studio' / 'Cherry Studio.exe',
        ],
        'config_paths': [
            Path(os.environ.get('APPDATA', '')) / 'cherry-studio' / 'mcp.json',
        ],
        'mcp_type': 'sse',
    },
    'ChatBox': {
        'check_paths': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'chatbox' / 'Chatbox.exe',
            Path(os.environ.get('PROGRAMFILES', '')) / 'Chatbox' / 'Chatbox.exe',
        ],
        'config_paths': [
            Path(os.environ.get('APPDATA', '')) / 'chatbox' / 'config.json',
        ],
        'mcp_type': 'sse',
    },
    'Continue': {
        'check_paths': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Microsoft VS Code' / 'Code.exe',
        ],
        'config_paths': [
            Path.home() / '.continue' / 'config.yaml',
        ],
        'mcp_type': 'sse',
    },
    'Cline (OpenCode)': {
        'check_paths': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'opencode' / 'OpenCode.exe',
        ],
        'config_paths': [
            Path(os.environ.get('APPDATA', '')) / 'opencode' / 'mcp.json',
        ],
        'mcp_type': 'sse',
    },
}


class IDEManager:
    @staticmethod
    def detect_all():
        """检测所有已安装的IDE"""
        results = {}
        for ide_name, ide_info in IDE_REGISTRY.items():
            installed = False
            exe_path = None
            for p in ide_info['check_paths']:
                if p.exists():
                    installed = True
                    exe_path = p
                    break
            results[ide_name] = {
                'installed': installed,
                'exe': str(exe_path) if exe_path else None,
                'config': ide_info['config_paths'][0] if ide_info['config_paths'] else None,
            }
        return results

    @staticmethod
    def configure(ide_name, port=8000):
        """配置IDE的MCP"""
        if ide_name not in IDE_REGISTRY:
            return False, "未知IDE"

        ide_info = IDE_REGISTRY[ide_name]
        config_path = None
        for p in ide_info['config_paths']:
            if p.parent.exists():
                config_path = p
                break

        if not config_path:
            return False, f"{ide_name} 配置目录不存在"

        # 读取现有配置
        config = {}
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        config = json.loads(content)
            except Exception:
                config = {}

        # 根据IDE类型写入不同格式
        if ide_name == 'Claude Desktop':
            if 'mcpServers' not in config:
                config['mcpServers'] = {}
            config['mcpServers']['lanhu'] = {
                'url': f'http://localhost:{port}/mcp',
            }
        elif ide_name == 'Continue':
            # YAML格式，单独处理
            return IDEManager._configure_continue(ide_name, port)
        else:
            if 'mcpServers' not in config:
                config['mcpServers'] = {}
            config['mcpServers']['lanhu'] = {
                'url': f'http://localhost:{port}/mcp',
                'disabled': False,
            }

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        return True, f"已配置 {ide_name}"

    @staticmethod
    def _configure_continue(ide_name, port):
        config_path = Path.home() / '.continue' / 'config.yaml'
        if not config_path.parent.exists():
            return False, "Continue 配置目录不存在"

        content = ''
        if config_path.exists():
            content = config_path.read_text(encoding='utf-8')

        # 简单的MCP配置追加
        mcp_block = f'''
mcpServers:
  - name: lanhu
    type: sse
    url: http://localhost:{port}/mcp
'''
        if 'mcpServers' not in content:
            content += mcp_block
            config_path.write_text(content, encoding='utf-8')

        return True, f"已配置 {ide_name}"

    @staticmethod
    def configure_all(port=8000):
        results = []
        detected = IDEManager.detect_all()
        for ide_name, info in detected.items():
            if info['installed']:
                ok, msg = IDEManager.configure(ide_name, port)
                results.append((ide_name, ok, msg))
        return results


# ============================================
# 服务管理（子进程模式）
# ============================================

class ServiceManager:
    _process = None
    _running = False
    _port = 8000

    @staticmethod
    def is_running():
        return ServiceManager._running and ServiceManager._process is not None

    @staticmethod
    def start(port=8000, on_log=None):
        if ServiceManager.is_running():
            return False, "服务已在运行"

        if is_port_in_use(port):
            return False, f"端口 {port} 已被占用"

        server_exe = find_server_exe()
        if not server_exe:
            return False, "未找到服务端程序"

        ServiceManager._port = port

        # 准备环境变量
        env = os.environ.copy()
        if ENV_FILE.exists():
            with open(ENV_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        env[k.strip()] = v.strip().strip('"')

        env['SERVER_PORT'] = str(port)
        env['MCP_TRANSPORT'] = 'http'

        try:
            if server_exe.suffix == '.py':
                cmd = [sys.executable, str(server_exe)]
            else:
                cmd = [str(server_exe)]

            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW

            ServiceManager._process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            ServiceManager._running = True

            # 监控输出
            def monitor():
                try:
                    for line in ServiceManager._process.stdout:
                        if on_log:
                            on_log(line.decode('utf-8', errors='replace').strip())
                except Exception:
                    pass
                ServiceManager._running = False

            threading.Thread(target=monitor, daemon=True).start()

            # 等待启动
            for _ in range(10):
                time.sleep(0.5)
                if is_port_in_use(port):
                    return True, "服务已启动"

            if ServiceManager._process.poll() is not None:
                ServiceManager._running = False
                return False, "服务启动失败（进程已退出）"

            return True, "服务已启动"

        except Exception as e:
            ServiceManager._running = False
            return False, f"启动失败: {e}"

    @staticmethod
    def stop():
        if ServiceManager._process:
            try:
                ServiceManager._process.terminate()
                ServiceManager._process.wait(timeout=5)
            except Exception:
                ServiceManager._process.kill()
            ServiceManager._process = None
            ServiceManager._running = False
            return True, "服务已停止"
        return False, "服务未运行"


# ============================================
# 浏览器Cookie获取
# ============================================

def fetch_cookie_async(callback):
    """用浏览器打开蓝湖，等待用户登录后自动获取Cookie"""
    def _worker():
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    args=['--start-maximized']
                )
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 800}
                )
                page = context.new_page()
                page.goto(LANHU_URL)

                # 等待登录成功
                cookie_str = ''
                for _ in range(300):  # 5分钟
                    time.sleep(1)
                    try:
                        cookies = context.cookies()
                        relevant = [c for c in cookies if 'lanhuapp' in c.get('domain', '')]
                        if relevant:
                            cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in relevant])
                            if len(cookie_str) > 50:
                                break
                    except Exception:
                        pass

                browser.close()

                if cookie_str:
                    callback(cookie_str)
                else:
                    callback(None)

        except ImportError:
            callback(None, "需要安装playwright: pip install playwright")
        except Exception as e:
            callback(None, str(e))

    threading.Thread(target=_worker, daemon=True).start()


# ============================================
# GUI
# ============================================

def create_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox, scrolledtext
    except ImportError:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "需要安装 tkinter", "错误", 0)
        return

    root = tk.Tk()
    root.title("Lanhu MCP Server - 管理面板")
    root.geometry("900x700")
    root.minsize(800, 600)

    # ---- 变量 ----
    port_var = tk.StringVar(value="8000")
    cookie_var = tk.StringVar()

    # ---- 主框架 ----
    main = ttk.Frame(root, padding="15")
    main.pack(fill=tk.BOTH, expand=True)

    # ---- 标题 ----
    ttk.Label(main, text="🎨 Lanhu MCP Server", font=('Microsoft YaHei UI', 22, 'bold')).pack(anchor='w')
    ttk.Label(main, text="让所有AI助手都能读取蓝湖设计稿", foreground='gray').pack(anchor='w', pady=(0, 15))

    # ---- 服务状态 ----
    sf = ttk.LabelFrame(main, text=" 服务状态 ", padding=12)
    sf.pack(fill=tk.X, pady=(0, 10))

    row1 = ttk.Frame(sf)
    row1.pack(fill=tk.X)

    status_lbl = ttk.Label(row1, text="● 未运行", foreground='red', font=('Microsoft YaHei UI', 11, 'bold'))
    status_lbl.pack(side=tk.LEFT)

    ttk.Label(row1, text="端口:").pack(side=tk.LEFT, padx=(20, 5))
    ttk.Entry(row1, textvariable=port_var, width=8).pack(side=tk.LEFT)

    start_btn = ttk.Button(row1, text="▶ 启动服务")
    start_btn.pack(side=tk.LEFT, padx=(20, 5))
    stop_btn = ttk.Button(row1, text="■ 停止服务", state=tk.DISABLED)
    stop_btn.pack(side=tk.LEFT)

    def open_mcp():
        webbrowser.open(f"http://localhost:{port_var.get()}/mcp")

    ttk.Button(row1, text="🔗 打开MCP", command=open_mcp).pack(side=tk.LEFT, padx=(15, 0))

    # ---- 日志区（服务输出）----
    log_sf = ttk.LabelFrame(main, text=" 服务日志 ", padding=8)
    log_sf.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    log_text = scrolledtext.ScrolledText(log_sf, height=6, font=('Consolas', 9), state=tk.DISABLED)
    log_text.pack(fill=tk.BOTH, expand=True)

    def log(msg):
        ts = datetime.now().strftime("%H:%M:%S")
        log_text.config(state=tk.NORMAL)
        log_text.insert(tk.END, f"[{ts}] {msg}\n")
        log_text.see(tk.END)
        log_text.config(state=tk.DISABLED)

    def on_server_log(line):
        root.after(0, lambda: log(f"[server] {line}"))

    # ---- 启动/停止 ----
    def do_start():
        try:
            port = int(port_var.get())
        except ValueError:
            messagebox.showerror("错误", "端口必须是数字")
            return

        start_btn.config(state=tk.DISABLED)
        status_lbl.config(text="● 启动中...", foreground='orange')
        root.update()

        def _start():
            ok, msg = ServiceManager.start(port, on_server_log)
            root.after(0, lambda: _on_start_result(ok, msg, port))

        threading.Thread(target=_start, daemon=True).start()

    def _on_start_result(ok, msg, port):
        if ok:
            status_lbl.config(text="● 运行中", foreground='green')
            stop_btn.config(state=tk.NORMAL)
            log(f"✅ 服务已启动 http://localhost:{port}/mcp")
        else:
            status_lbl.config(text="● 启动失败", foreground='red')
            start_btn.config(state=tk.NORMAL)
            log(f"❌ {msg}")
            messagebox.showerror("启动失败", msg)

    def do_stop():
        ok, msg = ServiceManager.stop()
        status_lbl.config(text="● 未运行", foreground='red')
        start_btn.config(state=tk.NORMAL)
        stop_btn.config(state=tk.DISABLED)
        log(f"⏹ {msg}")

    start_btn.config(command=do_start)
    stop_btn.config(command=do_stop)

    # ---- 蓝湖登录 ----
    cf = ttk.LabelFrame(main, text=" 蓝湖登录 ", padding=12)
    cf.pack(fill=tk.X, pady=(0, 10))

    row2 = ttk.Frame(cf)
    row2.pack(fill=tk.X)

    ttk.Label(row2, text="Cookie:").pack(side=tk.LEFT)

    saved = load_cookie()
    cookie_var.set(saved[:70] + "..." if len(saved) > 70 else saved)
    ttk.Entry(row2, textvariable=cookie_var, width=60).pack(side=tk.LEFT, padx=(5, 10), fill=tk.X, expand=True)

    def do_auto_login():
        log("🌐 正在打开浏览器，请登录蓝湖...")
        log("登录成功后将自动获取Cookie...")

        def on_cookie(cookie, err=None):
            if cookie:
                save_cookie(cookie)
                cookie_var.set(cookie[:70] + "..." if len(cookie) > 70 else cookie)
                root.after(0, lambda: log(f"✅ Cookie获取成功！"))
            else:
                root.after(0, lambda: log(f"❌ 获取失败: {err or '未获取到Cookie'}"))

        fetch_cookie_async(on_cookie)

    def do_manual_login():
        webbrowser.open(LANHU_URL)

    def do_save_cookie():
        c = cookie_var.get()
        if '...' in c:
            c = load_cookie()
        save_cookie(c)
        log("✅ Cookie已保存")
        messagebox.showinfo("成功", "Cookie已保存")

    ttk.Button(row2, text="🌐 一键登录", command=do_auto_login).pack(side=tk.LEFT)
    ttk.Button(row2, text="📋 手动打开", command=do_manual_login).pack(side=tk.LEFT, padx=(5, 0))
    ttk.Button(row2, text="💾 保存", command=do_save_cookie).pack(side=tk.LEFT, padx=(5, 0))

    # ---- AI IDE 配置 ----
    ide_f = ttk.LabelFrame(main, text=" AI IDE 配置（自动检测已安装） ", padding=12)
    ide_f.pack(fill=tk.X, pady=(0, 10))

    ide_grid = ttk.Frame(ide_f)
    ide_grid.pack(fill=tk.X)

    detected_ides = IDEManager.detect_all()

    ide_widgets = {}

    def refresh_ides():
        nonlocal detected_ides
        detected_ides = IDEManager.detect_all()
        for w in ide_grid.winfo_children():
            w.destroy()

        col = 0
        row = 0
        for ide_name, info in detected_ides.items():
            if col >= 3:
                col = 0
                row += 1

            cell = ttk.Frame(ide_grid)
            cell.grid(row=row, column=col, sticky='w', padx=(0, 20), pady=3)

            if info['installed']:
                lbl = ttk.Label(cell, text=f"✅ {ide_name}", foreground='green')
                lbl.pack(side=tk.LEFT)

                def make_cfg(ide=ide_name):
                    ok, msg = IDEManager.configure(ide, int(port_var.get()))
                    if ok:
                        log(f"✅ {msg}")
                    else:
                        messagebox.showwarning("提示", msg)

                ttk.Button(cell, text="配置", command=make_cfg, width=5).pack(side=tk.LEFT, padx=(5, 0))
            else:
                ttk.Label(cell, text=f"⬜ {ide_name}", foreground='gray').pack(side=tk.LEFT)

            col += 1

    refresh_ides()

    def do_config_all():
        port = int(port_var.get())
        results = IDEManager.configure_all(port)
        msgs = []
        for name, ok, msg in results:
            status = "✅" if ok else "❌"
            msgs.append(f"{status} {name}: {msg}")
            log(f"{status} {name}: {msg}")
        if msgs:
            messagebox.showinfo("配置结果", "\n".join(msgs))
        else:
            messagebox.showinfo("提示", "未检测到已安装的AI IDE")

    btn_row = ttk.Frame(ide_f)
    btn_row.pack(fill=tk.X, pady=(8, 0))
    ttk.Button(btn_row, text="🚀 一键配置所有已安装的IDE", command=do_config_all).pack(side=tk.LEFT)
    ttk.Button(btn_row, text="🔄 重新检测", command=refresh_ides).pack(side=tk.LEFT, padx=(10, 0))

    # ---- MCP 配置代码 ----
    mcp_f = ttk.LabelFrame(main, text=" MCP 配置代码（手动配置时使用） ", padding=12)
    mcp_f.pack(fill=tk.X, pady=(0, 10))

    mcp_code = scrolledtext.ScrolledText(mcp_f, height=5, font=('Consolas', 9))
    mcp_code.pack(fill=tk.X)
    mcp_code.insert(tk.END, '{\n  "mcpServers": {\n    "lanhu": {\n      "url": "http://localhost:8000/mcp"\n    }\n  }\n}')
    mcp_code.config(state=tk.DISABLED)

    def copy_code():
        root.clipboard_clear()
        root.clipboard_append('{\n  "mcpServers": {\n    "lanhu": {\n      "url": "http://localhost:8000/mcp"\n    }\n  }\n}')
        log("📋 配置代码已复制到剪贴板")

    ttk.Button(mcp_f, text="📋 复制配置代码", command=copy_code).pack(pady=(5, 0))

    # ---- 初始化 ----
    log("Lanhu MCP Server 管理面板已启动")
    log(f"配置目录: {DATA_DIR}")
    if saved:
        log(f"Cookie: 已配置")
    else:
        log("Cookie: 未配置 - 点击「一键登录」获取")
    log(f"检测到 {sum(1 for v in detected_ides.values() if v['installed'])} 个已安装的AI IDE")

    # ---- 关闭处理 ----
    def on_close():
        if ServiceManager.is_running():
            ServiceManager.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    root.mainloop()


if __name__ == '__main__':
    create_gui()
