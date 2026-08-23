# Purpose: Build installable Kodi screensaver zip (Phase 3 guide 02).
#
# Requirements: PowerShell 5.1+; python on PATH for ZIP_STORED packaging.
#
# Usage: .\scripts\package_kodi_screensaver.ps1 [OutPath]
#
# When to run: Before Kodi install-from-zip. Default: dist\screensaver.jellyflam3.zip
# Success: Zip root is screensaver.jellyflam3/ (addon.xml at that prefix).
# Docs: docs/phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md

param(
  [string]$OutPath = ""
)
$Root = Split-Path -Parent $PSScriptRoot
$AddonId = "screensaver.jellyflam3"
$Src = Join-Path $Root "kodi-screensaver\$AddonId"
$StageRoot = Join-Path $Root "dist\kodi-stage"
$Stage = Join-Path $StageRoot $AddonId
if (-not $OutPath) { $OutPath = Join-Path $Root "dist\screensaver.jellyflam3.zip" }

if (-not (Test-Path (Join-Path $Src "addon.xml"))) {
  throw "missing addon: $Src\addon.xml"
}

python (Join-Path $Root "scripts\build_kodi_screensaver_assets.py")

New-Item -ItemType Directory -Force -Path (Split-Path $OutPath) | Out-Null
if (Test-Path $OutPath) { Remove-Item -Force $OutPath }
if (Test-Path $StageRoot) { Remove-Item -Recurse -Force $StageRoot }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

Get-ChildItem -Path $Src -Recurse -File | Where-Object {
  $_.Name -ne ".gitkeep" -and
  $_.Extension -ne ".pyc" -and
  ($_.FullName -notmatch '[\\/]__pycache__[\\/]') -and
  ($_.FullName -notmatch '[\\/]posters[\\/]')
} | ForEach-Object {
  $rel = $_.FullName.Substring($Src.Length).TrimStart("\", "/")
  $dest = Join-Path $Stage $rel
  New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
  Copy-Item -Force $_.FullName $dest
}

python (Join-Path $Root "scripts\client_pack_presets.py") prepare --kodi-settings (Join-Path $Stage "resources\settings.xml") 2>$null | Out-Null

$stageFwd = ($StageRoot -replace '\\', '/')
$outFwd = ($OutPath -replace '\\', '/')
@"
import zipfile
from pathlib import Path
stage_root = Path("$stageFwd")
out = Path("$outFwd")
addon_id = "$AddonId"
skip = {".gitkeep", ".DS_Store"}
with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
    for p in (stage_root / addon_id).rglob("*"):
        if not p.is_file() or p.name in skip or p.suffix == ".pyc":
            continue
        if "__pycache__" in p.parts or "posters" in p.parts:
            continue
        zf.write(p, p.relative_to(stage_root).as_posix())
print(out)
"@ | python -
Write-Host "Kodi screensaver package: $OutPath"
Write-Host "Install from zip in Kodi, then Settings -> Interface -> Screensaver -> JellyFlam3 Dreams"
Get-Item $OutPath | Format-List FullName, Length
