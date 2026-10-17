# V91 local verification — read-only with respect to source/runtime data.
# This script does NOT pull code, install packages, start containers, deploy, or repair files.
# It creates timestamped evidence logs under .\artifacts\v91-local-verify-<timestamp>.
[CmdletBinding()]
param(
    [string]$LedgerPath = (Join-Path (Split-Path -Parent (Get-Location).Path) "v91-audit-ledger"),
    [switch]$SkipDockerComposeCheck
)
$ErrorActionPreference = "Continue"
$Root = (Get-Location).Path
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$EvidenceDir = Join-Path $Root ("artifacts\v91-local-verify-" + $Stamp)
New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null
$SummaryPath = Join-Path $EvidenceDir "SUMMARY.txt"
$script:Summary = [System.Collections.Generic.List[string]]::new()
function Add-Result([string]$Name, [string]$Status, [string]$Detail) {
    $line = "{0} | {1} | {2}" -f $Name, $Status, $Detail
    $script:Summary.Add($line)
    Write-Host $line
}
function Run-Logged([string]$Name, [string]$Exe, [string[]]$Args, [string]$WorkingDirectory) {
    $Log = Join-Path $EvidenceDir ($Name + ".log")
    "COMMAND: $Exe $($Args -join ' ')" | Set-Content -LiteralPath $Log -Encoding UTF8
    "WORKDIR: $WorkingDirectory" | Add-Content -LiteralPath $Log -Encoding UTF8
    Push-Location $WorkingDirectory
    try {
        & $Exe @Args *>&1 | Tee-Object -FilePath $Log -Append
        $Code = $LASTEXITCODE
    } catch {
        $_ | Out-String | Add-Content -LiteralPath $Log -Encoding UTF8
        $Code = 9009
    } finally {
        Pop-Location
    }
    if ($Code -eq 0) { Add-Result $Name "PASS" "exit=$Code; log=$Log" }
    else { Add-Result $Name "FAIL" "exit=$Code; log=$Log" }
    return $Code
}
function Get-GitValue([string[]]$Args, [string]$WorkingDirectory) {
    Push-Location $WorkingDirectory
    try { $value = & git @Args 2>&1; $code = $LASTEXITCODE }
    finally { Pop-Location }
    if ($code -ne 0) { return $null }
    return (($value | Out-String).Trim())
}
function Check-Ancestor([string]$RepoPath, [string]$Commit, [string]$Label) {
    if (-not (Test-Path (Join-Path $RepoPath ".git"))) {
        Add-Result $Label "UNKNOWN" "Kein Git-Repository unter $RepoPath"
        return
    }
    & git -C $RepoPath merge-base --is-ancestor $Commit HEAD 2>$null
    if ($LASTEXITCODE -eq 0) { Add-Result $Label "PASS" "$Commit ist Vorfahr des lokalen HEAD" }
    else { Add-Result $Label "UNKNOWN" "Commit nicht als Vorfahr des lokalen HEAD bestätigt; kein automatisches Update ausgeführt" }
}
"V91 LOCAL VERIFICATION" | Set-Content -LiteralPath $SummaryPath -Encoding UTF8
"Timestamp local: $(Get-Date -Format o)" | Add-Content -LiteralPath $SummaryPath -Encoding UTF8
"Core path: $Root" | Add-Content -LiteralPath $SummaryPath -Encoding UTF8
"Evidence directory: $EvidenceDir" | Add-Content -LiteralPath $SummaryPath -Encoding UTF8

if (-not (Test-Path (Join-Path $Root ".git"))) {
    Add-Result "CORE_REPOSITORY" "FAIL" "Im aktuellen Verzeichnis kein .git gefunden. Erst in v91-core-system wechseln."
    $script:Summary | Add-Content -LiteralPath $SummaryPath -Encoding UTF8
    exit 2
}
$Head = Get-GitValue @("rev-parse","HEAD") $Root
$Branch = Get-GitValue @("branch","--show-current") $Root
$Status = Get-GitValue @("status","--short") $Root
Add-Result "CORE_HEAD" "INFO" "$Head; branch=$Branch"
if ([string]::IsNullOrWhiteSpace($Status)) { Add-Result "CORE_WORKTREE" "PASS" "Keine lokalen Änderungen gemeldet" }
else { Add-Result "CORE_WORKTREE" "WARN" "Lokale Änderungen vorhanden; nichts wird verworfen. Siehe git status --short." }

# Verify known merge commits are contained in this local checkout; no network operation.
Check-Ancestor $Root "3d449e58a98d175e60eb883b29928cb8021000dc" "GUARDED_RUNNER_MERGE"
Check-Ancestor $Root "8f8e042f065501efe41aa74e21ec325c877be08f" "KEY_REGISTRY_MERGE"
Check-Ancestor $Root "0a0d8b581d57ab7907b9b15e3bc5c2ab64554f26" "GLOBAL_GUARD_MERGE"

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    Add-Result "PYTHON" "FAIL" "python nicht gefunden; Python 3.10+ installieren oder PATH prüfen."
} else {
    $PyVersion = & python --version 2>&1
    Add-Result "PYTHON" "INFO" "$PyVersion"
    Run-Logged "CORE_TESTS" "python" @("-m","pytest","-q","tests","addons/v91_guardrail/tests") $Root | Out-Null
    Run-Logged "CORE_COMPILE" "python" @("-m","compileall","-q","controller","addons","global_guard") $Root | Out-Null
}
if (-not $SkipDockerComposeCheck) {
    $Docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $Docker) { Add-Result "DOCKER_COMPOSE_CONFIG" "UNKNOWN" "Docker nicht installiert/verfügbar; keine Container gestartet." }
    else {
        Run-Logged "DOCKER_COMPOSE_CONFIG" "docker" @("compose","config","--quiet") $Root | Out-Null
    }
}

if (Test-Path (Join-Path $LedgerPath ".git")) {
    $LedgerHead = Get-GitValue @("rev-parse","HEAD") $LedgerPath
    Add-Result "LEDGER_HEAD" "INFO" "$LedgerHead; path=$LedgerPath"
    Check-Ancestor $LedgerPath "fb6de901dd916b90a1c28e7bbb1af979d1e5cd3b" "LEDGER_BASE_MERGE"
    Check-Ancestor $LedgerPath "c9c410aa67b0804e044d7877d1f5abb9153be336" "LEDGER_TIMESTAMP_FIX"
    Run-Logged "LEDGER_TESTS" "python" @("-m","pytest","-q") $LedgerPath | Out-Null
} else {
    Add-Result "LEDGER_REPOSITORY" "UNKNOWN" "Nicht gefunden unter $LedgerPath; Ledger-Prüfung übersprungen."
}

Add-Result "PRODUCTION_STATUS" "UNKNOWN" "Dieses Skript beweist keinen laufenden Dienst, keine Tool-Anbindung, keine WORM-Speicherung und kein Modelltraining."
$script:Summary | Add-Content -LiteralPath $SummaryPath -Encoding UTF8
Write-Host ""
Write-Host "Fertig. Belege liegen in: $EvidenceDir"
Write-Host "Es wurden keine Container gestartet, keine Daten repariert und kein Code gepullt."

# Fail closed: CI must fail if any required check failed, even if logs were written.
$Failures = @($script:Summary | Where-Object { $_ -match '\| FAIL \|' })
if ($Failures.Count -gt 0) {
    Write-Host "Gesamtstatus: FAIL ($($Failures.Count) fehlgeschlagene Prüfung(en))."
    exit 1
}
Write-Host "Gesamtstatus: PASS (keine Prüfung als FAIL protokolliert; UNKNOWN bleibt separat sichtbar)."
exit 0
