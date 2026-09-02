# Purpose: Copy catalog sheep MP4s from the furnace fleet to this Windows host.
#
# Requirements: OpenSSH scp/ssh; BatchMode keys as jellyflam3@ each Pi.
#
# Usage (from repo root or any cwd):
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/scrape_fleet_sheep.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/scrape_fleet_sheep.ps1 -Dest "$env:USERPROFILE\Downloads\jellyflam3-sheep"
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/scrape_fleet_sheep.ps1 -DryRun
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/scrape_fleet_sheep.ps1 -Force
#
# When to run: Operator wants local copies of rendered flock MP4s (not posters).
# Success: Each host's /media/sheep/by-generation/**/*.mp4 lands under Dest\<host>\...
# Docs: docs/USER_GUIDE_AND_RUNBOOK.md (operator workstation)
#
# Assumptions: Catalog lives at /media/sheep/by-generation (not _refactor-preview).
# Fleet IPs: JELLYFLAM3_FLEET_IP_16A / _08A / _04A, else lab defaults below.
# Skip existing files unless -Force.

param(
  [string]$Dest = "",
  [switch]$DryRun,
  [switch]$Force
)

$ErrorActionPreference = "Stop"

function Get-FleetIp([string]$hostId, [string]$fallback) {
  $envName = "JELLYFLAM3_FLEET_IP_$($hostId.ToUpper())"
  $fromEnv = [Environment]::GetEnvironmentVariable($envName)
  if ($fromEnv) { return $fromEnv }
  return $fallback
}

if (-not $Dest) {
  $Dest = Join-Path $env:USERPROFILE "Downloads\jellyflam3-sheep"
}

$hosts = [ordered]@{
  "16a" = (Get-FleetIp "16a" "192.168.156.162")
  "08a" = (Get-FleetIp "08a" "192.168.156.163")
  "04a" = (Get-FleetIp "04a" "192.168.156.164")
}
$remoteRoot = "/media/sheep/by-generation"

New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Write-Host "Dest $Dest"
if ($DryRun) { Write-Host "DryRun (list only)" }

$copied = 0
$skipped = 0
$failed = 0

foreach ($name in $hosts.Keys) {
  $ip = $hosts[$name]
  Write-Host "=== $name $ip ==="
  $list = & ssh -o BatchMode=yes -o ConnectTimeout=12 "jellyflam3@$ip" "find $remoteRoot -type f -name '*.mp4' -print"
  if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL ssh/find on $name"
    $failed++
    continue
  }
  $paths = @($list | Where-Object { $_ -and $_.Trim() })
  Write-Host ("{0} mp4 on {1}" -f $paths.Count, $name)
  foreach ($remote in $paths) {
    $rel = $remote.Substring($remoteRoot.Length).TrimStart("/")
    $relWin = $rel -replace "/", "\"
    $local = Join-Path (Join-Path $Dest $name) $relWin
    if ((Test-Path $local) -and -not $Force) {
      Write-Host "skip $name/$rel"
      $skipped++
      continue
    }
    if ($DryRun) {
      Write-Host "would $name/$rel"
      $copied++
      continue
    }
    $parent = Split-Path $local
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    & scp -o BatchMode=yes -o ConnectTimeout=12 "jellyflam3@${ip}:$remote" $local
    if ($LASTEXITCODE -ne 0) {
      Write-Host "FAIL scp $name/$rel"
      $failed++
      continue
    }
    Write-Host "ok $name/$rel"
    $copied++
  }
}

Write-Host ("DONE copied_or_listed={0} skipped={1} failed={2}" -f $copied, $skipped, $failed)
if ($failed -gt 0) { exit 1 }
exit 0
