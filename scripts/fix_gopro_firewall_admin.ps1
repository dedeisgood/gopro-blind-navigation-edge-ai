$ErrorActionPreference = "Stop"

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "This script must be run as Administrator." -ForegroundColor Yellow
    Write-Host "Right-click PowerShell and choose 'Run as administrator', then run this script again."
    exit 1
}

$goproExe = "C:\Program Files (x86)\GoPro\GoPro Webcam\GoPro Webcam.exe"
if (-not (Test-Path $goproExe)) {
    throw "GoPro Webcam executable not found: $goproExe"
}

$rules = @(
    @{ DisplayName = "GoPro Webcam Allow Inbound (Codex)"; Direction = "Inbound" },
    @{ DisplayName = "GoPro Webcam Allow Outbound (Codex)"; Direction = "Outbound" }
)

foreach ($rule in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $rule.DisplayName -ErrorAction SilentlyContinue
    if ($existing) {
        Set-NetFirewallRule -DisplayName $rule.DisplayName -Enabled True -Action Allow -Profile Any
        Write-Host "Updated firewall rule: $($rule.DisplayName)"
    }
    else {
        New-NetFirewallRule `
            -DisplayName $rule.DisplayName `
            -Program $goproExe `
            -Direction $rule.Direction `
            -Action Allow `
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
Write-Host "Current GoPro-related firewall rules:"
Get-NetFirewallApplicationFilter -PolicyStore ActiveStore |
    Where-Object { $_.Program -match "GoPro|gopro" } |
    ForEach-Object {
        $app = $_
        Get-NetFirewallRule -AssociatedNetFirewallApplicationFilter $app |
            Select-Object DisplayName, Enabled, Direction, Action, Profile, @{ Name = "Program"; Expression = { $app.Program } }
    } |
    Format-Table -AutoSize

Write-Host ""
Write-Host "Current GoPro network profile:"
Get-NetConnectionProfile |
    Where-Object { $_.InterfaceAlias -in $goproAdapters.Name } |
    Select-Object Name, InterfaceAlias, NetworkCategory, IPv4Connectivity |
    Format-Table -AutoSize

Write-Host ""
Write-Host "Testing GoPro API:"
try {
    $version = Invoke-WebRequest -Uri "http://172.26.181.51:8080/gopro/version" -UseBasicParsing -TimeoutSec 5
    Write-Host "GoPro API OK: $($version.Content)"
}
catch {
    Write-Host "GoPro API test failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

