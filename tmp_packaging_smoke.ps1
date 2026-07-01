$ErrorActionPreference = 'Stop'
$repo = Get-Location
$exe = Join-Path $repo 'dist\LanhuMCP.exe'

Write-Host "EXE_EXISTS=$([IO.File]::Exists($exe))"
if (-not (Test-Path $exe)) { exit 10 }
$item = Get-Item $exe
Write-Host "EXE_SIZE=$($item.Length)"
Write-Host "EXE_TIME=$($item.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"

# Clean previous app processes that may have been left by interrupted smoke runs.
Get-Process LanhuMCP -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# GUI smoke: start default app, confirm process stays alive briefly, then stop it.
$p = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds 10
$p.Refresh()
Write-Host "GUI_STARTED=$(-not $p.HasExited)"
if ($p.HasExited) {
    Write-Host "GUI_EXIT_CODE=$($p.ExitCode)"
    exit 11
}
Stop-Process -Id $p.Id -Force
Wait-Process -Id $p.Id -ErrorAction SilentlyContinue
Write-Host "GUI_STOPPED=True"

# Login helper smoke.
$tmp = Join-Path $env:TEMP ('lanhu-login-smoke-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
$result = Join-Path $tmp 'result.json'
$storage = Join-Path $tmp 'webview'
$env:LANHU_LOGIN_HELPER_SMOKE = '1'
$p2 = Start-Process -FilePath $exe -ArgumentList @('--login-helper', $result, $storage, 'https://lanhuapp.com/web/') -PassThru -Wait
Remove-Item Env:LANHU_LOGIN_HELPER_SMOKE -ErrorAction SilentlyContinue
Write-Host "LOGIN_EXIT=$($p2.ExitCode)"
Write-Host "LOGIN_RESULT_EXISTS=$(Test-Path $result)"
if ($p2.ExitCode -ne 0) { exit 12 }
if (-not (Test-Path $result)) { exit 13 }
$json = Get-Content $result -Raw -Encoding utf8 | ConvertFrom-Json
Write-Host "LOGIN_STATUS=$($json.status)"
if ($json.status -ne 'success') { exit 14 }
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue

# Server smoke: use isolated APPDATA and local host/port.
$oldAppData = $env:APPDATA
$appdata = Join-Path $env:TEMP ('lanhu-appdata-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $appdata | Out-Null
$port = 49337
$env:APPDATA = $appdata
$env:SERVER_HOST = '127.0.0.1'
$env:SERVER_PORT = [string]$port
$p3 = Start-Process -FilePath $exe -ArgumentList @('--server') -PassThru
$open = $false
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Milliseconds 500
    $p3.Refresh()
    if ($p3.HasExited) { break }
    try {
        $client = New-Object Net.Sockets.TcpClient
        $iar = $client.BeginConnect('127.0.0.1', $port, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne(250)) {
            $client.EndConnect($iar)
            $open = $true
            $client.Close()
            break
        }
        $client.Close()
    } catch {}
}
$p3.Refresh()
Write-Host "SERVER_STARTED=$(-not $p3.HasExited)"
Write-Host "SERVER_PORT_OPEN=$open"
if (-not $p3.HasExited) {
    Stop-Process -Id $p3.Id -Force
    Wait-Process -Id $p3.Id -ErrorAction SilentlyContinue
    Write-Host "SERVER_STOPPED=True"
} else {
    Write-Host "SERVER_EXIT_CODE=$($p3.ExitCode)"
}
$env:APPDATA = $oldAppData
Remove-Item Env:SERVER_HOST -ErrorAction SilentlyContinue
Remove-Item Env:SERVER_PORT -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $appdata -ErrorAction SilentlyContinue
if (-not $open) { exit 15 }

Write-Host "SMOKE_OK=True"
exit 0
