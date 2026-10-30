# ─────────────────────────────────────────────────────────────
# VatKnow 本地开发启动脚本（Windows PowerShell）
# 用法：
#   .\start.ps1           # 自动检测，优先 Docker
#   .\start.ps1 -Local    # 强制本地启动
#   .\start.ps1 -Docker   # 强制 Docker
# 或双击 start.bat
# ─────────────────────────────────────────────────────────────

param(
    [switch]$Local,
    [switch]$Docker,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$RUN = Join-Path $ROOT ".run"
New-Item -ItemType Directory -Force -Path $RUN | Out-Null

# ── 参数解析 ──────────────────────────────────────────────────
$MODE = "auto"
if ($Help) {
    Write-Host "用法: .\start.ps1 [-Local|-Docker]"
    Write-Host "  -Local    强制本地启动（不用 Docker）"
    Write-Host "  -Docker   强制使用 Docker"
    Write-Host "  无参数    自动检测，优先 Docker"
    exit 0
}
if ($Local)  { $MODE = "local" }
if ($Docker) { $MODE = "docker" }

function Write-Info  { param($msg) Write-Host ">> $msg" -ForegroundColor Cyan }
function Write-Warn  { param($msg) Write-Host "!! $msg" -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "!! $msg" -ForegroundColor Red }

# ── Docker 检测 ───────────────────────────────────────────────
function Test-Docker {
    try {
        $null = & docker info 2>&1
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Start-Docker {
    Write-Info "使用 Docker 启动..."

    $envFile = Join-Path $ROOT ".env"
    if (-not (Test-Path $envFile)) {
        Write-Warn ".env 文件不存在，从 .env.example 复制..."
        Copy-Item (Join-Path $ROOT ".env.example") $envFile
        Write-Warn "请编辑 .env 填写 JWT_SECRET 等配置后重新运行"
        exit 1
    }

    Push-Location $ROOT
    try {
        docker compose up --build -d
        if ($LASTEXITCODE -ne 0) { throw "docker compose 启动失败" }
    } finally {
        Pop-Location
    }

    Write-Host ""
    Write-Info "Docker 服务已启动！"
    Write-Info "界面：http://localhost:3000"
    Write-Info "API 文档：http://localhost:8000/docs"
    Write-Info "查看日志：docker compose logs -f"
    Write-Info "停止服务：docker compose down"
    exit 0
}

# ── PostgreSQL ────────────────────────────────────────────────
function Test-PgReady {
    try {
        $null = & pg_isready -q 2>&1
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Find-PgBin {
    $paths = @(
        "C:\Program Files\PostgreSQL\*\bin",
        "C:\Program Files (x86)\PostgreSQL\*\bin",
        "$env:LOCALAPPDATA\Programs\pgAdmin *\runtime",
        "C:\msys64\mingw64\bin"
    )
    foreach ($p in $paths) {
        $resolved = Resolve-Path $p -ErrorAction SilentlyContinue
        if ($resolved) {
            foreach ($r in $resolved) {
                if (Test-Path (Join-Path $r "psql.exe")) {
                    $env:PATH = "$r;$env:PATH"
                    Write-Info "找到 PostgreSQL: $r"
                    return $true
                }
            }
        }
    }
    if (Get-Command psql -ErrorAction SilentlyContinue) { return $true }
    return $false
}

function Ensure-PgRunning {
    if (Test-PgReady) { return }
    Write-Info "PostgreSQL 未运行，尝试启动..."
    $svc = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($svc) {
        Write-Info "启动服务: $($svc.Name)"
        Start-Service -Name $svc.Name
        Start-Sleep -Seconds 3
        if (Test-PgReady) { return }
    }
    if (Get-Command scoop -ErrorAction SilentlyContinue) {
        $scoopPg = scoop list 2>$null | Where-Object { $_ -match "postgresql" }
        if ($scoopPg) {
            scoop start postgresql 2>$null
            Start-Sleep -Seconds 3
            if (Test-PgReady) { return }
        }
    }
    Write-Err "无法自动启动 PostgreSQL，请手动启动后重试"
    Write-Host "   常见方式：services.msc → 找到 postgresql 服务 → 启动"
    exit 1
}

function Ensure-PgDatabase {
    $roleExists = & psql -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='vatknow'" 2>$null
    if ($roleExists.Trim() -ne "1") {
        Write-Info "创建数据库用户 vatknow"
        & psql -d postgres -c "CREATE USER vatknow WITH PASSWORD 'vatknow' SUPERUSER;"
    }
    $dbExists = & psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='vatknow'" 2>$null
    if ($dbExists.Trim() -ne "1") {
        Write-Info "创建数据库 vatknow"
        & psql -d postgres -c "CREATE DATABASE vatknow OWNER vatknow;"
    }
}

# ── 端口工具 ──────────────────────────────────────────────────
function Test-Alive {
    param($url)
    try {
        $resp = Invoke-WebRequest -Uri $url -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop
        return $resp.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Free-Port {
    param($port)
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $pids = $conn | Select-Object -ExpandProperty OwningProcess -Unique
        Write-Warn "端口 $port 被占用（pid: $($pids -join ',')），正在释放..."
        foreach ($pid in $pids) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 500
    }
}

# ── 后端 API ──────────────────────────────────────────────────
function Start-Api {
    if (Test-Alive "http://127.0.0.1:8000/api/v1/health") {
        Write-Info "API 已在 :8000 运行"
        return
    }
    Free-Port 8000

    $venvPython = Join-Path $ROOT "backend\.venv\Scripts\python.exe"
    $venvUvicorn = Join-Path $ROOT "backend\.venv\Scripts\uvicorn.exe"

    if (-not (Test-Path $venvUvicorn)) {
        Write-Info "初始化后端虚拟环境..."
        & python -m venv (Join-Path $ROOT "backend\.venv")
        & $venvPython -m pip install -q -r (Join-Path $ROOT "backend\requirements.txt")
    }

    $envFile = Join-Path $ROOT ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
                [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
            }
        }
    }

    $logFile = Join-Path $RUN "api.log"
    $pidFile = Join-Path $RUN "api.pid"

    $process = Start-Process -FilePath $venvUvicorn `
        -ArgumentList "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory (Join-Path $ROOT "backend") `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError (Join-Path $RUN "api.err.log") `
        -NoNewWindow -PassThru

    $process.Id | Out-File -FilePath $pidFile -Encoding ascii
    Write-Info "API 已启动 pid=$($process.Id)"
}

# ── 前端 ──────────────────────────────────────────────────────
function Start-Web {
    if (Test-Alive "http://127.0.0.1:3000/") {
        Write-Info "前端已在 :3000 运行"
        return
    }
    Free-Port 3000

    $frontendDir = Join-Path $ROOT "frontend"
    $nodeModules = Join-Path $frontendDir "node_modules"

    if (-not (Test-Path $nodeModules)) {
        Write-Info "安装前端依赖..."
        Push-Location $frontendDir
        & npm install --silent
        Pop-Location
    }

    $logFile = Join-Path $RUN "web.log"
    $pidFile = Join-Path $RUN "web.pid"

    Push-Location $frontendDir
    $process = Start-Process -FilePath "npm" `
        -ArgumentList "run", "dev", "--", "--host", "127.0.0.1", "--port", "3000" `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError (Join-Path $RUN "web.err.log") `
        -NoNewWindow -PassThru
    Pop-Location

    $process.Id | Out-File -FilePath $pidFile -Encoding ascii
    Write-Info "前端已启动 pid=$($process.Id)"
}

function Start-Local {
    Write-Info "本地模式启动（Windows）..."
    Write-Host ""

    if (-not (Find-PgBin)) {
        Write-Err "未找到 PostgreSQL"
        Write-Host "   请安装 PostgreSQL 16+ 并确保 psql.exe 在 PATH 中"
        Write-Host "   推荐方式："
        Write-Host "   - 官网安装器: https://www.postgresql.org/download/windows/"
        Write-Host "   - Scoop:      scoop install postgresql"
        Write-Host "   - Winget:     winget install PostgreSQL.PostgreSQL"
        exit 1
    }

    Ensure-PgRunning
    Ensure-PgDatabase
    Write-Host ""

    Start-Api
    Start-Web
    Write-Host ""

    Write-Info "完成！打开 http://localhost:3000"
    Write-Info "停止服务: Stop-Process -Id (Get-Content .run\api.pid), (Get-Content .run\web.pid)"
}

# ── 主流程 ────────────────────────────────────────────────────
function Main {
    switch ($MODE) {
        "docker" { Start-Docker }
        "local"  { Start-Local }
        default {
            if (Test-Docker) {
                Write-Info "检测到 Docker，优先使用容器化启动"
                Write-Info "如需强制本地启动，请运行: .\start.ps1 -Local"
                Write-Host ""
                Start-Docker
            } else {
                Write-Info "未检测到 Docker，使用本地环境启动"
                Write-Info "如需使用 Docker，请安装后运行: .\start.ps1 -Docker"
                Write-Host ""
                Start-Local
            }
        }
    }
}

Main
