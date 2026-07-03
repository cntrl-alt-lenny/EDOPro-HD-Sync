@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command "$c=Get-Content -LiteralPath '%~f0' -Raw; $m='#PS'+'START#'; $p=Join-Path $env:TEMP 'edopro-hd-sync-launcher.ps1'; Set-Content -LiteralPath $p -Value $c.Substring($c.IndexOf($m)); & $p; Remove-Item -LiteralPath $p -Force -EA SilentlyContinue"
echo.
pause
exit /b
#PSSTART#
$ErrorActionPreference = 'Stop'
$AppName = 'EDOPro-HD-Sync.exe'
$SupportDir = Join-Path $env:LOCALAPPDATA 'EDOPro-HD-Sync'
$Binary = Join-Path $SupportDir $AppName
$Api = 'https://api.github.com/repos/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest'
$UA = 'EDOPro-HD-Sync-Launcher'

New-Item -ItemType Directory -Force -Path $SupportDir | Out-Null
$InstalledFile = Join-Path $SupportDir 'binary_version.txt'

# One quick release check: used for the first download and to spot updates.
# When GitHub is unreachable the cached app still runs.
$rel = $null
try {
    $rel = Invoke-RestMethod -UseBasicParsing -UserAgent $UA -Uri $Api -TimeoutSec 15
} catch { }

# Update the cached app when a newer release is out.
if ((Test-Path -LiteralPath $Binary) -and $rel -and $rel.tag_name) {
    $installed = ''
    if (Test-Path -LiteralPath $InstalledFile) {
        $installed = (Get-Content -LiteralPath $InstalledFile -Raw).Trim()
    }
    if ($installed -ne $rel.tag_name) {
        Write-Host "A new version ($($rel.tag_name)) is available - updating..."
        Remove-Item -LiteralPath $Binary -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path -LiteralPath $Binary)) {
    Write-Host 'Setting up EDOPro HD Sync...'
    if (-not $rel) {
        Write-Host 'Could not reach GitHub. Check your internet connection.'
        exit 1
    }
    $zip = $rel.assets | Where-Object { $_.name -like 'EDOPro-HD-Sync-Windows-v*.zip' } | Select-Object -First 1
    $sha = $rel.assets | Where-Object { $_.name -like 'EDOPro-HD-Sync-Windows-v*.zip.sha256' } | Select-Object -First 1
    if (-not $zip) {
        Write-Host 'Could not find the latest Windows download in the release.'
        exit 1
    }
    $tmpZip = Join-Path $env:TEMP 'EDOPro-HD-Sync.zip'
    Invoke-WebRequest -UseBasicParsing -UserAgent $UA -Uri $zip.browser_download_url -OutFile $tmpZip

    if ($sha) {
        try {
            $shaText = (Invoke-WebRequest -UseBasicParsing -UserAgent $UA -Uri $sha.browser_download_url).Content
            $expected = (($shaText -split '\s+') | Select-Object -First 1).Trim().ToLower()
            $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $tmpZip).Hash.ToLower()
            if ($expected -and ($expected -ne $actual)) {
                Write-Host 'Checksum mismatch - the download may be corrupted or tampered with.'
                Remove-Item -LiteralPath $tmpZip -Force -ErrorAction SilentlyContinue
                exit 1
            }
            Write-Host 'Checksum verified.'
        } catch {
            Write-Host 'Could not verify the checksum - continuing.'
        }
    }

    $extract = Join-Path $env:TEMP 'EDOPro-HD-Sync-extract'
    if (Test-Path -LiteralPath $extract) { Remove-Item -LiteralPath $extract -Recurse -Force }
    Expand-Archive -LiteralPath $tmpZip -DestinationPath $extract -Force
    $exe = Get-ChildItem -LiteralPath $extract -Recurse -Filter $AppName | Select-Object -First 1
    if (-not $exe) {
        Write-Host 'Could not find the app after unzip.'
        exit 1
    }
    Copy-Item -LiteralPath $exe.FullName -Destination $Binary -Force
    Set-Content -LiteralPath $InstalledFile -Value $rel.tag_name
    Remove-Item -LiteralPath $tmpZip -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue
}

# Remove the 'downloaded from the internet' mark so SmartScreen does not block it.
Unblock-File -LiteralPath $Binary -ErrorAction SilentlyContinue

# The app asks for your EDOPro folder the first time and remembers it.
& $Binary --no-pause
