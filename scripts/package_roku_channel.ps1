# Purpose: Build a sideloadable Roku channel zip for the Developer Application Installer.
#
# Requirements: PowerShell 5.1 or 7+; .NET System.IO.Compression.FileSystem.
#
# Usage: .\scripts\package_roku_channel.ps1 [OutPath]
#
# When to run: Windows operator packaging before sideload / Phase 3 RC. Default: dist\jellyflam3-roku.zip
# Success: Zip entries at archive root with forward-slash paths (manifest, source/, …).
# Docs: docs/phase2/04_ROKU_CHANNEL_POLISH.md
#
# Assumptions: roku-channel\ has manifest, source\, components\, images\; zip entry paths use /.
#
# Why ZipFile (not Compress-Archive): Roku requires forward-slash entry paths at archive root.
# Compress-Archive is fine on PowerShell 7+ (entries like source/main.brs) but on Windows
# PowerShell 5.1 it stores backslashes (source\main.brs), which breaks sideload. ZipFile
# keeps POSIX-style paths on both hosts. Compress-Archive also still uses .NET under the hood.

param(
  [string]$OutPath = ""
)
$Root = Split-Path -Parent $PSScriptRoot
if (-not $OutPath) { $OutPath = Join-Path $Root "dist\jellyflam3-roku.zip" }
$Channel = Join-Path $Root "roku-channel"
New-Item -ItemType Directory -Force -Path (Split-Path $OutPath) | Out-Null
if (Test-Path $OutPath) { Remove-Item -Force $OutPath }

python (Join-Path $Root "scripts\client_pack_presets.py") prepare --roku-registry (Join-Path $Channel "registry") 2>$null | Out-Null

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($OutPath, "Create")
# Add one file into the open zip under the given archive entry path.
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
Get-Item $OutPath | Format-List FullName, Length
