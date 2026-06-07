$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
. "$PSScriptRoot\Resolve-Python.ps1"
$Python = Resolve-EdgePython -Preferred gpu

Set-Location $ProjectRoot
Write-Host "Using Python: $Python"
Write-Host "Demo window will open on the laptop. Press q or Esc in the video window to stop."

& $Python .\scripts\realtime_gopro_obstacle_voice.py `
    --gopro-ip 172.26.181.51 `
    --seconds 90 `
    --res 480 `
    --analysis-fps 10 `
    --device auto `
    --disable-object-cues `
    --hfov 118 `
    --distance-scale 1.4212 `
    --min-stable-frames 2 `
    --cooldown 2.5 `
    --repeat-cooldown 8 `
    --lang zh-TW `
    --enable-depth-nav `
    --depth-every 5 `
    --enable-semantic-nav `
    --seg-every 4 `
    --semantic-min-stable-frames 3 `
    --decision-model .\runs\decision_classifier_v2_merged_enriched_real_only\decision_classifier.pt `
    --decision-threshold 0.70 `
    --decision-blocked-front-threshold 0.45 `
    --display `
    --display-scale 1.25 `
    --display-stable-frames 3 `
    --display-window "GoPro Blind Navigation Demo" `
    --save-video .\runs\realtime_gopro_navigation_demo_display\annotated_demo_display_480p.mp4 `
    --events .\runs\realtime_gopro_navigation_demo_display\events_demo_display.jsonl `
    --metrics .\runs\realtime_gopro_navigation_demo_display\metrics_demo_display.json
