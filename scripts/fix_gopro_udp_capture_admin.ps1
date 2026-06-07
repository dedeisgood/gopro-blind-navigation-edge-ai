$ErrorActionPreference = "Stop"

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "This script must be run as Administrator." -ForegroundColor Yellow
    exit 1
}

. "$PSScriptRoot\Resolve-Python.ps1"
$python = Resolve-EdgePython -Preferred cpu
$homeDir = [Environment]::GetFolderPath("UserProfile")
$ffmpeg = Join-Path $homeDir "anaconda3\envs\edge_cpu\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"

$programRules = @(
    @{ DisplayName = "GoPro UDP Capture Python Inbound (Codex)"; Program = $python; Direction = "Inbound" },
    @{ DisplayName = "GoPro UDP Capture Python Outbound (Codex)"; Program = $python; Direction = "Outbound" },
    @{ DisplayName = "GoPro UDP Capture FFmpeg Inbound (Codex)"; Program = $ffmpeg; Direction = "Inbound" },
    @{ DisplayName = "GoPro UDP Capture FFmpeg Outbound (Codex)"; Program = $ffmpeg; Direction = "Outbound" }
)

foreach ($rule in $programRules) {
    if (-not (Test-Path $rule.Program)) {
        Write-Host "Program not found: $($rule.Program)" -ForegroundColor Yellow
        continue
    }

    $existing = Get-NetFirewallRule -DisplayName $rule.DisplayName -ErrorAction SilentlyContinue
    if ($existing) {
        Set-NetFirewallRule -DisplayName $rule.DisplayName -Enabled True -Action Allow -Profile Any
        Write-Host "Updated firewall rule: $($rule.DisplayName)"
    }
    else {
        New-NetFirewallRule `
            -DisplayName $rule.DisplayName `
            -Program $rule.Program `
            -Direction $rule.Direction `
            -Action Allow `
            -Profile Any | Out-Null
        Write-Host "Created firewall rule: $($rule.DisplayName)"
    }
}

$portRules = @(
    @{ DisplayName = "GoPro UDP 8554 Inbound (Codex)"; Direction = "Inbound" },
    @{ DisplayName = "GoPro UDP 8554 Outbound (Codex)"; Direction = "Outbound" }
)

foreach ($rule in $portRules) {
    $existing = Get-NetFirewallRule -DisplayName $rule.DisplayName -ErrorAction SilentlyContinue
    if ($existing) {
        Set-NetFirewallRule -DisplayName $rule.DisplayName -Enabled True -Action Allow -Profile Any
        Set-NetFirewallPortFilter -AssociatedNetFirewallRule $existing -Protocol UDP -LocalPort 8554
        Write-Host "Updated firewall rule: $($rule.DisplayName)"
    }
    else {
        New-NetFirewallRule `
            -DisplayName $rule.DisplayName `
            -Direction $rule.Direction `
            -Action Allow `
            -Protocol UDP `
            -LocalPort 8554 `
            -Profile Any | Out-Null
        Write-Host "Created firewall rule: $($rule.DisplayName)"
    }
}

$goproAdapters = Get-NetAdapter | Where-Object {
    $_.InterfaceDescription -match "GoPro|RNDIS" -or $_.Name -match "GoPro"
}

foreach ($adapter in $goproAdapters) {
    try {
        Set-NetConnectionProfile -InterfaceAlias $adapter.Name -NetworkCategory Private
        Write-Host "Set network category to Private: $($adapter.Name)"
    }
    catch {
        Write-Host "Could not set network category for $($adapter.Name): $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "GoPro UDP capture firewall rules:"
Get-NetFirewallRule |
    Where-Object { $_.DisplayName -match "GoPro UDP|GoPro UDP Capture" } |
    Select-Object DisplayName, Enabled, Direction, Action, Profile |
    Format-Table -AutoSize
