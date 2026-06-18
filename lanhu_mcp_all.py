"""
Lanhu MCP Server - 单文件版本（GUI + Server 合并）

一个exe同时包含管理界面和服务端。
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
# 服务端（内嵌）
# ============================================

class EmbeddedServer:
    """内嵌MCP服务端"""

    _thread = None
    _running = False
    _port = 8000
    _error = None
    _on_log = None
    _stop_event = threading.Event()

    @staticmethod
    def is_running():
        return EmbeddedServer._running

    @staticmethod
    def start(port=8000, on_log=None):
        if EmbeddedServer._running:
            return False, "服务已在运行"
        if is_port_in_use(port):
            return False, f"端口 {port} 已被占用"

        EmbeddedServer._port = port
        EmbeddedServer._on_log = on_log
        EmbeddedServer._error = None
        EmbeddedServer._stop_event.clear()

        def run():
            try:
                # 加载环境变量
                if ENV_FILE.exists():
                    with open(ENV_FILE, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                k, v = line.split('=', 1)
                                os.environ[k.strip()] = v.strip().strip('"')

                os.environ['SERVER_PORT'] = str(port)
                os.environ['MCP_TRANSPORT'] = 'http'

                if on_log:
                    on_log("正在导入服务端模块...")

                from lanhu_mcp_server import mcp

                if on_log:
                    on_log(f"服务端模块加载成功，启动HTTP服务 端口={port}")

                EmbeddedServer._running = True
                mcp.run(transport="http", path="/mcp", host="0.0.0.0", port=port)

            except Exception as e:
                EmbeddedServer._error = str(e)
                if on_log:
                    on_log(f"错误: {e}")
                    on_log(traceback.format_exc())
            finally:
                EmbeddedServer._running = False

        EmbeddedServer._thread = threading.Thread(target=run, daemon=True)
        EmbeddedServer._thread.start()

        # 等待启动
        for _ in range(30):
            time.sleep(0.5)
            if EmbeddedServer._running and is_port_in_use(port):
                return True, "服务已启动"
            if EmbeddedServer._error:
                return False, f"启动失败: {EmbeddedServer._error}"

        if not EmbeddedServer._running and EmbeddedServer._error:
            return False, f"启动失败: {EmbeddedServer._error}"

        return True, "服务启动中..."

    @staticmethod
    def stop():
        EmbeddedServer._stop_event.set()
        EmbeddedServer._running = False
        return True, "服务已停止"


# ============================================
# AI IDE 检测
# ============================================

IDE_REGISTRY = {
    'Cursor': {
        'exe': [Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Cursor' / 'Cursor.exe'],
        'config': [Path(os.environ.get('APPDATA', '')) / 'Cursor' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json'],
    },
    'Windsurf': {
        'exe': [Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Windsurf' / 'Windsurf.exe'],
        'config': [Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json'],
    },
    'Claude Desktop': {
        'exe': [Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Claude' / 'Claude.exe'],
        'config': [Path(os.environ.get('APPDATA', '')) / 'Claude' / 'claude_desktop_config.json'],
    },
    'VS Code + Cline': {
        'exe': [Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Microsoft VS Code' / 'Code.exe'],
        'config': [Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json'],
    },
    'Trae': {
        'exe': [Path(os.environ.get('LOCALAPPDATA', '')) / 'Trae' / 'Trae.exe', Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Trae' / 'Trae.exe'],
        'config': [Path(os.environ.get('APPDATA', '')) / 'Trae' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json'],
    },
    'Cherry Studio': {
        'exe': [Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'cherry-studio' / 'Cherry Studio.exe'],
        'config': [Path(os.environ.get('APPDATA', '')) / 'cherry-studio' / 'mcp.json'],
    },
    'ChatBox': {
        'exe': [Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'chatbox' / 'Chatbox.exe'],
        'config': [Path(os.environ.get('APPDATA', '')) / 'chatbox' / 'config.json'],
    },
    'Continue': {
        'exe': [Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Microsoft VS Code' / 'Code.exe'],
        'config': [Path.home() / '.continue' / 'config.yaml'],
    },
    'Junie (JetBrains)': {
        'exe': [Path(os.environ.get('LOCALAPPDATA', '')) / 'JetBrains' / 'Toolbox' / 'apps' / 'Junie' / 'ch-0' / 'Junie.exe'],
        'config': [Path(os.environ.get('APPDATA', '')) / 'JetBrains' / 'Junie' / 'mcp.json'],
    },
}


class IDEManager:
    @staticmethod
    def detect_all():
        results = {}
        for name, info in IDE_REGISTRY.items():
            installed = any(p.exists() for p in info['exe'])
            results[name] = installed
        return results

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
                        config = json.loads(content)
            except Exception:
                config = {}

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
    def configure_all(port=8000):
        results = []
        detected = IDEManager.detect_all()
        for name, installed in detected.items():
            if installed:
                ok, msg = IDEManager.configure(name, port)
                results.append((name, ok, msg))
        return results


# ============================================
# GUI
# ============================================

def create_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox, scrolledtext
    except ImportError:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "需要 tkinter（Python标准库）", "错误", 0)
        return

    root = tk.Tk()
    root.title("Lanhu MCP Server - 管理面板")
    root.geometry("920x750")
    root.minsize(820, 650)

    port_var = tk.StringVar(value="8000")
    cookie_var = tk.StringVar()

    main = ttk.Frame(root, padding="15")
    main.pack(fill=tk.BOTH, expand=True)

    # ---- 标题 ----
    ttk.Label(main, text="🎨 Lanhu MCP Server", font=('Microsoft YaHei UI', 22, 'bold')).pack(anchor='w')
    ttk.Label(main, text="让所有AI助手都能读取蓝湖设计稿 | 单文件版", foreground='gray').pack(anchor='w', pady=(0, 15))

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
    ttk.Button(row1, text="🔗 打开MCP", command=lambda: webbrowser.open(f"http://localhost:{port_var.get()}/mcp")).pack(side=tk.LEFT, padx=(15, 0))

    # ---- 日志 ----
    log_sf = ttk.LabelFrame(main, text=" 运行日志 ", padding=8)
    log_sf.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    log_text = scrolledtext.ScrolledText(log_sf, height=10, font=('Consolas', 9), state=tk.DISABLED)
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
        stop_btn.config(state=tk.DISABLED)
        status_lbl.config(text="● 启动中...", foreground='orange')
        root.update()

        def _start():
            ok, msg = EmbeddedServer.start(port, on_server_log)
            root.after(0, lambda: _on_result(ok, msg))

        threading.Thread(target=_start, daemon=True).start()

    def _on_result(ok, msg):
        if ok:
            status_lbl.config(text="● 运行中", foreground='green')
            start_btn.config(state=tk.DISABLED)
            stop_btn.config(state=tk.NORMAL)
            log(f"✅ {msg}  http://localhost:{port_var.get()}/mcp")
        else:
            status_lbl.config(text="● 启动失败", foreground='red')
            start_btn.config(state=tk.NORMAL)
            stop_btn.config(state=tk.DISABLED)
            log(f"❌ {msg}")
            messagebox.showerror("启动失败", msg)

    def do_stop():
        EmbeddedServer.stop()
        status_lbl.config(text="● 已停止", foreground='gray')
        start_btn.config(state=tk.NORMAL)
        stop_btn.config(state=tk.DISABLED)
        log("⏹ 服务已停止")

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
    ttk.Entry(row2, textvariable=cookie_var, width=55).pack(side=tk.LEFT, padx=(5, 10), fill=tk.X, expand=True)

    def do_open_lanhu():
        # 尝试用Chrome打开
        chrome = Path(os.environ.get('LOCALAPPDATA', '')) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe'
        if not chrome.exists():
            chrome = Path(os.environ.get('PROGRAMFILES', '')) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe'
        if chrome.exists():
            subprocess.Popen([str(chrome), LANHU_URL])
        else:
            webbrowser.open(LANHU_URL)
        log("🌐 已打开蓝湖登录页面")

    def do_save_cookie():
        c = cookie_var.get()
        if '...' in c:
            c = load_cookie()
        save_cookie(c)
        log(f"✅ Cookie已保存 ({len(c)} 字符)")

    ttk.Button(row2, text="🌐 打开蓝湖登录", command=do_open_lanhu).pack(side=tk.LEFT)
    ttk.Button(row2, text="💾 保存Cookie", command=do_save_cookie).pack(side=tk.LEFT, padx=(5, 0))

    ttk.Label(cf, text="登录后按F12→Application→Cookies→复制lanhuapp.com的Cookie粘贴到上方", foreground='gray', font=('Microsoft YaHei UI', 8)).pack(anchor='w', pady=(5, 0))

    # ---- AI IDE ----
    ide_f = ttk.LabelFrame(main, text=" AI IDE 配置（自动检测已安装） ", padding=12)
    ide_f.pack(fill=tk.X, pady=(0, 10))

    ide_grid = ttk.Frame(ide_f)
    ide_grid.pack(fill=tk.X)

    def refresh_ides():
        for w in ide_grid.winfo_children():
            w.destroy()
        detected = IDEManager.detect_all()
        col, row = 0, 0
        for name, installed in detected.items():
            if col >= 4:
                col = 0
                row += 1
            cell = ttk.Frame(ide_grid)
            cell.grid(row=row, column=col, sticky='w', padx=(0, 15), pady=3)
            if installed:
                ttk.Label(cell, text=f"✅ {name}", foreground='green').pack(side=tk.LEFT)
                def make_cfg(ide=name):
                    ok, msg = IDEManager.configure(ide, int(port_var.get()))
                    if ok:
                        log(f"✅ {msg}")
                    else:
                        messagebox.showwarning("提示", msg)
                ttk.Button(cell, text="配置", command=make_cfg, width=5).pack(side=tk.LEFT, padx=(5, 0))
            else:
                ttk.Label(cell, text=f"⬜ {name}", foreground='gray').pack(side=tk.LEFT)
            col += 1

    refresh_ides()

    btn_row = ttk.Frame(ide_f)
    btn_row.pack(fill=tk.X, pady=(8, 0))
    ttk.Button(btn_row, text="🚀 一键配置所有已安装的IDE", command=lambda: _config_all()).pack(side=tk.LEFT)
    ttk.Button(btn_row, text="🔄 重新检测", command=refresh_ides).pack(side=tk.LEFT, padx=(10, 0))

    def _config_all():
        port = int(port_var.get())
        results = IDEManager.configure_all(port)
        msgs = [f"{'✅' if ok else '❌'} {n}: {m}" for n, ok, m in results]
        for m in msgs:
            log(m)
        if msgs:
            messagebox.showinfo("配置结果", "\n".join(msgs))
        else:
            messagebox.showinfo("提示", "未检测到已安装的AI IDE")

    # ---- MCP配置 ----
    mcp_f = ttk.LabelFrame(main, text=" MCP 配置代码（手动配置时复制） ", padding=12)
    mcp_f.pack(fill=tk.X, pady=(0, 5))

    mcp_code = scrolledtext.ScrolledText(mcp_f, height=4, font=('Consolas', 9))
    mcp_code.pack(fill=tk.X)
    mcp_code.insert(tk.END, '{\n  "mcpServers": {\n    "lanhu": {\n      "url": "http://localhost:8000/mcp"\n    }\n  }\n}')
    mcp_code.config(state=tk.DISABLED)

    def copy_code():
        root.clipboard_clear()
        root.clipboard_append('{\n  "mcpServers": {\n    "lanhu": {\n      "url": "http://localhost:8000/mcp"\n    }\n  }\n}')
        log("📋 配置代码已复制")

    ttk.Button(mcp_f, text="📋 复制配置代码", command=copy_code).pack(pady=(5, 0))

    # ---- 初始化 ----
    log("Lanhu MCP Server 已启动（单文件版，内嵌服务端）")
    log(f"配置目录: {DATA_DIR}")
    if saved:
        log(f"Cookie: 已配置")
    else:
        log("Cookie: 未配置")
    count = sum(1 for v in IDEManager.detect_all().values() if v)
    log(f"检测到 {count} 个已安装的AI IDE")
    log("点击「启动服务」开始使用")

    def on_close():
        if EmbeddedServer.is_running():
            EmbeddedServer.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == '__main__':
    create_gui()
