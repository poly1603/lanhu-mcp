"""
Lanhu MCP Server - 可视化管理界面

功能：
- 一键启动/停止服务
- 一键登录蓝湖（Cookie配置）
- 自动检测并配置 AI IDE（Cursor/Windsurf/Claude Desktop等）
- 状态监控
"""
import os
import sys
import json
import threading
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime

# 获取应用目录
if getattr(sys, 'frozen', False):
    APP_DIR = Path(os.path.dirname(sys.executable))
    RESOURCES_DIR = Path(sys._MEIPASS)
else:
    APP_DIR = Path(__file__).parent
    RESOURCES_DIR = APP_DIR

DATA_DIR = Path(os.environ.get('APPDATA', '~')) / 'LanhuMCP'
DATA_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = DATA_DIR / '.env'

# AI IDE 配置路径
IDE_CONFIGS = {
    'Cursor': {
        'path': Path(os.environ.get('APPDATA', '')) / 'Cursor' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        'alt_path': Path(os.environ.get('LOCALAPPDATA', '')) / 'Cursor' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        'type': 'json',
    },
    'Windsurf': {
        'path': Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        'alt_path': Path(os.environ.get('LOCALAPPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        'type': 'json',
    },
    'Claude Desktop': {
        'path': Path(os.environ.get('APPDATA', '')) / 'Claude' / 'claude_desktop_config.json',
        'type': 'json',
    },
    'Cline': {
        'path': Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        'alt_path': Path(os.environ.get('LOCALAPPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        'type': 'json',
    },
}

# 蓝湖登录URL
LANHU_LOGIN_URL = "https://lanhuapp.com/web/"


class ConfigManager:
    """配置管理"""

    @staticmethod
    def load():
        config = {}
        if ENV_FILE.exists():
            with open(ENV_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip().strip('"').strip("'")
        return config

    @staticmethod
    def save(config):
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            for key, value in config.items():
                f.write(f'{key}={value}\n')

    @staticmethod
    def get_cookie():
        config = ConfigManager.load()
        return config.get('LANHU_COOKIE', '')

    @staticmethod
    def set_cookie(cookie):
        config = ConfigManager.load()
        config['LANHU_COOKIE'] = cookie
        ConfigManager.save(config)


class IDEManager:
    """AI IDE 配置管理"""

    @staticmethod
    def detect_installed():
        """检测已安装的AI IDE"""
        installed = {}
        for ide_name, ide_info in IDE_CONFIGS.items():
            path = ide_info['path']
            alt_path = ide_info.get('alt_path')
            if path.exists() or (alt_path and alt_path.exists()):
                installed[ide_name] = path if path.exists() else alt_path
        return installed

    @staticmethod
    def configure_ide(ide_name, port=8000):
        """配置AI IDE的MCP设置"""
        if ide_name not in IDE_CONFIGS:
            return False, f"未知的IDE: {ide_name}"

        ide_info = IDE_CONFIGS[ide_name]
        config_path = ide_info['path']
        if not config_path.exists() and ide_info.get('alt_path'):
            config_path = ide_info['alt_path']

        if not config_path.exists():
            return False, f"配置文件不存在: {config_path}"

        try:
            # 读取现有配置
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            config = {}

        # 确保 mcpServers 结构存在
        if 'mcpServers' not in config:
            config['mcpServers'] = {}

        # 添加/更新 Lanhu MCP 配置
        config['mcpServers']['lanhu'] = {
            'url': f'http://localhost:{port}/mcp',
            'disabled': False,
        }

        # 保存配置
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        return True, f"已配置 {ide_name}"

    @staticmethod
    def get_config_status():
        """获取所有IDE的配置状态"""
        status = {}
        installed = IDEManager.detect_installed()

        for ide_name in IDE_CONFIGS:
            if ide_name in installed:
                try:
                    with open(installed[ide_name], 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    has_lanhu = 'lanhu' in config.get('mcpServers', {})
                    status[ide_name] = {
                        'installed': True,
                        'configured': has_lanhu,
                        'path': str(installed[ide_name]),
                    }
                except Exception:
                    status[ide_name] = {
                        'installed': True,
                        'configured': False,
                        'path': str(installed[ide_name]),
                    }
            else:
                status[ide_name] = {
                    'installed': False,
                    'configured': False,
                }

        return status


class ServiceManager:
    """服务管理"""

    _process = None
    _running = False

    @staticmethod
    def is_running():
        return ServiceManager._running and ServiceManager._process is not None

    @staticmethod
    def start(port=8000, callback=None):
        if ServiceManager.is_running():
            return False, "服务已在运行"

        # 加载环境变量
        env = os.environ.copy()
        if ENV_FILE.exists():
            with open(ENV_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env[key.strip()] = value.strip().strip('"').strip("'")

        env['SERVER_PORT'] = str(port)
        env['MCP_TRANSPORT'] = 'http'

        # 启动服务
        if getattr(sys, 'frozen', False):
            exe_path = str(APP_DIR / 'lanhu_mcp.exe')
            cmd = [exe_path]
        else:
            cmd = [sys.executable, str(APP_DIR / 'lanhu_mcp_app.py')]

        try:
            ServiceManager._process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            )
            ServiceManager._running = True

            # 启动监控线程
            def monitor():
                ServiceManager._process.wait()
                ServiceManager._running = False
                if callback:
                    callback()

            threading.Thread(target=monitor, daemon=True).start()
            return True, "服务已启动"
        except Exception as e:
            return False, f"启动失败: {str(e)}"

    @staticmethod
    def stop():
        if ServiceManager._process:
            ServiceManager._process.terminate()
            ServiceManager._process = None
            ServiceManager._running = False
            return True, "服务已停止"
        return False, "服务未运行"

    @staticmethod
    def get_status():
        return {
            'running': ServiceManager.is_running(),
            'pid': ServiceManager._process.pid if ServiceManager._process else None,
        }


# ============================================
# GUI 界面（使用 tkinter）
# ============================================

def create_gui():
    """创建主界面"""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox, scrolledtext
    except ImportError:
        print("错误: 需要安装 tkinter (Python标准库自带)")
        return

    root = tk.Tk()
    root.title("Lanhu MCP Server - 管理面板")
    root.geometry("800x600")
    root.resizable(True, True)

    # 设置样式
    style = ttk.Style()
    style.theme_use('clam')

    # 主框架
    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # ========== 顶部标题 ==========
    title_frame = ttk.Frame(main_frame)
    title_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(title_frame, text="🎨 Lanhu MCP Server", font=('Helvetica', 18, 'bold')).pack(side=tk.LEFT)
    ttk.Label(title_frame, text="v2.0.0", font=('Helvetica', 10)).pack(side=tk.LEFT, padx=(10, 0))

    # ========== 状态栏 ==========
    status_frame = ttk.LabelFrame(main_frame, text="服务状态", padding="10")
    status_frame.pack(fill=tk.X, pady=(0, 10))

    status_inner = ttk.Frame(status_frame)
    status_inner.pack(fill=tk.X)

    status_label = ttk.Label(status_inner, text="● 未运行", foreground='red', font=('Helvetica', 12))
    status_label.pack(side=tk.LEFT)

    port_var = tk.StringVar(value="8000")
    ttk.Label(status_inner, text="端口:").pack(side=tk.LEFT, padx=(20, 5))
    port_entry = ttk.Entry(status_inner, textvariable=port_var, width=8)
    port_entry.pack(side=tk.LEFT)

    def start_service():
        port = int(port_var.get())
        ok, msg = ServiceManager.start(port, on_service_stopped)
        if ok:
            status_label.config(text="● 运行中", foreground='green')
            start_btn.config(state=tk.DISABLED)
            stop_btn.config(state=tk.NORMAL)
            log_message(f"服务已启动 - 端口 {port}")
            log_message(f"MCP地址: http://localhost:{port}/mcp")
        else:
            messagebox.showerror("错误", msg)

    def stop_service():
        ok, msg = ServiceManager.stop()
        on_service_stopped()

    def on_service_stopped():
        status_label.config(text="● 未运行", foreground='red')
        start_btn.config(state=tk.NORMAL)
        stop_btn.config(state=tk.DISABLED)

    start_btn = ttk.Button(status_inner, text="▶ 启动服务", command=start_service)
    start_btn.pack(side=tk.LEFT, padx=(20, 5))

    stop_btn = ttk.Button(status_inner, text="■ 停止服务", command=stop_service, state=tk.DISABLED)
    stop_btn.pack(side=tk.LEFT)

    def open_mcp_url():
        port = port_var.get()
        webbrowser.open(f"http://localhost:{port}/mcp")

    ttk.Button(status_inner, text="🔗 打开MCP地址", command=open_mcp_url).pack(side=tk.LEFT, padx=(10, 0))

    # ========== Cookie配置 ==========
    cookie_frame = ttk.LabelFrame(main_frame, text="蓝湖登录", padding="10")
    cookie_frame.pack(fill=tk.X, pady=(0, 10))

    cookie_inner = ttk.Frame(cookie_frame)
    cookie_inner.pack(fill=tk.X)

    ttk.Label(cookie_inner, text="Cookie:").pack(side=tk.LEFT)

    cookie_var = tk.StringVar(value=ConfigManager.get_cookie()[:50] + "..." if len(ConfigManager.get_cookie()) > 50 else ConfigManager.get_cookie())
    cookie_entry = ttk.Entry(cookie_inner, textvariable=cookie_var, width=60)
    cookie_entry.pack(side=tk.LEFT, padx=(5, 10), fill=tk.X, expand=True)

    def open_login():
        webbrowser.open(LANHU_LOGIN_URL)
        messagebox.showinfo("提示", "请在浏览器中登录蓝湖，然后复制Cookie到上方输入框")

    def save_cookie():
        cookie = cookie_var.get()
        if "..." in cookie:
            cookie = ConfigManager.get_cookie()
        ConfigManager.set_cookie(cookie)
        messagebox.showinfo("成功", "Cookie已保存")

    ttk.Button(cookie_inner, text="🌐 登录蓝湖", command=open_login).pack(side=tk.LEFT)
    ttk.Button(cookie_inner, text="💾 保存Cookie", command=save_cookie).pack(side=tk.LEFT, padx=(5, 0))

    # ========== IDE配置 ==========
    ide_frame = ttk.LabelFrame(main_frame, text="AI IDE 配置", padding="10")
    ide_frame.pack(fill=tk.X, pady=(0, 10))

    ide_status = IDEManager.get_config_status()

    ide_inner = ttk.Frame(ide_frame)
    ide_inner.pack(fill=tk.X)

    for ide_name, status in ide_status.items():
        row = ttk.Frame(ide_inner)
        row.pack(fill=tk.X, pady=2)

        if status['installed']:
            icon = "✅" if status['configured'] else "⚠️"
            text = f"{icon} {ide_name}"
            ttk.Label(row, text=text).pack(side=tk.LEFT)

            if not status['configured']:
                def make_configure(ide=ide_name):
                    ok, msg = IDEManager.configure_ide(ide, int(port_var.get()))
                    if ok:
                        messagebox.showinfo("成功", msg)
                        refresh_ide_status()
                    else:
                        messagebox.showerror("错误", msg)

                ttk.Button(row, text="配置", command=make_configure).pack(side=tk.RIGHT)
        else:
            ttk.Label(row, text=f"❌ {ide_name} (未安装)").pack(side=tk.LEFT)

    def refresh_ide_status():
        # 刷新IDE状态显示
        pass

    # 快速配置按钮
    quick_config_frame = ttk.Frame(ide_frame)
    quick_config_frame.pack(fill=tk.X, pady=(10, 0))

    def configure_all():
        port = int(port_var.get())
        results = []
        for ide_name in IDE_CONFIGS:
            ok, msg = IDEManager.configure_ide(ide_name, port)
            results.append(f"{ide_name}: {'✅' if ok else '❌'} {msg}")
        messagebox.showinfo("配置结果", "\n".join(results))

    ttk.Button(quick_config_frame, text="🚀 一键配置所有已安装的IDE", command=configure_all).pack(side=tk.LEFT)

    # ========== 日志 ==========
    log_frame = ttk.LabelFrame(main_frame, text="运行日志", padding="10")
    log_frame.pack(fill=tk.BOTH, expand=True)

    log_text = scrolledtext.ScrolledText(log_frame, height=10, state=tk.DISABLED)
    log_text.pack(fill=tk.BOTH, expand=True)

    def log_message(msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_text.config(state=tk.NORMAL)
        log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        log_text.see(tk.END)
        log_text.config(state=tk.DISABLED)

    # ========== 底部按钮 ==========
    bottom_frame = ttk.Frame(main_frame)
    bottom_frame.pack(fill=tk.X, pady=(10, 0))

    def open_config_dir():
        os.startfile(str(DATA_DIR))

    ttk.Button(bottom_frame, text="📁 打开配置目录", command=open_config_dir).pack(side=tk.LEFT)
    ttk.Button(bottom_frame, text="📖 查看文档", command=lambda: webbrowser.open("https://github.com/dsphper/lanhu-mcp")).pack(side=tk.LEFT, padx=(10, 0))

    # 初始化日志
    log_message("Lanhu MCP Server 管理面板已启动")
    log_message(f"配置目录: {DATA_DIR}")
    if ConfigManager.get_cookie():
        log_message("Cookie: 已配置")
    else:
        log_message("Cookie: 未配置 (请先登录蓝湖)")

    # 启动界面
    root.mainloop()


def main():
    """主入口"""
    if '--gui' in sys.argv or not any(arg in sys.argv for arg in ['--setup', '--tray', '--config', '--help']):
        create_gui()
    else:
        # 原有命令行模式
        from lanhu_mcp_app import main as app_main
        app_main()


if __name__ == '__main__':
    main()
