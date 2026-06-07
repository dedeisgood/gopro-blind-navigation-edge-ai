$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
. "$PSScriptRoot\Resolve-Python.ps1"
$Python = Resolve-EdgePython -Preferred gpu

Set-Location $ProjectRoot
Write-Host "Using Python: $Python"

& $Python .\scripts\realtime_gopro_obstacle_voice.py `
    --gopro-ip 172.26.181.51 `
    --seconds 30 `
    --res 480 `
    --analysis-fps 8 `
    --device auto `
    --hfov 118 `
    --distance-scale 1.4212 `
    --min-stable-frames 2 `
    --cooldown 1.2 `
    --repeat-cooldown 4 `
    --lang zh-TW `
    --enable-depth-nav `
    --depth-every 4 `
    --enable-semantic-nav `
    --seg-every 3 `
    --semantic-min-stable-frames 2 `
    --decision-model .\runs\decision_classifier_v2_merged_enriched_real_only\decision_classifier.pt `
    --decision-threshold 0.50 `
    --save-video .\runs\realtime_gopro_navigation_learned\annotated_navigation_learned_480p.mp4 `
    --events .\runs\realtime_gopro_navigation_learned\events_navigation_learned.jsonl `
    --metrics .\runs\realtime_gopro_navigation_learned\metrics_navigation_learned.json
