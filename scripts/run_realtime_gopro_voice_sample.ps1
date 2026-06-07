$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
. "$PSScriptRoot\Resolve-Python.ps1"
$Python = Resolve-EdgePython -Preferred gpu

Set-Location $ProjectRoot
Write-Host "Using Python: $Python"

& $Python .\scripts\realtime_gopro_obstacle_voice.py `
    --gopro-ip 172.26.181.51 `
    --seconds 15 `
    --res 480 `
    --analysis-fps 12 `
    --device auto `
    --hfov 118 `
    --distance-scale 1.4212 `
    --min-stable-frames 2 `
    --cooldown 1.2 `
    --repeat-cooldown 4 `
    --lang zh-TW `
    --save-video .\runs\realtime_gopro_obstacle_voice\annotated_realtime_clock_distance_480p.mp4 `
    --events .\runs\realtime_gopro_obstacle_voice\events_clock_distance.jsonl `
    --metrics .\runs\realtime_gopro_obstacle_voice\metrics_clock_distance.json
