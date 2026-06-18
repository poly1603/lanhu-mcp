# 先安装所有依赖（含pyinstaller）
pip install -e ".[build]"

# 然后打包
pyinstaller LanhuMCP-onefile.spec --clean --noconfirm