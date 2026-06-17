"""
Lanhu MCP Server - 可执行入口

打包后的独立运行入口，支持：
- 命令行模式（默认）
- 系统托盘模式（--tray）
- 配置向导模式（--setup）
"""
import os
import sys
import json
import argparse
from pathlib import Path


def get_app_dir():
    """获取应用数据目录"""
    if sys.platform == 'win32':
        app_dir = Path(os.environ.get('APPDATA', '~')) / 'LanhuMCP'
    elif sys.platform == 'darwin':
        app_dir = Path('~/Library/Application Support/LanhuMCP').expanduser()
    else:
        app_dir = Path('~/.config/lanhu-mcp').expanduser()
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_env_path():
    """获取 .env 文件路径"""
    app_dir = get_app_dir()
    env_path = app_dir / '.env'
    # 也检查当前目录
    local_env = Path('.') / '.env'
    if local_env.exists():
        return local_env
    return env_path


def load_config():
    """加载配置"""
    env_path = get_env_path()
    config = {}
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip().strip('"').strip("'")
    return config


def save_config(config):
    """保存配置"""
    env_path = get_env_path()
    with open(env_path, 'w', encoding='utf-8') as f:
        for key, value in config.items():
            f.write(f'{key}={value}\n')
    print(f"配置已保存到: {env_path}")


def setup_wizard():
    """配置向导"""
    print("=" * 60)
    print("  Lanhu MCP Server - 配置向导")
    print("=" * 60)
    print()

    config = load_config()

    # Cookie
    print("1. 蓝湖 Cookie（必需）")
    print("   获取方式：登录蓝湖网页版 → F12开发者工具 → Application → Cookies → 复制全部")
    cookie = input(f"   当前值: {config.get('LANHU_COOKIE', '未设置')[:30]}...\n   输入新值(回车跳过): ").strip()
    if cookie:
        config['LANHU_COOKIE'] = cookie

    # DDS Cookie
    print("\n2. DDS Cookie（可选，用于设计图分析）")
    print("   获取方式：访问 dds.lanhuapp.com → F12 → Application → Cookies")
    dds_cookie = input(f"   当前值: {config.get('DDS_COOKIE', '未设置')[:30]}...\n   输入新值(回车跳过): ").strip()
    if dds_cookie:
        config['DDS_COOKIE'] = dds_cookie

    # 服务端口
    print("\n3. 服务端口")
    port = input(f"   当前值: {config.get('SERVER_PORT', '8000')}\n   输入新值(回车跳过): ").strip()
    if port:
        config['SERVER_PORT'] = port

    # 传输模式
    print("\n4. 传输模式")
    print("   http - HTTP模式（推荐，支持远程访问）")
    print("   stdio - 标准输入输出（用于MCP客户端直接调用）")
    mode = input(f"   当前值: {config.get('MCP_TRANSPORT', 'http')}\n   输入新值(回车跳过): ").strip()
    if mode:
        config['MCP_TRANSPORT'] = mode

    # 飞书Webhook
    print("\n5. 飞书机器人Webhook（可选，用于通知）")
    webhook = input(f"   当前值: {config.get('FEISHU_WEBHOOK_URL', '未设置')[:30]}...\n   输入新值(回车跳过): ").strip()
    if webhook:
        config['FEISHU_WEBHOOK_URL'] = webhook

    save_config(config)
    print()
    print("配置完成！运行以下命令启动服务：")
    print("  python lanhu_mcp_app.py")
    print("  或双击 lanhu_mcp_app.exe")


def start_server():
    """启动MCP服务器"""
    # 加载环境变量
    from dotenv import load_dotenv
    env_path = get_env_path()
    if env_path.exists():
        load_dotenv(env_path, override=False)

    # 设置工作目录为脚本所在目录
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # 导入并启动服务器
    MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "http").lower()

    if MCP_TRANSPORT == "stdio":
        from lanhu_mcp_server import mcp
        mcp.run(transport="stdio")
    else:
        SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
        SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

        print(f"""
╔══════════════════════════════════════════════════════════╗
║                   Lanhu MCP Server                      ║
╠══════════════════════════════════════════════════════════╣
║  服务地址: http://localhost:{SERVER_PORT}/mcp             ║
║  传输模式: {MCP_TRANSPORT.upper():48s}║
║  配置文件: {str(env_path)[:48]:48s}║
╠══════════════════════════════════════════════════════════╣
║  Cursor MCP 配置示例:                                    ║
║  {{                                                      ║
║    "mcpServers": {{                                       ║
║      "lanhu": {{                                          ║
║        "url": "http://localhost:{SERVER_PORT}/mcp"       ║
║      }}                                                  ║
║    }}                                                    ║
║  }}                                                      ║
╚══════════════════════════════════════════════════════════╝
""")
        print("按 Ctrl+C 停止服务...")

        from lanhu_mcp_server import mcp
        try:
            mcp.run(transport="http", path="/mcp", host=SERVER_HOST, port=SERVER_PORT)
        except KeyboardInterrupt:
            print("\n服务已停止")


def start_tray():
    """启动系统托盘（需要 pystray 库）"""
    try:
        import pystray
        from PIL import Image
    except ImportError:
        print("系统托盘模式需要安装: pip install pystray Pillow")
        print("正在以命令行模式启动...")
        start_server()
        return

    # 创建托盘图标
    def create_icon():
        # 创建一个简单的图标
        img = Image.new('RGB', (64, 64), color=(70, 130, 180))
        return img

    def on_show(icon, item):
        print("Lanhu MCP Server 运行中...")

    def on_setup(icon, item):
        setup_wizard()

    def on_quit(icon, item):
        icon.stop()
        os._exit(0)

    # 在后台启动服务器
    import threading
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # 创建托盘菜单
    menu = pystray.Menu(
        pystray.MenuItem("显示状态", on_show, default=True),
        pystray.MenuItem("配置向导", on_setup),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", on_quit),
    )

    # 创建托盘图标
    icon = pystray.Icon(
        "Lanhu MCP",
        create_icon(),
        "Lanhu MCP Server",
        menu
    )

    print("Lanhu MCP Server 已在后台运行（系统托盘）")
    icon.run()


def main():
    parser = argparse.ArgumentParser(description='Lanhu MCP Server')
    parser.add_argument('--setup', action='store_true', help='运行配置向导')
    parser.add_argument('--tray', action='store_true', help='以系统托盘模式运行')
    parser.add_argument('--config', action='store_true', help='显示当前配置')
    args = parser.parse_args()

    if args.setup:
        setup_wizard()
    elif args.config:
        config = load_config()
        print("当前配置:")
        for key, value in config.items():
            if key == 'LANHU_COOKIE' or key == 'DDS_COOKIE':
                print(f"  {key}: {value[:20]}...")
            else:
                print(f"  {key}: {value}")
    elif args.tray:
        start_tray()
    else:
        start_server()


if __name__ == '__main__':
    main()
