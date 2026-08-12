# -*- mode: python ; coding: utf-8 -*-
"""
单文件打包配置 - GUI + Server 合并为一个 exe
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from pathlib import Path
import shutil
import sys


# PyInstaller uses ICO resources on Windows and PNG/ICNS resources on Unix.
# The GUI also applies the same path to Flet's live native window at runtime.
native_icon = 'assets/lanhu_mcp.ico' if sys.platform == 'win32' else 'assets/lanhu_mcp_logo.png'


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


def _patch_flet_windows_metadata(source: Path) -> Path | None:
    """Stage Flet's native view with Lanhu's Windows version metadata.

    Flet is a child process on Windows.  If its stock ``flet.exe`` is used,
    the taskbar context menu gets the framework's ``Flet description`` even
    when the parent PyInstaller executable has Lanhu resources.  Patch only a
    build-local copy; the developer's installed Flet package is never edited.
    """
    if sys.platform != 'win32' or not source.is_file():
        return None
    try:
        import pefile
        import win32api
    except Exception:
        return None

    staging = Path.cwd() / 'build' / 'lanhu-flet-runtime'
    staging.mkdir(parents=True, exist_ok=True)
    target = staging / 'flet.exe'
    shutil.copy2(source, target)
    pe = pefile.PE(str(target))
    version_entries = [entry for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries if entry.id == 16]
    if not version_entries:
        pe.close()
        return None
    version = version_entries[0]
    resources = []
    for name in version.directory.entries:
        for language in name.directory.entries:
            data = bytearray(pe.get_data(
                language.data.struct.OffsetToData,
                language.data.struct.Size,
            ))
            # Every replacement fits in the original UTF-16 slot, keeping
            # the version-resource offsets and lengths valid.
            for old, new in {
                'Copyright (C) 2023 Appveyor Systems Inc. All rights reserved. Licensed under the Apache License, Version 2.0': 'Lanhu MCP',
                'Appveyor Systems Inc.': 'Lanhu MCP',
                'Flet description': 'Lanhu MCP',
                # The InternalName/ProductName slots in this runtime are only
                # four UTF-16 characters wide.  Keep the replacement within
                # that slot; the user-facing description above carries the
                # full Lanhu MCP name.
                'Flet': 'Lan.',
                'flet.exe': 'lanh.exe',
            }.items():
                old_bytes = old.encode('utf-16le') + b'\x00\x00'
                new_bytes = new.encode('utf-16le') + b'\x00\x00'
                if len(new_bytes) <= len(old_bytes):
                    position = data.find(old_bytes)
                    while position >= 0:
                        data[position:position + len(old_bytes)] = (
                            new_bytes + b'\x00' * (len(old_bytes) - len(new_bytes))
                        )
                        position = data.find(old_bytes, position + len(old_bytes))
            resources.append((name.id, language.id, bytes(data)))
    pe.close()

    handle = win32api.BeginUpdateResource(str(target), False)
    try:
        for resource_name, language_id, data in resources:
            win32api.UpdateResource(handle, 16, resource_name, data, language_id)
        win32api.EndUpdateResource(handle, False)
    except Exception:
        win32api.EndUpdateResource(handle, True)
        raise
    return target


flet_desktop_hiddenimports = []
flet_desktop_datas = []
try:
    import flet_desktop

    flet_desktop_hiddenimports = collect_submodules('flet_desktop')
    flet_desktop_datas = collect_data_files('flet_desktop')
    flet_runtime = Path(flet_desktop.__file__).parent / 'app' / 'flet' / 'flet.exe'
    patched_flet_runtime = _patch_flet_windows_metadata(flet_runtime)
    if patched_flet_runtime is not None:
        flet_desktop_datas = [
            item for item in flet_desktop_datas
            if Path(item[0]).name.lower() != 'flet.exe'
        ]
        flet_desktop_datas.append((str(patched_flet_runtime), 'flet_desktop/app/flet'))
except Exception:
    # Source-mode development can still use the installed Flet runtime when
    # the optional desktop package or metadata patcher is unavailable.
    pass

# The tray is optional at source/runtime level, but include it in GUI builds
# when the GUI extras are installed.  Missing build extras must not block the
# server-only analysis path.
try:
    pystray_hiddenimports = collect_submodules('pystray')
    pystray_datas = collect_data_files('pystray')
except Exception:
    pystray_hiddenimports = []
    pystray_datas = []

optional_gui_hiddenimports = []
try:
    import pystray  # noqa: F401
    optional_gui_hiddenimports += ['pystray', 'pystray._win32'] + pystray_hiddenimports
except Exception:
    pass
try:
    import PIL  # noqa: F401
    optional_gui_hiddenimports += ['PIL', 'PIL.Image', 'PIL.ImageDraw']
except Exception:
    pass

a = Analysis(
    ['lanhu_mcp_launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('.env.example', '.'),
        ('lanhu_login_helper.py', '.'),
        # The GUI reads signatures from source when building the inline
        # method form. Include these two small source modules in the frozen
        # bundle so packaged builds do not fall back to an empty arguments
        # object for required MCP parameters such as ``url``.
        ('lanhu_mcp_server.py', '.'),
        ('lanhu_mcp/server.py', 'lanhu_mcp'),
        ('assets', 'assets'),
    ] + fastmcp_datas + flet_datas + flet_desktop_datas + pystray_datas,
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
        'lanhu_mcp.gui.branding',
        'lanhu_mcp.gui.state',
        'lanhu_mcp.gui.app',
        'lanhu_mcp.gui.tray',
        'lanhu_mcp.gui.floating',
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
    ] + fastmcp_hiddenimports + mcp_hiddenimports + flet_hiddenimports + flet_desktop_hiddenimports + optional_gui_hiddenimports,
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
    icon=native_icon,
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
