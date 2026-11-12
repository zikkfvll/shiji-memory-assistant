param([switch]$NoBrowser, [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) { throw '缺少项目环境，请先阅读 README.txt 的安装说明。' }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'dist\index.html'))) { throw '缺少页面构建，请先运行 npm run build。' }
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($listener) { throw '8765 端口正在使用。请关闭之前的拾记窗口或核查占用，不会自动停止其他程序。' }
$localProcess = $null
try {
  $localProcess = Start-Process -FilePath $projectPython -ArgumentList @('-X','utf8','run.py') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
  $ready = $false
  for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ($localProcess.HasExited) { throw '本地服务启动失败。请在项目目录运行 .venv\Scripts\python.exe run.py 查看原因。' }
    try {
      $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 1
      if ($health.status -eq 'ok' -and $health.mode -eq 'local_rules') { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 300 }
  }
  if (-not $ready) { throw '服务未在预期时间内就绪。' }
  Write-Host '拾记已启动：http://127.0.0.1:8765'
  Write-Host '仅本机可访问。按 Ctrl+C 关闭本次服务；记录保存在 data 目录。'
  if ($CheckOnly) { Write-Host '启动自检通过。'; return }
  if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8765' }
  Wait-Process -Id $localProcess.Id
} finally {
  if ($localProcess -and -not $localProcess.HasExited) { Stop-Process -Id $localProcess.Id -ErrorAction SilentlyContinue }
}
