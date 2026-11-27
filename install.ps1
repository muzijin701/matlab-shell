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
        $SumsAsset = $Release.assets | Where-Object { $_.name -eq "SHA256SUMS.txt" } | Select-Object -First 1
        if (-not $SumsAsset) {
            throw "No SHA256SUMS.txt asset found in latest release of $Repo."
        }

        $ArchivePath = Join-Path $TempDir $Asset.name
        $SumsPath = Join-Path $TempDir "SHA256SUMS.txt"
        Write-Host "Downloading $($Asset.name)..."
        Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $ArchivePath
        Invoke-WebRequest -Uri $SumsAsset.browser_download_url -OutFile $SumsPath

        $ExpectedHash = $null
        foreach ($line in (Get-Content -Path $SumsPath -Encoding UTF8)) {
            if ($line -match '^\s*([0-9a-fA-F]{64})\s+\*?(.+?)\s*$') {
                if ($Matches[2] -eq $Asset.name) {
                    $ExpectedHash = $Matches[1].ToLowerInvariant()
                    break
                }
            }
        }
        if (-not $ExpectedHash) {
            throw "Checksum entry for '$($Asset.name)' not found in SHA256SUMS.txt."
        }
        $ActualHash = (Get-FileHash -Algorithm SHA256 -Path $ArchivePath).Hash.ToLowerInvariant()
        if ($ActualHash -ne $ExpectedHash) {
            throw "SHA256 verification failed for $($Asset.name): expected $ExpectedHash, got $ActualHash."
        }
        Write-Host "Verified SHA256 checksum."
    }

    $ExtractDir = Join-Path $TempDir "unpacked"
    New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null
    Write-Host "Extracting archive..."
    Expand-Archive -Path $ArchivePath -DestinationPath $ExtractDir -Force

    if (-not (Test-Path (Join-Path $ExtractDir "msh.exe"))) {
        throw "Archive verification failed: msh.exe not found in extracted package."
    }

    $AllowedEntries = @("msh.exe", "matlab-shell.exe", "msh", "matlab-shell", "_internal", ".matlab-shell-install")
    if (Test-Path $InstallDir) {
        if (-not (Test-Path $InstallDir -PathType Container)) {
            throw "Install path '$InstallDir' exists and is not a directory."
        }
        foreach ($item in (Get-ChildItem -Force -Path $InstallDir)) {
            if ($AllowedEntries -notcontains $item.Name.ToLowerInvariant()) {
                throw "Refusing to overwrite non-empty directory '$InstallDir' containing unrelated entry '$($item.Name)'. Use a dedicated subdirectory such as '$env:LOCALAPPDATA\matlab-shell\bin'."
            }
        }
        Remove-Item -Path $InstallDir -Recurse -Force
    }

    Write-Host "Installing to $InstallDir..."
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Get-ChildItem -Force -Path $ExtractDir | Copy-Item -Destination $InstallDir -Recurse -Force
    $MarkerPath = Join-Path $InstallDir ".matlab-shell-install"
    if (-not (Test-Path $MarkerPath)) {
        Set-Content -Path $MarkerPath -Value "matlab-shell" -Encoding UTF8
    }

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
