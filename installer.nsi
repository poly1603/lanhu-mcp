; Unicode NSIS script. Build with: makensis installer.nsi
; Build with: makensis installer.nsi

!include "MUI2.nsh"

!ifndef APP_DIST_DIR
!define APP_DIST_DIR "dist"
!endif
!ifndef APP_VERSION
!define APP_VERSION "2.0.0"
!endif
!ifndef APP_PAYLOAD
!define APP_PAYLOAD "${APP_DIST_DIR}\LanhuMCP.exe"
!endif

Name "Lanhu MCP"
OutFile "${APP_DIST_DIR}\LanhuMCP-Setup-v${APP_VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\Lanhu MCP"
InstallDirRegKey HKCU "Software\LanhuMCP" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma

VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName" "Lanhu MCP"
VIAddVersionKey "CompanyName" "Lanhu MCP"
VIAddVersionKey "FileDescription" "Lanhu MCP desktop application"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"

!define MUI_ICON "assets\lanhu_mcp.ico"
!define MUI_UNICON "assets\lanhu_mcp.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "欢迎安装 Lanhu MCP"
!define MUI_WELCOMEPAGE_TEXT "Lanhu MCP 提供蓝湖设计稿读取、分析和 MCP 服务能力。$\n$\n安装完成后，桌面会创建 Lanhu MCP 快捷方式。"
!define MUI_FINISHPAGE_TITLE "安装完成"
!define MUI_FINISHPAGE_TEXT "Lanhu MCP 已成功安装。$\n$\n您可以通过桌面快捷方式启动应用。"
!define MUI_FINISHPAGE_RUN "$INSTDIR\LanhuMCP.exe"
!define MUI_FINISHPAGE_RUN_TEXT "启动 Lanhu MCP"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "Lanhu MCP" SecMain
    SectionIn RO
    SetShellVarContext current
    SetOutPath "$INSTDIR"
    File /oname=LanhuMCP.exe "${APP_PAYLOAD}"

    WriteUninstaller "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "Software\LanhuMCP" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LanhuMCP" "DisplayName" "Lanhu MCP"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LanhuMCP" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LanhuMCP" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LanhuMCP" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LanhuMCP" "Publisher" "Lanhu MCP"

    CreateDirectory "$SMPROGRAMS\Lanhu MCP"
    CreateShortCut "$SMPROGRAMS\Lanhu MCP\Lanhu MCP.lnk" "$INSTDIR\LanhuMCP.exe"
    CreateShortCut "$SMPROGRAMS\Lanhu MCP\卸载 Lanhu MCP.lnk" "$INSTDIR\Uninstall.exe"
    CreateShortCut "$DESKTOP\Lanhu MCP.lnk" "$INSTDIR\LanhuMCP.exe"
SectionEnd

Section "Uninstall"
    SetShellVarContext current
    Delete "$INSTDIR\LanhuMCP.exe"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir "$INSTDIR"

    Delete "$SMPROGRAMS\Lanhu MCP\Lanhu MCP.lnk"
    Delete "$SMPROGRAMS\Lanhu MCP\卸载 Lanhu MCP.lnk"
    RMDir "$SMPROGRAMS\Lanhu MCP"
    Delete "$DESKTOP\Lanhu MCP.lnk"

    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LanhuMCP"
    DeleteRegKey HKCU "Software\LanhuMCP"
SectionEnd
