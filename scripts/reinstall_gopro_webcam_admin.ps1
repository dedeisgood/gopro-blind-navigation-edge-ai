$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

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

$installerCandidates = @(
    "$env:USERPROFILE\Downloads\GoProWebcam-1.2.2.830-RELEASE.msi",
    "$env:USERPROFILE\Downloads\GoProWebcam-1.2.2.830-RELEASE (1).msi",
    "$env:USERPROFILE\Downloads\GoProWebcam-1.2.2.830-RELEASE (2).msi"
)

$installer = $installerCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $installer) {
    throw "No GoPro Webcam MSI installer found in Downloads."
}

$productCode = "{6DA1C152-86B9-48F0-9C68-760509C29DAC}"
$exe = "C:\Program Files (x86)\GoPro\GoPro Webcam\GoPro Webcam.exe"

Write-Host "Using installer: $installer"

Write-Host "Stopping GoPro Webcam..."
Get-Process "GoPro Webcam" -ErrorAction SilentlyContinue | Stop-Process -Force

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $ProjectRoot "work\gopro_reinstall_backup_$stamp"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$statePaths = @(
    "$env:LOCALAPPDATA\GoPro_Inc",
    "$env:APPDATA\GoPro"
)

foreach ($path in $statePaths) {
    if (Test-Path $path) {
        $dest = Join-Path $backupRoot (Split-Path $path -Leaf)
        try {
            Move-Item -LiteralPath $path -Destination $dest -Force
            Write-Host "Moved state: $path -> $dest"
        }
        catch {
            Write-Host "Could not move state folder ${path}: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
}

Write-Host "Uninstalling GoPro Webcam..."
$uninstall = Start-Process -FilePath "msiexec.exe" -ArgumentList "/x $productCode /qn /norestart" -Wait -PassThru
Write-Host "Uninstall exit code: $($uninstall.ExitCode)"

if ($uninstall.ExitCode -ne 0 -and $uninstall.ExitCode -ne 1605) {
    Write-Host "Silent uninstall did not fully succeed. Trying uninstall from MSI package..." -ForegroundColor Yellow
    $uninstall2 = Start-Process -FilePath "msiexec.exe" -ArgumentList "/x `"$installer`" /qn /norestart" -Wait -PassThru
    Write-Host "MSI uninstall exit code: $($uninstall2.ExitCode)"
}

Start-Sleep -Seconds 2

Write-Host "Installing GoPro Webcam..."
$install = Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$installer`" /qn /norestart" -Wait -PassThru
Write-Host "Install exit code: $($install.ExitCode)"

if ($install.ExitCode -ne 0) {
    throw "Install failed with exit code $($install.ExitCode)"
}

Write-Host "Re-applying firewall rules..."
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
            -Program $exe `
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

Write-Host "Starting GoPro Webcam..."
Start-Process -FilePath $exe
Start-Sleep -Seconds 8

$proc = Get-Process "GoPro Webcam" -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host "GoPro Webcam process is running."
    $proc | Select-Object ProcessName, Id, Path, Responding | Format-Table -AutoSize
}
else {
    Write-Host "GoPro Webcam process is not running after reinstall." -ForegroundColor Yellow
}

Write-Host "Recent GoPro crash events:"
Get-WinEvent -FilterHashtable @{ LogName = "Application"; StartTime = (Get-Date).AddMinutes(-3) } -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -match "GoPro Webcam.exe" } |
    Select-Object TimeCreated, ProviderName, Id, Message -First 5 |
    Format-List

Write-Host ""
Write-Host "Done. If the tray icon still does not appear, open Task Manager and check whether GoPro Webcam.exe stays running."
