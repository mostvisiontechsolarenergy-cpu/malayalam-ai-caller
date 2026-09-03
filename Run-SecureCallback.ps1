param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https://.+\.ngrok-free\.(app|dev)$')]
    [string]$PublicUrl
)

$ErrorActionPreference = "Continue"
$projectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDirectory = Join-Path $projectDirectory "logs"
$logFile = Join-Path $logDirectory "secure-callback.log"
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

$mutex = [System.Threading.Mutex]::new(
    $false,
    "Local\DcreationSecureCallbackSupervisor"
)
$ownsMutex = $false
try {
    try {
        $ownsMutex = $mutex.WaitOne(0, $false)
    } catch [System.Threading.AbandonedMutexException] {
        $ownsMutex = $true
    }
    if (-not $ownsMutex) {
        exit 0
    }

    $ngrok = Get-Command ngrok -ErrorAction Stop
    $publicHost = ([Uri]$PublicUrl).Host
    while ($true) {
        "$(Get-Date -Format o) starting secure callback for $publicHost" |
            Add-Content -LiteralPath $logFile
        & $ngrok.Source http "--url=$publicHost" 8000 --log=stdout --log-format=json 2>&1 |
            ForEach-Object { "$_" | Add-Content -LiteralPath $logFile }
        "$(Get-Date -Format o) callback process stopped; restarting in 3 seconds" |
            Add-Content -LiteralPath $logFile
        Start-Sleep -Seconds 3
    }
} finally {
    if ($ownsMutex) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
