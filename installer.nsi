; ========================================
;  Lanhu MCP Server - NSIS 安装脚本
; ========================================
; 编译命令: makensis installer.nsi

!include "MUI2.nsh"

; ========================================
; 基本配置
; ========================================
Name "Lanhu MCP Server"
OutFile "LanhuMCP-Setup.exe"
InstallDir "$PROGRAMFILES\Lanhu MCP"
InstallDirRegKey HKLM "Software\LanhuMCP" "InstallDir"
RequestExecutionLevel admin

; 版本信息
VIProductVersion "2.0.0.0"
VIAddVersionKey "ProductName" "Lanhu MCP Server"
VIAddVersionKey "CompanyName" "Lanhu MCP"
VIAddVersionKey "FileDescription" "蓝湖MCP服务器 - 让AI助手读取蓝湖设计"
VIAddVersionKey "FileVersion" "2.0.0"
VIAddVersionKey "ProductVersion" "2.0.0"

; ========================================
; 界面配置
; ========================================
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "欢迎安装 Lanhu MCP Server"
!define MUI_WELCOMEPAGE_TEXT "Lanhu MCP Server 让所有AI助手（Cursor、Windsurf、Claude Desktop等）都能读取蓝湖设计稿和需求文档。$\n$\n功能特性：$\n• 智能需求分析$\n• UI设计稿解析$\n• 切图自动提取$\n• 团队知识共享$\n$\n点击下一步继续安装。"
!define MUI_FINISHPAGE_TITLE "安装完成"
!define MUI_FINISHPAGE_TEXT "Lanhu MCP Server 已成功安装！$\n$\n您可以通过以下方式使用：$\n1. 从开始菜单启动管理面板$\n2. 配置蓝湖Cookie$\n3. 一键配置AI IDE"
!define MUI_FINISHPAGE_RUN "$INSTDIR\LanhuMCP-GUI.exe"
!define MUI_FINISHPAGE_RUN_TEXT "启动管理面板"

; ========================================
; 安装页面
; ========================================
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; ========================================
; 卸载页面
; ========================================
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; ========================================
; 语言
; ========================================
!insertmacro MUI_LANGUAGE "SimplifiedChinese"

; ========================================
; 安装内容
; ========================================
Section "主程序" SecMain
    SectionIn RO

    ; 设置输出路径
    SetOutPath "$INSTDIR"

    ; 安装文件
    File "dist\lanhu_mcp\lanhu_mcp.exe"
    File "dist\lanhu_mcp\lanhu_mcp_gui.exe"
    File /r "dist\lanhu_mcp\_internal"

    ; 创建卸载程序
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; 写入注册表
    WriteRegStr HKLM "Software\LanhuMCP" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LanhuMCP" "DisplayName" "Lanhu MCP Server"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LanhuMCP" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LanhuMCP" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LanhuMCP" "DisplayVersion" "2.0.0"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LanhuMCP" "Publisher" "Lanhu MCP"

    ; 创建开始菜单快捷方式
    CreateDirectory "$SMPROGRAMS\Lanhu MCP"
    CreateShortCut "$SMPROGRAMS\Lanhu MCP\Lanhu MCP 管理面板.lnk" "$INSTDIR\LanhuMCP-GUI.exe"
    CreateShortCut "$SMPROGRAMS\Lanhu MCP\Lanhu MCP 服务.lnk" "$INSTDIR\lanhu_mcp.exe"
    CreateShortCut "$SMPROGRAMS\Lanhu MCP\卸载.lnk" "$INSTDIR\Uninstall.exe"

    ; 创建桌面快捷方式
    CreateShortCut "$DESKTOP\Lanhu MCP.lnk" "$INSTDIR\LanhuMCP-GUI.exe"

SectionEnd

; ========================================
; 卸载内容
; ========================================
Section "Uninstall"
    ; 删除文件
    Delete "$INSTDIR\lanhu_mcp.exe"
    Delete "$INSTDIR\LanhuMCP-GUI.exe"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir /r "$INSTDIR\_internal"
    RMDir "$INSTDIR"

    ; 删除快捷方式
    Delete "$SMPROGRAMS\Lanhu MCP\Lanhu MCP 管理面板.lnk"
    Delete "$SMPROGRAMS\Lanhu MCP\Lanhu MCP 服务.lnk"
    Delete "$SMPROGRAMS\Lanhu MCP\卸载.lnk"
    RMDir "$SMPROGRAMS\Lanhu MCP"
    Delete "$DESKTOP\Lanhu MCP.lnk"

    ; 删除注册表
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LanhuMCP"
    DeleteRegKey HKLM "Software\LanhuMCP"
SectionEnd
