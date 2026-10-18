param(
    [string]$ServiceName = "V91Bootstrap",
    [string]$DisplayName = "V91 Production Bootstrap",
    [string]$Description = "Starts V91 controller in production mode with real actions.",
    [string]$ScriptPath = "$(Split-Path -Parent $MyInvocation.MyCommand.Path)\\bootstrap.py",
    [string]$NssmPath = "C:\\nssm\\nssm.exe"
)

# Ensure nssm exists
if (-Not (Test-Path $NssmPath)) {
    Write-Error "nssm not found at $NssmPath. Install nssm first."
    exit 1
}

# Install the service
& $NssmPath install $ServiceName "python" "$ScriptPath"
& $NssmPath set $ServiceName DisplayName "$DisplayName"
& $NssmPath set $ServiceName Description "$Description"
& $NssmPath set $ServiceName Start "SERVICE_AUTO_START"
& $NssmPath set $ServiceName AppRestartDelay 5000

Write-Host "Service $ServiceName installed and set to auto-start. Use 'nssm start $ServiceName' to run now."
