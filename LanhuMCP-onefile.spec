# -*- mode: python ; coding: utf-8 -*-
"""
单文件打包配置 - GUI + Server 合并为一个 exe
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules


fastmcp_hiddenimports = collect_submodules('fastmcp')
fastmcp_datas = collect_data_files('fastmcp')

mcp_hiddenimports = collect_submodules('mcp')

# 收集 flet（新的 Flet GUI 依赖）。flet 未安装时不阻断 server/CLI 打包。
try:
    flet_hiddenimports = collect_submodules('flet')
    flet_datas = collect_data_files('flet')
    # flet.utils.pip 在 frozen EXE 里会调用 `python -m pip install`，
    # 触发 ModuleNotFoundError 后又调用 `exit(1)`，但 frozen 下 exit 不存在
    # 会抛 NameError 杀掉进程。运行时由 hook_flet_no_pip.py 替换为 no-op，
    # 这里把 ensure_* 三个名字保留（hook 里要 monkey-patch 它们），
    # 其余子模块保留。
    flet_hiddenimports = [
        m for m in flet_hiddenimports
        if not m.startswith('flet.utils.pip')
    ] + ['flet.utils.pip']
except Exception:
    flet_hiddenimports = []
    flet_datas = []

a = Analysis(
    ['lanhu_mcp_launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('.env.example', '.'),
        ('lanhu_login_helper.py', '.'),
    ] + fastmcp_datas + flet_datas,
    hiddenimports=[
        # === 核心入口 ===
        'lanhu_mcp_server',
        'lanhu_login_helper',
        'lanhu_mcp_launcher',
        'lanhu_mcp.runtime',

        # === pywebview ===
        'webview',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'webview.platforms.mshtml',
        'pythonnet',
        'clr',
        'clr_loader',
        'clr_loader.netfx',
        'clr_loader.hostfxr',
        'clr_loader.ffi',

        # === lanhu_mcp 子包 ===
        'lanhu_mcp',
        'lanhu_mcp.server',
        'lanhu_mcp.tools',
        'lanhu_mcp.tools.design_system',
        'lanhu_mcp.tools.layout_spec',
        'lanhu_mcp.tools.components',
        'lanhu_mcp.tools.interactions',
        'lanhu_mcp.tools.quality_check',
        'lanhu_mcp.tools.code_gen',
        'lanhu_mcp.tools.compare',
        'lanhu_mcp.tools.batch_download',
        'lanhu_mcp.tools.annotations',
        'lanhu_mcp.tools.version_history',
        'lanhu_mcp.tools.svg_extract',
        'lanhu_mcp.tools.measurements',
        'lanhu_mcp.tools.animation',
        'lanhu_mcp.tools.export_options',
        'lanhu_mcp.tools.responsive',
        'lanhu_mcp.core',
        'lanhu_mcp.core.paths',
        'lanhu_mcp.core.accounts',
        'lanhu_mcp.core.projects',
        'lanhu_mcp.core.avatar',
        'lanhu_mcp.services',
        'lanhu_mcp.services.tools_registry',
        'lanhu_mcp.services.lanhu_api',
        'lanhu_mcp.services.ide_config',
        'lanhu_mcp.services.service_manager',
        'lanhu_mcp.services.login_helper',
        'lanhu_mcp.services.browser_login',

        # === Default browser Cookie bridge ===
        'browser_cookie3',
        'win32crypt',
        'Cryptodome',
        'Cryptodome.Cipher',
        'Cryptodome.Cipher.AES',
        'lz4',
        'shadowcopy',
        'wmi',

        # === lanhu_mcp.gui（Flet 界面）===
        'lanhu_mcp.gui',
        'lanhu_mcp.gui.theme',
        'lanhu_mcp.gui.state',
        'lanhu_mcp.gui.app',
        'lanhu_mcp.gui.components',
        'lanhu_mcp.gui.components.widgets',
        'lanhu_mcp.gui.pages',
        'lanhu_mcp.gui.pages.overview',
        'lanhu_mcp.gui.pages.service',
        'lanhu_mcp.gui.pages.accounts',
        'lanhu_mcp.gui.pages.projects',
        'lanhu_mcp.gui.pages.designs',
        'lanhu_mcp.gui.pages.ide_tools',
        'lanhu_mcp.gui.pages.logs',

        'lanhu_mcp.converters',
        'lanhu_mcp.utils',
        'lanhu_mcp.prompts',

        # === HTTP 客户端 ===
        'httpx',
        'httpcore',
        'h11',

        # === HTML 解析 ===
        'bs4',
        'bs4.builder',
        'lxml',
        'lxml.etree',
        'lxml._elementpath',

        # === 环境变量 ===
        'dotenv',

        # === HTML 压缩 ===
        'htmlmin',

        # === JSON Schema ===
        'jsonschema',
        'jsonschema_specifications',
        'referencing',

        # === Starlette ===
        'starlette',
        'starlette.responses',
        'starlette.routing',
        'starlette.middleware',
        'starlette.websockets',

        # === Uvicorn ===
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',

        # === Pydantic ===
        'pydantic',
        'pydantic_core',
        'pydantic_settings',

        # === SSE ===
        'sse_starlette',

        # === Auth ===
        'authlib',
        'joserfc',

        # === Watchfiles ===
        'watchfiles',

        # === Websockets ===
        'websockets',

        # === 网络相关 ===
        'ssl',
        'certifi',
        'charset_normalizer',
        'idna',

        # === importlib 元数据（关键！fastmcp 需要） ===
        'importlib.metadata',
        'importlib_metadata',
        # FastMCP/Docket 在 HTTP 服务启动时通过 importlib 动态加载。
        'docket',
        'burner_redis',
        'redis',
        'fakeredis',
        'key_value',
        'key_value.aio',
        'key_value.aio.stores.filetree',
        'aiofile',
        'caio',
    ] + fastmcp_hiddenimports + mcp_hiddenimports + flet_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        'hook_fastmcp_metadata.py',
        'hook_flet_no_pip.py',
    ],
    excludes=[
        'unittest',
        'pytest',
        '_pytest',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'jupyter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LanhuMCP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
