param(
    [switch]$Rebuild,
    [switch]$NoBrowser,
    [ValidateRange(30, 300)]
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"

$projectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectDirectory
$startedAt = Get-Date

function Resolve-DockerExecutable {
    $command = Get-Command docker -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Docker\Docker\resources\bin\docker.exe"),
        (Join-Path $env:ProgramData "DockerDesktop\version-bin\docker.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw "Docker was not found. Install or open Docker Desktop, then try again."
}

function Test-DockerEngine([string]$DockerExecutable) {
    try {
        & $DockerExecutable info --format "{{.ServerVersion}}" *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Start-DockerDesktopIfNeeded([string]$DockerExecutable) {
    if (Test-DockerEngine $DockerExecutable) {
        return
    }

    $desktopCandidates = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Docker\Docker\Docker Desktop.exe")
    )
    $desktop = $desktopCandidates |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1

    if (-not $desktop) {
        throw "Docker Desktop is not running. Open Docker Desktop and run this launcher again."
    }

    Write-Host "Docker Desktop is starting (first start after reboot can take longer)..." -ForegroundColor Yellow
    Start-Process -FilePath $desktop -WindowStyle Hidden

    $dockerDeadline = (Get-Date).AddSeconds(120)
    do {
        Start-Sleep -Seconds 3
        if (Test-DockerEngine $DockerExecutable) {
            Write-Host "Docker is ready." -ForegroundColor Green
            return
        }
    } while ((Get-Date) -lt $dockerDeadline)

    throw "Docker Desktop did not become ready within two minutes. Open Docker Desktop and check its status."
}

function Get-EnvironmentValue([string]$Name) {
    $line = Get-Content -LiteralPath ".env" |
        Where-Object { $_ -match "^$([regex]::Escape($Name))=" } |
        Select-Object -First 1
    if (-not $line) { return "" }
    return $line.Substring($line.IndexOf("=") + 1).Trim().Trim('"').Trim("'")
}

function Start-SecureCallbackSupervisor {
    $automaticTunnel = (Get-EnvironmentValue "CLOUDFLARE_QUICK_TUNNEL_ENABLED").ToLowerInvariant()
    $publicWebhookUrl = Get-EnvironmentValue "PUBLIC_WEBHOOK_BASE_URL"
    if ($automaticTunnel -ne "true" -and $publicWebhookUrl -match '^https://.+\.ngrok-free\.(app|dev)$') {
        Start-Process -FilePath "powershell.exe" `
            -ArgumentList @(
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", (Join-Path $projectDirectory "Run-SecureCallback.ps1"),
                "-PublicUrl", $publicWebhookUrl
            ) `
            -WindowStyle Hidden
    }
}

function Test-FrontendReady {
    try {
        $response = Invoke-WebRequest `
            -Uri "http://127.0.0.1:3000/login" `
            -UseBasicParsing `
            -TimeoutSec 4
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Get-BackendHealth {
    try {
        return Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 4
    } catch {
        return $null
    }
}

$docker = Resolve-DockerExecutable
Start-DockerDesktopIfNeeded $docker

if ($Rebuild) {
    Write-Host "Updating Dcreation application images..." -ForegroundColor Cyan
    & $docker compose up --build -d --remove-orphans
} else {
    Write-Host "Opening Dcreation (fast start; no rebuild)..." -ForegroundColor Cyan
    & $docker compose up -d --remove-orphans
}
if ($LASTEXITCODE -ne 0) {
    if (-not $Rebuild) {
        throw "The fast start failed. Run Update-Dcreation.cmd once, then use Open-Dcreation.cmd normally."
    }
    throw "Docker Compose failed to build or start the application."
}

Start-SecureCallbackSupervisor

Write-Host "Waiting for the dashboard and API..." -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$lastProgressAt = Get-Date
$frontendReady = $false
$backendReady = $false
$backendHealth = $null

do {
    if (-not $backendReady) {
        $backendHealth = Get-BackendHealth
        $backendReady = $null -ne $backendHealth -and $backendHealth.status -eq "ok"
    }
    if (-not $frontendReady) {
        $frontendReady = Test-FrontendReady
    }

    if ($frontendReady -and $backendReady) {
        break
    }

    if (((Get-Date) - $lastProgressAt).TotalSeconds -ge 10) {
        Write-Host "Still starting: dashboard=$frontendReady, API=$backendReady"
        $lastProgressAt = Get-Date
    }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $deadline)

if (-not ($frontendReady -and $backendReady)) {
    & $docker compose ps
    throw "Dcreation did not become ready within $TimeoutSeconds seconds. Run: docker compose logs --tail=100 backend frontend"
}

$elapsedSeconds = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 1)
Write-Host "Dcreation is ready in $elapsedSeconds seconds." -ForegroundColor Green

if ($backendHealth -and $backendHealth.calling_callback -eq "ready") {
    Write-Host "Phone calling connection: ready" -ForegroundColor Green
} else {
    $callbackDetail = if ($backendHealth -and $backendHealth.calling_callback_detail) {
        $backendHealth.calling_callback_detail
    } else {
        "starting in the background"
    }
    Write-Host "Dashboard is ready. Phone callback: $callbackDetail" -ForegroundColor Yellow
}

$applicationUrl = "http://localhost:3000/login"
Write-Host "Open: $applicationUrl"
if (-not $NoBrowser) {
    Start-Process $applicationUrl
}

