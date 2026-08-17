@echo off
setlocal
set "HDSYNC_SELF=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$c=Get-Content -LiteralPath $env:HDSYNC_SELF -Raw; $m='#PS'+'START#'; $p=Join-Path $env:TEMP 'edopro-hd-sync-launcher.ps1'; Set-Content -LiteralPath $p -Value $c.Substring($c.IndexOf($m)); & $p; Remove-Item -LiteralPath $p -Force -EA SilentlyContinue"
echo.
pause
exit /b
#PSSTART#
$ErrorActionPreference = 'Stop'
$AppName = 'EDOPro-HD-Sync.exe'
$SupportDir = Join-Path $env:LOCALAPPDATA 'EDOPro-HD-Sync'
$AppDir = Join-Path $SupportDir 'app'
$Binary = Join-Path $AppDir $AppName
$InstalledFile = Join-Path $SupportDir 'binary_version.txt'
$Api = 'https://api.github.com/repos/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest'
$UA = 'EDOPro-HD-Sync-Launcher'

# The launcher always runs the copy it manages in LOCALAPPDATA, so updates
# work the same wherever this file ends up. The app shipped next to it (in
# the extracted zip) is used to install without downloading anything.
$SelfDir = Split-Path -Parent $env:HDSYNC_SELF
$BundledDir = Join-Path $SelfDir 'app'
$Bundled = Join-Path $BundledDir $AppName
$BundledVersionFile = Join-Path $BundledDir 'version.txt'

New-Item -ItemType Directory -Force -Path $SupportDir | Out-Null

# One quick release check: used to spot updates (and to install when the app
# was not shipped alongside). Silent when GitHub is unreachable.
$rel = $null
try {
    $rel = Invoke-RestMethod -UseBasicParsing -UserAgent $UA -Uri $Api -TimeoutSec 15
} catch { }

function Swap-InAppDir {
    # Replace the installed app folder, keeping the old copy until the swap
    # succeeds so a failure can never leave a half-installed app.
    param([string]$Source)
    $backup = $AppDir + '.old'
    try {
        Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $AppDir) { Move-Item -LiteralPath $AppDir -Destination $backup -Force }
        try {
            Move-Item -LiteralPath $Source -Destination $AppDir -Force
        } catch {
            if (Test-Path -LiteralPath $backup) { Move-Item -LiteralPath $backup -Destination $AppDir -Force }
            throw
        }
        Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue
        return $true
    } catch {
        return $false
    }
}

function Install-FromRelease {
    # Download + verify into a scratch folder; the existing app is replaced
    # only after every step succeeds, so a failed update never breaks a
    # working install.
    if (-not $rel) { Write-Host 'Could not reach GitHub.'; return $false }
    $zip = $rel.assets | Where-Object { $_.name -like 'EDOPro-HD-Sync-Windows-v*.zip' } | Select-Object -First 1
    if (-not $zip) { Write-Host 'Could not find the latest Windows download in the release.'; return $false }

    $work = Join-Path $env:TEMP ('EDOPro-HD-Sync-new-' + [System.IO.Path]::GetRandomFileName())
    try {
        New-Item -ItemType Directory -Force -Path $work | Out-Null
        $tmpZip = Join-Path $work 'app.zip'
        Invoke-WebRequest -UseBasicParsing -UserAgent $UA -Uri $zip.browser_download_url -OutFile $tmpZip

        # GitHub publishes the SHA-256 of every asset in its release API.
        if ($zip.digest -and ($zip.digest -like 'sha256:*')) {
            $expected = ($zip.digest -replace '^sha256:', '').Trim().ToLower()
            $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $tmpZip).Hash.ToLower()
            if ($expected -ne $actual) {
                Write-Host 'Checksum mismatch - the download may be corrupted or tampered with.'
                return $false
            }
            Write-Host 'Download verified.'
        }

        $extract = Join-Path $work 'unzipped'
        Expand-Archive -LiteralPath $tmpZip -DestinationPath $extract -Force
        $exe = Get-ChildItem -LiteralPath $extract -Recurse -Filter $AppName | Select-Object -First 1
        if (-not $exe) { Write-Host 'Could not find the app inside the download.'; return $false }

        # Staged beside the target so the final step is a same-volume rename.
        $staged = $Binary + '.new'
        Copy-Item -LiteralPath $exe.FullName -Destination $staged -Force
        Move-Item -LiteralPath $staged -Destination $Binary -Force
        Set-Content -LiteralPath $InstalledFile -Value $rel.tag_name
        return $true
    } catch {
        Write-Host ('Download failed: ' + $_.Exception.Message)
        return $false
    } finally {
        Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Install-FromBundle {
    # Install the app that shipped next to this launcher - no download needed.
    try {
        $staged = $Binary + '.new'
        Copy-Item -LiteralPath $Bundled -Destination $staged -Force
        Move-Item -LiteralPath $staged -Destination $Binary -Force
        $bundledVersion = ''
        if (Test-Path -LiteralPath $BundledVersionFile) {
            $bundledVersion = ([string](Get-Content -LiteralPath $BundledVersionFile -Raw -ErrorAction SilentlyContinue)).Trim()
        }
        Set-Content -LiteralPath $InstalledFile -Value $bundledVersion
        return $true
    } catch {
        Write-Host ('Could not install the app: ' + $_.Exception.Message)
        return $false
    }
}

if (-not (Test-Path -LiteralPath $Binary)) {
    Write-Host 'Setting up EDOPro HD Sync...'
    $ok = $false
    if (Test-Path -LiteralPath $Bundled) { $ok = Install-FromBundle }
    if (-not $ok) { $ok = Install-FromRelease }
    if (-not $ok) {
        Write-Host 'Setup failed. Check your internet connection and try again.'
        exit 1
    }
} elseif ($rel -and $rel.tag_name) {
    $installed = ([string](Get-Content -LiteralPath $InstalledFile -Raw -ErrorAction SilentlyContinue)).Trim()
    if ($installed -ne $rel.tag_name) {
        Write-Host ("A new version (" + $rel.tag_name + ") is available - updating...")
        if (Install-FromRelease) {
            Write-Host ('Updated to ' + $rel.tag_name + '.')
        } else {
            Write-Host 'Update failed - keeping the current version for now.'
        }
    }
}

# Remove the 'downloaded from the internet' mark so SmartScreen does not block it.
Unblock-File -LiteralPath $Binary -ErrorAction SilentlyContinue

# The app asks for your EDOPro folder the first time and remembers it.
& $Binary --no-pause
