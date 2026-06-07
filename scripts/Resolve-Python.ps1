function Resolve-EdgePython {
    param(
        [ValidateSet("gpu", "cpu", "any")]
        [string]$Preferred = "any"
    )

    $homeDir = [Environment]::GetFolderPath("UserProfile")
    $gpuPython = Join-Path $homeDir "anaconda3\envs\edge_gpu\python.exe"
    $cpuPython = Join-Path $homeDir "anaconda3\envs\edge_cpu\python.exe"

    $candidates = @()
    if ($Preferred -eq "gpu") {
        $candidates += $env:EDGE_GPU_PYTHON
        $candidates += $gpuPython
        $candidates += $env:EDGE_CPU_PYTHON
        $candidates += $cpuPython
    } elseif ($Preferred -eq "cpu") {
        $candidates += $env:EDGE_CPU_PYTHON
        $candidates += $cpuPython
        $candidates += $env:EDGE_GPU_PYTHON
        $candidates += $gpuPython
    } else {
        $candidates += $env:EDGE_GPU_PYTHON
        $candidates += $gpuPython
        $candidates += $env:EDGE_CPU_PYTHON
        $candidates += $cpuPython
    }

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    return "python"
}
