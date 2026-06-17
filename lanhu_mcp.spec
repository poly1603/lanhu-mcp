# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置

打包命令：
  Windows: pyinstaller lanhu_mcp.spec
  macOS:   pyinstaller lanhu_mcp.spec
  Linux:   pyinstaller lanhu_mcp.spec
"""
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# 收集所有子模块
hidden_imports = [
    'lanhu_mcp',
    'lanhu_mcp.server',
    'lanhu_mcp.tools',
    'lanhu_mcp.core',
    'lanhu_mcp.converters',
    'lanhu_mcp.utils',
    'lanhu_mcp.prompts',
    'fastmcp',
    'httpx',
    'bs4',
    'playwright',
    'dotenv',
]

a = Analysis(
    ['lanhu_mcp_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('lanhu_mcp', 'lanhu_mcp'),
        ('.env.example', '.'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='lanhu_mcp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 保持控制台窗口
    icon=None,  # 可以添加 .ico 图标文件
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='lanhu_mcp',
)
