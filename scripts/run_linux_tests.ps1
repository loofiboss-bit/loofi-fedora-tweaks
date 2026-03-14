param(
    [ValidateSet("auto", "wsl", "docker")]
    [string]$Backend = "docker",
    [string]$Distro = "Ubuntu",
    [string]$TestArgs = "",
    [string]$PythonVersion = "3.12"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-SystemDepsCommand {
    param(
        [bool]$NeedsSudo = $false
    )

    # PyQt6 runtime deps: libGL, libglib, libxkbcommon, D-Bus, xcb, EGL
    $pkgs = "libgl1 libglib2.0-0 libxkbcommon0 libdbus-1-3 libdbus-1-dev libegl1 libxcb-xinerama0 libxcb-cursor0 libfontconfig1 pkg-config"
    $prefix = if ($NeedsSudo) { "sudo " } else { "" }
    return "${prefix}apt-get update -qq && ${prefix}apt-get install -y -qq $pkgs"
}

function Invoke-LinuxTestCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [string]$TestArgs,
        [bool]$NeedsSudo = $false
    )

    $sysDeps = Get-SystemDepsCommand -NeedsSudo $NeedsSudo

    $base = @(
        "set -euo pipefail",
        $sysDeps,
        "cd '$RepoRoot'",
        "python3 -m venv .venv-linux-tests",
        "source .venv-linux-tests/bin/activate",
        "python -m pip install --upgrade pip",
        "pip install -r requirements.txt",
        "pip install -e .[dev]",
        "PYTHONPATH=loofi-fedora-tweaks python -m pytest tests/ -v --tb=short $TestArgs"
    )

    return ($base -join "; ")
}

function Invoke-TestsInWsl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        [string]$Distro,
        [string]$TestArgs
    )

    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
        return $false
    }

    $linuxPath = (& wsl.exe -d $Distro wslpath -a "$RepoRoot").Trim()
    if ([string]::IsNullOrWhiteSpace($linuxPath)) {
        throw "Could not resolve repo path in WSL distro '$Distro'."
    }

    $bashCmd = Invoke-LinuxTestCommand -RepoRoot $linuxPath -TestArgs $TestArgs -NeedsSudo $true
    & wsl.exe -d $Distro bash -lc $bashCmd
    return $true
}

function Invoke-TestsInDocker {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [string]$TestArgs,
        [string]$PythonVersion
    )

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI not found. Install Docker Desktop or use WSL backend."
    }

    $image = "python:$PythonVersion-bookworm"
    $insideRoot = "/workspace"
    $linuxCmd = Invoke-LinuxTestCommand -RepoRoot $insideRoot -TestArgs $TestArgs -NeedsSudo $false

    & docker run --rm `
        --volume "${RepoRoot}:${insideRoot}" `
        --workdir $insideRoot `
        $image bash -lc $linuxCmd
}

$repoRoot = (Get-Location).Path

switch ($Backend) {
    "wsl" {
        [void](Invoke-TestsInWsl -RepoRoot $repoRoot -Distro $Distro -TestArgs $TestArgs)
        break
    }
    "docker" {
        Invoke-TestsInDocker -RepoRoot $repoRoot -TestArgs $TestArgs -PythonVersion $PythonVersion
        break
    }
    default {
        $ran = $false
        try {
            Invoke-TestsInDocker -RepoRoot $repoRoot -TestArgs $TestArgs -PythonVersion $PythonVersion
            $ran = $true
        }
        catch {
            Write-Warning "Docker backend failed: $($_.Exception.Message)"
        }

        if (-not $ran) {
            Write-Host "Docker unavailable or failed. Falling back to WSL..."
            [void](Invoke-TestsInWsl -RepoRoot $repoRoot -Distro $Distro -TestArgs $TestArgs)
        }
    }
}
