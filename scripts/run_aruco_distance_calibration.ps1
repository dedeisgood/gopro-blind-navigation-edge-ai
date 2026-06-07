param(
    [double]$MarkerSizeM = 0.15,
    [double]$KnownDistanceM = 1.0,
    [double]$Seconds = 10.0,
    [string]$Label = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
. "$PSScriptRoot\Resolve-Python.ps1"
$Python = Resolve-EdgePython -Preferred gpu

if (-not $Label) {
    $Label = ("{0:g}m" -f $KnownDistanceM)
}

Set-Location $ProjectRoot
Write-Host "Using Python: $Python"
Write-Host "MarkerSizeM: $MarkerSizeM"
Write-Host "KnownDistanceM: $KnownDistanceM"

& $Python .\scripts\calibrate_gopro_aruco_live.py `
    --gopro-ip 172.26.181.51 `
    --seconds $Seconds `
    --res 720 `
    --analysis-fps 8 `
    --dictionary 4X4_50 `
    --marker-id 0 `
    --marker-size-m $MarkerSizeM `
    --known-distance-m $KnownDistanceM `
    --hfov 118 `
    --out-dir .\runs\aruco_distance_calibration `
    --label $Label
