$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
. "$PSScriptRoot\Resolve-Python.ps1"
$Python = Resolve-EdgePython -Preferred cpu

Set-Location $ProjectRoot
& $Python .\scripts\check_yolo_env.py
& $Python .\scripts\yolo_image_probe.py --image .\assets\ultralytics_bus.jpg --device cpu
& $Python .\scripts\run_pipeline.py --config .\configs\yolo_sample_person_counting.json
