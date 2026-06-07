$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$homeDir = [Environment]::GetFolderPath("UserProfile")
$Conda = if ($env:CONDA_EXE) { $env:CONDA_EXE } else { Join-Path $homeDir "anaconda3\Scripts\conda.exe" }
$EnvName = "edge_gpu"
$EnvPath = Join-Path $homeDir "anaconda3\envs\$EnvName"

Set-Location $ProjectRoot

if (-not (Test-Path $Conda)) {
    throw "Conda not found at $Conda"
}

if (-not (Test-Path $EnvPath)) {
    Write-Host "Creating conda env: $EnvName"
    & $Conda create -n $EnvName python=3.11 -y
} else {
    Write-Host "Conda env already exists: $EnvName"
}

$Python = Join-Path $EnvPath "python.exe"

Write-Host "Upgrading pip"
& $Python -m pip install --upgrade pip

Write-Host "Installing PyTorch CUDA 12.8 wheels"
& $Python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

Write-Host "Installing project runtime packages"
& $Python -m pip install -r .\requirements.txt

Write-Host "Verifying CUDA"
& $Python .\scripts\check_torch_cuda.py
