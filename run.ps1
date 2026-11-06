# 一键启动（Windows）
#
#   .\run.ps1            仅本机访问
#   .\run.ps1 -Lan       允许局域网访问（绑定 0.0.0.0）
#
# 首次运行自动安装后端/前端依赖；日志写入 .run\ 目录。

param(
    [switch]$Lan,
    [switch]$NoBrowser,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$runDir = Join-Path $root ".run"
$bindHost = if ($Lan) { "0.0.0.0" } else { "127.0.0.1" }

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-Port([string]$TargetHost, [int]$Port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect($TargetHost, $Port)
        $client.Close()
        return $true
    }
    catch {
        return $false
    }
}

Write-Step "检查运行环境"
foreach ($cmd in @("python", "node", "npm.cmd")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "未找到 $cmd，请安装 Python 3.11+ 与 Node.js 18+ 并加入 PATH"
    }
}
Write-Host ("python " + (& python --version))
Write-Host ("node   " + (& node --version))

Write-Step "检查依赖（首次运行会自动安装）"
& python -c "import fastapi, uvicorn, sqlalchemy, httpx, pydantic" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "安装后端依赖 ..."
    & python -m pip install -r (Join-Path $backendDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "后端依赖安装失败" }
}
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "安装前端依赖 ..."
    Push-Location $frontendDir
    & npm.cmd install
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { throw "前端依赖安装失败" }
}

New-Item -ItemType Directory -Force -Path $runDir | Out-Null

Write-Step "启动后端  http://${bindHost}:$BackendPort"
$backend = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "main:app", "--host", $bindHost, "--port", $BackendPort `
    -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $runDir "backend.log") `
    -RedirectStandardError (Join-Path $runDir "backend.err.log")

Write-Step "启动前端  http://${bindHost}:$FrontendPort"
$frontend = Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run", "dev", "--", "--host", $bindHost, "--port", $FrontendPort, "--strictPort" `
    -WorkingDirectory $frontendDir -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $runDir "frontend.log") `
    -RedirectStandardError (Join-Path $runDir "frontend.err.log")

Write-Step "等待服务就绪（后端启动时会自动同步一次数据，可能需要几十秒）"
$ready = $false
for ($i = 0; $i -lt 120; $i++) {
    if ($backend.HasExited -or $frontend.HasExited) { break }
    if ((Test-Port "127.0.0.1" $BackendPort) -and (Test-Port "127.0.0.1" $FrontendPort)) {
        $ready = $true
        break
    }
    Start-Sleep -Milliseconds 500
}

if (-not $ready) {
    Write-Host "服务启动失败，日志如下：" -ForegroundColor Red
    Get-Content (Join-Path $runDir "backend.err.log") -Tail 20 -ErrorAction SilentlyContinue
    Get-Content (Join-Path $runDir "frontend.err.log") -Tail 20 -ErrorAction SilentlyContinue
    foreach ($proc in @($frontend, $backend)) {
        if ($proc -and -not $proc.HasExited) { taskkill /T /F /PID $proc.Id *> $null }
    }
    exit 1
}

$url = "http://127.0.0.1:$FrontendPort"
Write-Host ""
Write-Host "  系统已启动：" -ForegroundColor Green
Write-Host "  前端  $url"
Write-Host "  后端  http://127.0.0.1:$BackendPort/api/health"
Write-Host "  文档  http://127.0.0.1:$BackendPort/docs"
Write-Host "  日志  $runDir"
Write-Host "  按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host ""

if (-not $NoBrowser) {
    Start-Process $url
}

try {
    while ($true) {
        Start-Sleep -Seconds 1
        if ($backend.HasExited -or $frontend.HasExited) {
            throw "服务意外退出，请查看 $runDir 下的日志"
        }
    }
}
finally {
    foreach ($proc in @($frontend, $backend)) {
        if ($proc -and -not $proc.HasExited) { taskkill /T /F /PID $proc.Id *> $null }
    }
    Write-Host "服务已停止" -ForegroundColor Yellow
}
