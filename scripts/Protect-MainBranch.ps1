[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_.-]+$')][string]$Owner,
 [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_.-]+$')][string]$Repo,
 [ValidatePattern('^[A-Za-z0-9_.-]+$')][string]$Branch="main",
 [string[]]$RequiredChecks=@(),
 [ValidateRange(0,6)][int]$RequiredApprovals=0,
 [switch]$Apply,
 [switch]$ReplaceExisting
)
Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"
$stamp=Get-Date -Format "yyyyMMdd_HHmmss"
$logDir=Join-Path ([System.IO.Path]::GetTempPath()) "v91_main_protection_$stamp"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logFile=Join-Path $logDir "run.log"
$jsonOut=Join-Path $logDir "protection_report.json"

function Write-AuditLog {
 param([string]$Message)
 $line="[ {0} ] {1}" -f (Get-Date).ToUniversalTime().ToString("o"),$Message
 Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
 Write-Output $line
}
function Write-Report {
 param([hashtable]$Report)
 $Report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonOut -Encoding UTF8
 Get-Content -LiteralPath $jsonOut
}
function Invoke-GhApiWithStatus {
 param([string]$Endpoint,[string[]]$ExtraArguments=@())
 $output=& gh api --include @ExtraArguments $Endpoint 2>&1
 $exitCode=$LASTEXITCODE
 $raw=($output | ForEach-Object { "$_" }) -join [Environment]::NewLine
 $statusCode=$null; $body=$null
 if($raw -match '(?m)^HTTP/\S+\s+(\d{3})\b'){
  $statusCode=[int]$Matches[1]
  $separator=[regex]::Match($raw,"\r?\n\r?\n")
  if($separator.Success){$body=$raw.Substring($separator.Index+$separator.Length)}
 }
 [PSCustomObject]@{ExitCode=$exitCode;StatusCode=$statusCode;Body=$body}
}
function Test-Protection {
 param($Protection,[string[]]$Checks,[int]$Approvals)
 $failures=[System.Collections.Generic.List[string]]::new()
 if($Protection.enforce_admins.enabled -ne $true){$failures.Add("enforce_admins")}
 if($Protection.allow_force_pushes.enabled -ne $false){$failures.Add("allow_force_pushes")}
 if($Protection.allow_deletions.enabled -ne $false){$failures.Add("allow_deletions")}
 if($Protection.required_conversation_resolution.enabled -ne $true){$failures.Add("required_conversation_resolution")}
 $actualApprovals=$Protection.required_pull_request_reviews.required_approving_review_count
 if($null -eq $actualApprovals -or [int]$actualApprovals -ne $Approvals){$failures.Add("required_approving_review_count")}
 if($Checks.Count -eq 0){
  if($null -ne $Protection.required_status_checks){$failures.Add("required_status_checks_expected_null")}
 }else{
  $actualChecks=@($Protection.required_status_checks.contexts | Sort-Object)
  $expectedChecks=@($Checks | Sort-Object)
  if(($actualChecks -join [Environment]::NewLine) -ne ($expectedChecks -join [Environment]::NewLine)){$failures.Add("required_status_checks")}
  if($Protection.required_status_checks.strict -ne $true){$failures.Add("required_status_checks_strict")}
 }
 [PSCustomObject]@{Matches=($failures.Count -eq 0);Differences=@($failures)}
}

$repository="$Owner/$Repo"
$endpoint="repos/$Owner/$Repo/branches/$Branch/protection"
$mode=if($Apply){"APPLY"}else{"CHECK_ONLY"}
if(-not (Get-Command gh -ErrorAction SilentlyContinue)){
 Write-AuditLog "STATUS=UNKNOWN REASON=gh_cli_not_found"
 Write-Report @{Repository=$repository;Branch=$Branch;Mode=$mode;Status="UNKNOWN";Reason="GitHub CLI not found.";LogDirectory=$logDir}; exit 2
}
& gh auth status *> $null
if($LASTEXITCODE -ne 0){
 Write-AuditLog "STATUS=UNKNOWN REASON=gh_auth_unavailable"
 Write-Report @{Repository=$repository;Branch=$Branch;Mode=$mode;Status="UNKNOWN";Reason="GitHub CLI authentication unavailable.";LogDirectory=$logDir}; exit 2
}
$before=Invoke-GhApiWithStatus -Endpoint $endpoint
$beforeProtected=$false; $beforeProtection=$null
if($before.ExitCode -eq 0 -and $before.StatusCode -eq 200){
 try{$beforeProtection=$before.Body | ConvertFrom-Json -ErrorAction Stop;$beforeProtected=$true;Write-AuditLog "BEFORE=PROTECTION_PRESENT"}
 catch{Write-AuditLog "STATUS=UNKNOWN REASON=before_response_not_valid_json";Write-Report @{Repository=$repository;Branch=$Branch;Mode=$mode;Status="UNKNOWN";Reason="Protection response could not be parsed.";LogDirectory=$logDir};exit 2}
}elseif($before.StatusCode -eq 404){
 Write-AuditLog "BEFORE=PROTECTION_NOT_FOUND"
}elseif($before.StatusCode -eq 403){
 Write-AuditLog "STATUS=UNKNOWN REASON=permission_denied"
 Write-Report @{Repository=$repository;Branch=$Branch;Mode=$mode;Status="UNKNOWN";Reason="GitHub denied access; this is not proof of missing protection.";HttpStatus=403;LogDirectory=$logDir};exit 2
}else{
 Write-AuditLog "STATUS=UNKNOWN REASON=github_read_failed"
 Write-Report @{Repository=$repository;Branch=$Branch;Mode=$mode;Status="UNKNOWN";Reason="GitHub read failed; protection state is not inferred.";HttpStatus=$before.StatusCode;ExitCode=$before.ExitCode;LogDirectory=$logDir};exit 2
}
if($beforeProtected -and -not $Apply){
 $check=Test-Protection -Protection $beforeProtection -Checks $RequiredChecks -Approvals $RequiredApprovals
 $status=if($check.Matches){"PROTECTION_MATCHES_REQUESTED_BASELINE"}else{"PROTECTION_PRESENT_DIFFERENCES_FOUND"}
 Write-AuditLog "FINAL_STATUS=$status"
 Write-Report @{Repository=$repository;Branch=$Branch;Mode=$mode;Status=$status;Differences=$check.Differences;LogDirectory=$logDir};exit 0
}
if(-not $Apply){
 Write-AuditLog "FINAL_STATUS=PROTECTION_NOT_FOUND_CHECK_ONLY"
 Write-Report @{Repository=$repository;Branch=$Branch;Mode=$mode;Status="PROTECTION_NOT_FOUND_CHECK_ONLY";LogDirectory=$logDir};exit 0
}
if($beforeProtected -and -not $ReplaceExisting){
 Write-AuditLog "APPLY=BLOCKED_EXISTING_PROTECTION"
 Write-Report @{Repository=$repository;Branch=$Branch;Mode=$mode;Status="BLOCKED_EXISTING_PROTECTION";Reason="PUT replaces existing settings. Review them and use -ReplaceExisting only if replacement is intended.";LogDirectory=$logDir};exit 3
}
$requiredStatusChecks=$null
if($RequiredChecks.Count -gt 0){$requiredStatusChecks=@{strict=$true;contexts=@($RequiredChecks)}}
$payload=[ordered]@{
 required_status_checks=$requiredStatusChecks
 enforce_admins=$true
 required_pull_request_reviews=@{dismiss_stale_reviews=$true;require_code_owner_reviews=$false;required_approving_review_count=$RequiredApprovals}
 restrictions=$null
 allow_force_pushes=$false
 allow_deletions=$false
 required_conversation_resolution=$true
}
$payloadFile=Join-Path $logDir "protection_payload.json"
$payloadJson=$payload | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($payloadFile,$payloadJson,[System.Text.UTF8Encoding]::new($false))
$put=Invoke-GhApiWithStatus -Endpoint $endpoint -ExtraArguments @("--method","PUT","-H","Accept: application/vnd.github+json","--input",$payloadFile)
if($put.ExitCode -ne 0 -or $put.StatusCode -notin @(200,201)){
 Write-AuditLog "APPLY=FAILED_OR_UNCONFIRMED"
 Write-Report @{Repository=$repository;Branch=$Branch;Mode=$mode;Status="APPLY_FAILED_OR_UNCONFIRMED";HttpStatus=$put.StatusCode;ExitCode=$put.ExitCode;LogDirectory=$logDir};exit 2
}
Write-AuditLog "APPLY=REQUEST_ACCEPTED_READBACK_REQUIRED"
$after=Invoke-GhApiWithStatus -Endpoint $endpoint
if($after.ExitCode -ne 0 -or $after.StatusCode -ne 200){
 Write-AuditLog "FINAL_STATUS=APPLIED_BUT_READBACK_UNKNOWN"
 Write-Report @{Repository=$repository;Branch=$Branch;Mode=$mode;Status="APPLIED_BUT_READBACK_UNKNOWN";HttpStatus=$after.StatusCode;ExitCode=$after.ExitCode;LogDirectory=$logDir};exit 2
}
try{$afterProtection=$after.Body | ConvertFrom-Json -ErrorAction Stop}
catch{Write-AuditLog "FINAL_STATUS=APPLIED_BUT_READBACK_INVALID";Write-Report @{Repository=$repository;Branch=$Branch;Mode=$mode;Status="APPLIED_BUT_READBACK_INVALID";LogDirectory=$logDir};exit 2}
$verification=Test-Protection -Protection $afterProtection -Checks $RequiredChecks -Approvals $RequiredApprovals
$finalStatus=if($verification.Matches){"PROTECTION_VERIFIED_MATCH"}else{"PROTECTION_MISMATCH"}
Write-AuditLog "FINAL_STATUS=$finalStatus"
Write-Report @{Repository=$repository;Branch=$Branch;Mode=$mode;Status=$finalStatus;Differences=$verification.Differences;RequiredChecks=@($RequiredChecks);RequiredApprovals=$RequiredApprovals;LogDirectory=$logDir}
if(-not $verification.Matches){exit 1};exit 0
