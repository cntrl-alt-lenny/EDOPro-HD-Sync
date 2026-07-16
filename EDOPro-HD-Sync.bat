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
$Binary = Join-Path $SupportDir $AppName
$InstalledFile = Join-Path $SupportDir 'binary_version.txt'
$Api = 'https://api.github.com/repos/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest'
$UA = 'EDOPro-HD-Sync-Launcher'

New-Item -ItemType Directory -Force -Path $SupportDir | Out-Null

# One quick release check: used for the first download and to spot updates.
# When GitHub is unreachable the cached app still runs.
$rel = $null
try {
    $rel = Invoke-RestMethod -UseBasicParsing -UserAgent $UA -Uri $Api -TimeoutSec 15
} catch { }

function Install-App {
    # Download + verify into a scratch folder; the existing app is replaced
    # only after every step succeeds, so a failed update never breaks a
    # working install.
    if (-not $rel) { Write-Host 'Could not reach GitHub.'; return $false }
    $zip = $rel.assets | Where-Object { $_.name -like 'EDOPro-HD-Sync-Windows-v*.zip' } | Select-Object -First 1
    $sha = $rel.assets | Where-Object { $_.name -like 'EDOPro-HD-Sync-Windows-v*.zip.sha256' } | Select-Object -First 1
    if (-not $zip) { Write-Host 'Could not find the latest Windows download in the release.'; return $false }

    $work = Join-Path $env:TEMP ('EDOPro-HD-Sync-new-' + [System.IO.Path]::GetRandomFileName())
    try {
        New-Item -ItemType Directory -Force -Path $work | Out-Null
        $tmpZip = Join-Path $work 'app.zip'
        Invoke-WebRequest -UseBasicParsing -UserAgent $UA -Uri $zip.browser_download_url -OutFile $tmpZip

        if ($sha) {
            try {
                $shaRaw = (Invoke-WebRequest -UseBasicParsing -UserAgent $UA -Uri $sha.browser_download_url).Content
                # GitHub serves .sha256 as octet-stream: .Content is byte[] in PS 5.1.
                if ($shaRaw -is [byte[]]) { $shaText = [System.Text.Encoding]::ASCII.GetString($shaRaw) } else { $shaText = [string]$shaRaw }
                $expected = (($shaText -split '\s+') | Select-Object -First 1).Trim().ToLower()
                $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $tmpZip).Hash.ToLower()
                if ($expected -and ($expected -ne $actual)) {
                    Write-Host 'Checksum mismatch - the download may be corrupted or tampered with.'
                    return $false
                }
                Write-Host 'Checksum verified.'
            } catch {
                Write-Host 'Could not verify the checksum - continuing.'
            }
        }

        $extract = Join-Path $work 'unzipped'
        Expand-Archive -LiteralPath $tmpZip -DestinationPath $extract -Force
        $exe = Get-ChildItem -LiteralPath $extract -Recurse -Filter $AppName | Select-Object -First 1
        if (-not $exe) { Write-Host 'Could not find the app after unzip.'; return $false }

        # The old app is replaced only now, after everything succeeded -
        # staged beside the target so the final step is a same-volume rename.
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

if (-not (Test-Path -LiteralPath $Binary)) {
    Write-Host 'Setting up EDOPro HD Sync (first run)...'
    if (-not (Install-App)) {
        Write-Host 'Setup failed. Check your internet connection and try again.'
        exit 1
    }
} elseif ($rel -and $rel.tag_name) {
    $installed = ([string](Get-Content -LiteralPath $InstalledFile -Raw -ErrorAction SilentlyContinue)).Trim()
    if ($installed -ne $rel.tag_name) {
        Write-Host ("A new version (" + $rel.tag_name + ") is available - updating...")
        if (Install-App) {
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
