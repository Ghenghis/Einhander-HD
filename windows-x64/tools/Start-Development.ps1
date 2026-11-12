[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$Port = 8094,
    [switch]$WebOnly,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimePath = Join-Path $projectRoot 'build-release\Einhander_Recompiled.exe'
$bridgePath = Join-Path $PSScriptRoot 'ein_bridge.py'
$packPath = Join-Path $projectRoot 'hd-textures\stage1-v1'
$gamePath = Join-Path $projectRoot 'game.toml'
$discPath = Join-Path (Split-Path -Parent $projectRoot) 'ROM\Einhander (USA).cue'
$biosPath = Join-Path $projectRoot 'build-release\bios\SCPH1001.BIN'
$workspaceUrl = "http://127.0.0.1:$Port"

foreach ($requiredPath in @($bridgePath, (Join-Path $PSScriptRoot 'dev_center.js'), (Join-Path $PSScriptRoot 'research_service.py'), (Join-Path $PSScriptRoot 'research_lab.js'), (Join-Path $PSScriptRoot 'research_catalog.json'), (Join-Path $PSScriptRoot 'material_lab.js'), (Join-Path $PSScriptRoot 'skin_collection\collection.json'))) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) { throw "Missing development file: $requiredPath" }
}
if (-not $WebOnly) {
    foreach ($requiredPath in @($runtimePath, $gamePath, $discPath, $biosPath, (Join-Path $packPath 'manifest.json'))) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) { throw "Missing game prerequisite: $requiredPath" }
    }
}
$pythonCommand = Get-Command python.exe -ErrorAction Stop
if ($Check) {
    Write-Output "Development workspace ready: $workspaceUrl"
    Write-Output "Python: $($pythonCommand.Source)"
    Write-Output "Runtime: $runtimePath"
    return
}

$bridgeReady = $false
try {
    $catalog = Invoke-RestMethod -Uri "$workspaceUrl/dev/catalog" -TimeoutSec 2
    $research = Invoke-RestMethod -Uri "$workspaceUrl/dev/research" -TimeoutSec 2
    $bridgeReady = $catalog.ok -and $catalog.disc -eq 'SCUS-94243' -and $catalog.fields.Count -gt 0 -and $research.ok -and $research.catalog.scenarios.Count -gt 0
} catch { }
if (-not $bridgeReady) {
    # Refuse to replace another listener; this launcher only owns its new process.
    if (Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $Port is occupied by another service or an older bridge. Choose -Port with a free local port."
    }
    $logRoot = Join-Path $projectRoot 'logs'
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $env:EIN_DEBUG_PORT = '4370'
    $bridgeProcess = Start-Process -FilePath $pythonCommand.Source -ArgumentList @('"' + $bridgePath + '"', "$Port") -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logRoot "development-$Port.out.log") -RedirectStandardError (Join-Path $logRoot "development-$Port.err.log") -PassThru
    $startupTimer = [Diagnostics.Stopwatch]::StartNew()
    while ($startupTimer.Elapsed.TotalSeconds -lt 6) {
        if ($bridgeProcess.HasExited) { throw "Bridge exited. Inspect logs\development-$Port.err.log." }
        try {
            $catalog = Invoke-RestMethod -Uri "$workspaceUrl/dev/catalog" -TimeoutSec 1
            $research = Invoke-RestMethod -Uri "$workspaceUrl/dev/research" -TimeoutSec 1
            if ($catalog.ok -and $catalog.fields.Count -gt 0 -and $research.ok -and $research.catalog.scenarios.Count -gt 0) { $bridgeReady = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 150
    }
    if (-not $bridgeReady) { throw "Bridge did not become ready. Inspect logs\development-$Port.err.log." }
}

Start-Process -FilePath "$workspaceUrl/#skins"
if (-not $WebOnly) {
    $env:EIN_DEBUG_PORT = '4370'
    $env:EIN_DEV_URL = $workspaceUrl
    $env:PSXRECOMP_HD_TEXTURE_ROOT = $packPath
    $env:PSXRECOMP_HD_PAGE_FALLBACK = '1'
    $env:PSXRECOMP_HD_DECODE_BUDGET_MB = '256'
    $env:PSXRECOMP_HD_CPU_AUTHORITY = '0'
    # The launcher is interactive and intentionally visible. Its normal Play
    # action owns game startup and settings persistence.
    Start-Process -FilePath $runtimePath -ArgumentList @('--game', '"' + $gamePath + '"', '--disc', '"' + $discPath + '"', '--bios', '"' + $biosPath + '"') -WorkingDirectory $projectRoot
}
