[CmdletBinding()]
param(
    [string]$ComposeDirectory = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $ComposeDirectory).Path
$queue = Join-Path $root "queue"
$pending = Join-Path $queue "pending"
$workspace = Join-Path $root "workspace"
$runtime = Join-Path $root "runtime"
$sourceExample = Join-Path $root "examples\example.txt"

foreach ($directory in @($pending, (Join-Path $queue "processing"), (Join-Path $queue "done"), (Join-Path $queue "failed"), $workspace, (Join-Path $runtime "results"))) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

if (-not (Test-Path -LiteralPath $sourceExample -PathType Leaf)) {
    throw "Example input file is missing: $sourceExample"
}
$inputFile = Join-Path $workspace "example.txt"
if (-not (Test-Path -LiteralPath $inputFile -PathType Leaf)) {
    Copy-Item -LiteralPath $sourceExample -Destination $inputFile
}

$taskId = "hash-demo-" + [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss-fff")
$taskPath = Join-Path $pending ($taskId + ".json")
$task = @{
    task_id = $taskId
    action = "sha256_file"
    relative_path = "example.txt"
} | ConvertTo-Json -Depth 4

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($taskPath, $task + [Environment]::NewLine, $utf8NoBom)

Write-Host "V91 example task queued."
Write-Host "Task ID: $taskId"
Write-Host "Task file: $taskPath"
Write-Host "Result will appear under runtime\results\$taskId.json after a worker processes it."
Write-Host "This submits a local SHA-256 task; it does not contact the network."
