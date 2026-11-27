#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"

$Repo = if ($env:MATLAB_SHELL_REPO) { $env:MATLAB_SHELL_REPO } else { "muzijin701/matlab-shell" }
$InstallDir = if ($env:MATLAB_SHELL_INSTALL_DIR) { $env:MATLAB_SHELL_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA "matlab-shell\bin" }
$LocalArchive = $env:MATLAB_SHELL_ARCHIVE
$NoModifyPath = $env:MATLAB_SHELL_NO_MODIFY_PATH -eq "1"

$archRaw = $env:PROCESSOR_ARCHITECTURE
if ($archRaw -eq "ARM64") {
    $Arch = "arm64"
} else {
    $Arch = "x86_64"
}

$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("matlab-shell-install-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null

try {
    if ($LocalArchive) {
        $ArchivePath = (Resolve-Path $LocalArchive).Path
    } else {
        $ReleaseApi = "https://api.github.com/repos/$Repo/releases/latest"
        Write-Host "Fetching latest release metadata from $Repo..."
        $Release = Invoke-RestMethod -Uri $ReleaseApi -Headers @{ "User-Agent" = "matlab-shell-installer" }
        $Pattern = "windows-$Arch\.zip$"
        $Asset = $Release.assets | Where-Object { $_.name -match $Pattern } | Select-Object -First 1
        if (-not $Asset) {
            throw "No Windows release asset matching '$Pattern' found in latest release of $Repo."
        }
        $ArchivePath = Join-Path $TempDir $Asset.name
        Write-Host "Downloading $($Asset.name)..."
        Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $ArchivePath
    }

    if (Test-Path $InstallDir) {
        Remove-Item -Path $InstallDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

    Write-Host "Extracting to $InstallDir..."
    Expand-Archive -Path $ArchivePath -DestinationPath $InstallDir -Force

    if (-not $NoModifyPath) {
        $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $Entries = @()
        if ($UserPath) {
            $Entries = $UserPath -split ";" | Where-Object { $_ -ne "" }
        }
        $AlreadyInPath = $Entries | Where-Object { $_.TrimEnd("\") -ieq $InstallDir.TrimEnd("\") }
        if (-not $AlreadyInPath) {
            $NewPath = ($Entries + $InstallDir) -join ";"
            [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
            Write-Host "Added $InstallDir to User PATH. Restart your terminal to pick up PATH changes."
        }
    }

    $MshExe = Join-Path $InstallDir "msh.exe"
    if (-not (Test-Path $MshExe)) {
        throw "Installation verification failed: $MshExe not found."
    }

    Write-Host "Installed matlab-shell successfully!"
    Write-Host "Run: `"$MshExe`" --version"
} finally {
    if (Test-Path $TempDir) {
        Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
