$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
. "$PSScriptRoot\Resolve-Python.ps1"
$Python = Resolve-EdgePython -Preferred cpu

Set-Location $ProjectRoot
& $Python .\scripts\check_yolo_env.py
& $Python .\scripts\run_obstacle_assist.py --config .\configs\blind_obstacle_assist_sample.json
