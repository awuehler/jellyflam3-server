# Purpose: Fleet matrix for Phase 3 guide 05 shared sheep security lab smoke.
#
# Requirements: SSH to 16a/08a/04a as jellyflam3; tip with scripts/lab_smoke05_local.py.
#
# Usage (from Windows operator machine, repo root or any cwd):
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/lab_smoke05_fleet.ps1
#
# When to run: After share_security changes, or as Phase 3 RC regression for guide 05.
# Success: PASS 24/24 (all publisher→receiver pairs × pathways A–D).
# Docs: docs/phase3/05_SHARED_SHEEP_SECURITY.md
# Assumptions: Manual scp land (not Syncthing). Pedigree throwaways. Cross-trust pubs.
# Pathways: A happy Ed25519, B tamper, C missing sidecar, D SHA-256 fallback.
# Pairs: 04a→08a/16a, 08a→04a/16a, 16a→04a/08a.
# Fleet IPs: set JELLYFLAM3_FLEET_IP_16A / _08A / _04A, or edit $hosts below.

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
function Get-FleetIp([string]$hostId) {
  $envName = "JELLYFLAM3_FLEET_IP_$($hostId.ToUpper())"
  $fromEnv = [Environment]::GetEnvironmentVariable($envName)
  if ($fromEnv) { return $fromEnv }
  return "<RPi_IP_$hostId>"
}
$hosts = [ordered]@{
  "16a" = (Get-FleetIp "16a")
  "08a" = (Get-FleetIp "08a")
  "04a" = (Get-FleetIp "04a")
}
$remoteRoot = "/opt/jellyflam3-server"
$localWork = Join-Path $RepoRoot "var\lab_smoke05_xfer"
New-Item -ItemType Directory -Force -Path $localWork | Out-Null

function Invoke-Pi([string]$ip, [string]$remoteCmd) {
  # PYTHONPATH belt-and-suspenders; lab_smoke05_local.py also inserts repo root via __file__.
  ssh -o BatchMode=yes "jellyflam3@$ip" "cd $remoteRoot && PYTHONPATH=$remoteRoot $remoteCmd"
}

function Scp-To([string]$ip, [string]$local, [string]$remote) {
  scp -o BatchMode=yes $local "jellyflam3@${ip}:$remote"
}

function Scp-From([string]$ip, [string]$remote, [string]$local) {
  scp -o BatchMode=yes "jellyflam3@${ip}:$remote" $local
}

Write-Host "=== Setup keys on each Pi (tip must already include scripts/lab_smoke05_local.py) ==="
foreach ($name in $hosts.Keys) {
  $ip = $hosts[$name]
  Write-Host "--- setup $name ---"
  Invoke-Pi $ip "python3 scripts/lab_smoke05_local.py setup"
  New-Item -ItemType Directory -Force -Path "$localWork\$name" | Out-Null
  Scp-From $ip "$remoteRoot/var/share_security/ed25519.pub" "$localWork\$name\ed25519.pub"
}

Write-Host "=== Exchange trust keys ==="
foreach ($recv in $hosts.Keys) {
  $rip = $hosts[$recv]
  foreach ($pub in $hosts.Keys) {
    if ($pub -eq $recv) { continue }
    Scp-To $rip "$localWork\$pub\ed25519.pub" "/tmp/${pub}.pub"
    Invoke-Pi $rip "python3 scripts/lab_smoke05_local.py trust /tmp/${pub}.pub --name $pub"
  }
}

$pairs = @(
  @{ Pub = "04a"; Recv = "08a" },
  @{ Pub = "04a"; Recv = "16a" },
  @{ Pub = "08a"; Recv = "04a" },
  @{ Pub = "08a"; Recv = "16a" },
  @{ Pub = "16a"; Recv = "04a" },
  @{ Pub = "16a"; Recv = "08a" }
)
$paths = @("A", "B", "C", "D")
$results = @()

foreach ($pair in $pairs) {
  $pub = $pair.Pub
  $recv = $pair.Recv
  $pip = $hosts[$pub]
  $rip = $hosts[$recv]
  foreach ($path in $paths) {
    $stem = "smoke05_${pub}_${recv}_${path}"
    $xfer = "$localWork\$stem"
    New-Item -ItemType Directory -Force -Path $xfer | Out-Null
    Write-Host "=== $pub -> $recv path $path ($stem) ==="

    $row = [ordered]@{
      publisher = $pub
      receiver = $recv
      path = $path
      stem = $stem
      expected = switch ($path) {
        "A" { "promote (ed25519 verified) -> genomes/inbox" }
        "B" { "quarantine (tamper) -> genomes/quarantine" }
        "C" { "quarantine (missing sidecar) -> genomes/quarantine" }
        "D" { "promote (sha256 fallback) -> genomes/inbox" }
      }
    }

    try {
      Invoke-Pi $pip "python3 scripts/lab_smoke05_local.py cleanup --name $stem" | Out-Null
      Invoke-Pi $rip "python3 scripts/lab_smoke05_local.py cleanup --name $stem" | Out-Null

      $remoteOut = "/tmp/$stem"
      Invoke-Pi $pip "rm -rf $remoteOut && mkdir -p $remoteOut"
      $pubJson = Invoke-Pi $pip "python3 scripts/lab_smoke05_local.py publish --path $path --name $stem --out-dir $remoteOut"
      $row.publish_raw = ($pubJson | Out-String).Trim()
      try { $row.publish = $pubJson | ConvertFrom-Json } catch { $row.publish_parse_error = $_.Exception.Message }

      Get-ChildItem $xfer -ErrorAction SilentlyContinue | Remove-Item -Force
      scp -o BatchMode=yes "jellyflam3@${pip}:${remoteOut}/*" "$xfer/"
      $remoteIn = "/tmp/${stem}_in"
      Invoke-Pi $rip "rm -rf $remoteIn && mkdir -p $remoteIn"
      scp -o BatchMode=yes "$xfer/*" "jellyflam3@${rip}:${remoteIn}/"

      $recvJson = Invoke-Pi $rip "python3 scripts/lab_smoke05_local.py receive --path $path --name $stem --inbox-src $remoteIn"
      $row.receive_raw = ($recvJson | Out-String).Trim()
      try { $row.receive = $recvJson | ConvertFrom-Json } catch { $row.receive_parse_error = $_.Exception.Message }

      $pubOk = $false
      $recvOk = $false
      if ($row.publish) { $pubOk = [bool]$row.publish.ok }
      if ($row.receive) { $recvOk = [bool]$row.receive.ok }
      $row.publish_ok = $pubOk
      $row.receive_ok = $recvOk
      $row.pass = ($pubOk -and $recvOk)

      if ($row.receive) {
        $row.observed = "action=$($row.receive.observed_action); inbox=$($row.receive.observed_inbox); quarantine=$($row.receive.observed_quarantine); reason=$($row.receive.quarantine_reason); sec=$($row.receive.share_security.result)/$($row.receive.share_security.reason)"
      } else {
        $row.observed = "receive parse failed: $($row.receive_raw)"
      }
      if ($row.publish) {
        $row.publish_observed = "action=$($row.publish.action); alg=$($row.publish.observed_alg); sec=$($row.publish.share_security.result)/$($row.publish.share_security.reason)"
      }
    }
    catch {
      $row.pass = $false
      $row.error = $_.Exception.Message
      $row.observed = "EXCEPTION: $($_.Exception.Message)"
    }
    finally {
      Invoke-Pi $pip "python3 scripts/lab_smoke05_local.py cleanup --name $stem" | Out-Null
      Invoke-Pi $rip "python3 scripts/lab_smoke05_local.py cleanup --name $stem" | Out-Null
    }

    $results += [pscustomobject]$row
    $mark = if ($row.pass) { "PASS" } else { "FAIL" }
    Write-Host "  -> $mark | expected: $($row.expected) | observed: $($row.observed)"
  }
}

$reportPath = Join-Path $localWork "report.json"
$results | ConvertTo-Json -Depth 8 | Set-Content -Path $reportPath -Encoding utf8
Write-Host "=== SUMMARY ==="
$pass = ($results | Where-Object { $_.pass }).Count
$fail = ($results | Where-Object { -not $_.pass }).Count
Write-Host "PASS=$pass FAIL=$fail TOTAL=$($results.Count)"
Write-Host "Report: $reportPath"
$results | Select-Object publisher, receiver, path, pass, expected, observed, publish_observed | Format-Table -AutoSize -Wrap
if ($fail -gt 0) {
  Write-Host "FAIL: $fail pathway(s) did not meet expected outcome"
  exit 1
}
exit 0
