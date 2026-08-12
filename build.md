# Windows 发布

一次构建生成两个文件：

- `dist/LanhuMCP.exe`：下载后直接双击运行的便携版。
- `dist/LanhuMCP-Setup-v<version>.exe`：带版本号的安装程序，安装完成后自动创建桌面快捷方式。

前置条件：Python、Node.js、PyInstaller 和 NSIS（`makensis.exe`）。

```bash
node build.js --clean
```

如果暂时没有 NSIS，只生成便携版 exe：

```bash
node build.js --clean --no-installer
```

也可以双击 `build.bat` 或 `build_onefile.bat`。
