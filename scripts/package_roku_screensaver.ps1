# Purpose: Build sideloadable JellyFlam3 Roku Screensaver zip (Phase 3 guide 01).
#
# Requirements: PowerShell 5.1+; .NET ZipFile (forward-slash entries).
#
# Usage: .\scripts\package_roku_screensaver.ps1 [OutPath]
#
# When to run: Before Roku Screensaver sideload (Settings / Theme / Screensavers, not Home).
# Success: dist\jellyflam3-screensaver.zip with manifest at archive root.
# Note: Replaces the VoD channel sideload on that device (one sideload at a time).
# Docs: docs/phase3/01_SCREENSAVERS_AND_STILLS.md

param(
  [string]$OutPath = ""
)
$Root = Split-Path -Parent $PSScriptRoot
if (-not $OutPath) { $OutPath = Join-Path $Root "dist\jellyflam3-screensaver.zip" }
$Channel = Join-Path $Root "roku-screensaver"
New-Item -ItemType Directory -Force -Path (Split-Path $OutPath) | Out-Null
if (Test-Path $OutPath) { Remove-Item -Force $OutPath }

python (Join-Path $Root "scripts\client_pack_presets.py") prepare --roku-registry (Join-Path $Channel "registry") 2>$null | Out-Null

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($OutPath, "Create")
function Add-File($full, $entry) {
  [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $full, $entry, "Optimal") | Out-Null
}
Add-File (Join-Path $Channel "manifest") "manifest"
$folders = @("source", "components", "images")
if (Test-Path (Join-Path $Channel "registry\jellyflam3-presets.json")) {
  $folders += "registry"
}
foreach ($folder in $folders) {
  $dir = Join-Path $Channel $folder
  if (-not (Test-Path $dir)) { continue }
  Get-ChildItem -Path $dir -Recurse -File | Where-Object { $_.Name -ne ".gitkeep" } | ForEach-Object {
    $rel = $_.FullName.Substring($Channel.Length + 1).Replace("\", "/")
    Add-File $_.FullName $rel
  }
}
$zip.Dispose()
Write-Host "Sideload package: $OutPath"
Write-Host "NOTE: Roku allows one sideload at a time - this zip replaces jellyflam3-roku.zip on that device."
Write-Host "      Pick under Settings / Theme / Screensavers (not Home). Re-sideload VoD when done."
Get-Item $OutPath | Format-List FullName, Length
