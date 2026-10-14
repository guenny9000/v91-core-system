[CmdletBinding()]
param(
    [switch]$EnableRealActions,
    [switch]$AllowScaleDown,
    [switch]$Watch,
    [ValidateRange(15, 3600)]
    [int]$IntervalSeconds = 60,
    [string]$ProjectName = "",
    [string]$ComposeFile = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeScript = Join-Path $repoRoot "controller\runtime_control.py"

if (-not $ComposeFile) {
    $ComposeFile = Join-Path $repoRoot "docker-compose.yml"
}
if (-not (Test-Path -LiteralPath $runtimeScript -PathType Leaf)) {
    throw "V91 runtime controller not found: $runtimeScript"
}
if (-not (Test-Path -LiteralPath $ComposeFile -PathType Leaf)) {
    throw "Compose file not found: $ComposeFile"
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not available. No action was taken."
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not available. No action was taken."
}

$env:V91_ENABLE_REAL_ACTIONS = if ($EnableRealActions) { "1" } else { "0" }
$env:V91_ALLOW_SCALE_DOWN = if ($AllowScaleDown) { "1" } else { "0" }
if ($ProjectName) {
    $env:V91_PROJECT_NAME = $ProjectName
} else {
    $env:V91_PROJECT_NAME = ""
}

$arguments = @(
    $runtimeScript,
    "--compose-file", (Resolve-Path -LiteralPath $ComposeFile).Path,
    "--interval-seconds", "$IntervalSeconds"
)
if ($ProjectName) {
    $arguments += @("--project", $ProjectName)
}
if ($Watch) {
    $arguments += "--watch"
} else {
    $arguments += "--once"
}

Write-Host "V91 runtime controller"
Write-Host "Real actions: $($EnableRealActions.IsPresent)"
Write-Host "Scale-down allowed: $($AllowScaleDown.IsPresent)"
Write-Host "Compose file: $ComposeFile"
Write-Host "No arbitrary host commands are accepted by this controller."
& python @arguments
exit $LASTEXITCODE
