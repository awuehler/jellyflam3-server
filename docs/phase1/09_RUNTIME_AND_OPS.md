# 09 — Runtime and ops

## Boundary

Production runtime on the Pi — not feature development.

## Install path

Unit files assume **`/opt/jellyflam3-server`**. If the repo lives elsewhere (e.g. `~/GitHub/jellyflam3-server`), symlink once:

```bash
sudo ln -sfn /home/jellyflam3/GitHub/jellyflam3-server /opt/jellyflam3-server
# Requires secrets.env + configs/jellyflam3.yaml under that tree
ls /opt/jellyflam3-server/secrets.env /opt/jellyflam3-server/configs/jellyflam3.yaml
```

`status=200/CHDIR` from systemd means `WorkingDirectory` is missing — almost always this symlink/path step was skipped.

```bash
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now jellyflam3-idlegate jellyflam3-worker
# Guide 04 F — per-screen TV display profile sink (port 8791; accepts Roku FormatJson lowercase keys)
sudo mkdir -p /var/lib/jellyflam3/display_profiles
sudo chown jellyflam3:jellyflam3 /var/lib/jellyflam3/display_profiles
sudo systemctl enable --now jellyflam3-display-sink
systemctl is-active jellyflam3-worker jellyflam3-idlegate jellyflam3-display-sink
# python3 -m pipeline.display_profiles list
```

## Ops scripts

Git tracks the executable bit on CLI tools: `scripts/*.{sh,py,ps1}` and `pipeline/*.py` are `100755`; `tests/**` are not. Refresh with `./scripts/ensure_exec_bits.sh` (or `--check`). Deploy to the Pi via `git pull` (not scp of a Windows working tree) so LF line endings and exec bits stay intact; verify with `./scripts/ensure_exec_bits.sh --check`.

```bash
cd /opt/jellyflam3-server

# Sheep catalog perms (2775 dirs / 664 files) so Jellyfin can write .trickplay
python3 -m pipeline.media_layout --config configs/jellyflam3.yaml

# Full backup: config + secrets + genomes + /media/sheep
./scripts/backup.sh
# Config/secrets only
./scripts/backup.sh --config-only

./scripts/healthcheck.sh              # mounts, library disk WARN/BAD, systemd units, idle-gate, tools
./scripts/perf_healthcheck.sh         # layout/thermals + disk microbench
./scripts/perf_healthcheck.sh --quick
./scripts/status_report.sh            # load, flock/inbox, thermals, top procs snapshot
./scripts/status_report.sh --json     # same report as JSON
```

Validated on `rpi-jellyflam3-16a` (formerly lab `rpi-jellyflam3-01`; 2026-07-28 / reboot 2026-07-28 19:47 PDT):

- Backup → `/var/lib/jellyflam3/backups/jellyflam3-*.tar.gz` (~33 MiB with current flock)
- `healthcheck.sh` exit 0 (worker, idlegate, jellyfin active)
- `perf_healthcheck.sh` FAIL=0 (WARN may include no zram; IO scratch ~700+ MB/s, sheep ~280+ MB/s)
- Cold reboot: all three units `active` within ~1 min; `throttled=0x0`; healthcheck exit 0

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `deploy/systemd/jellyflam3-worker.service` | deploy | Worker under `/opt/jellyflam3-server` |
| `deploy/systemd/jellyflam3-idlegate.service` | deploy | Idle-gate unit |
| `deploy/systemd/jellyflam3-display-sink.service` | deploy | Per-screen display profile sink (:8791) |
| `scripts/backup.sh` | script | Config / secrets / genomes / flock tarball |
| `scripts/healthcheck.sh` | script | Mounts, library disk, units, idle-gate, tools |
| `scripts/perf_healthcheck.sh` | script | Thermals + disk microbench |
| `scripts/status_report.sh` | script | Load, flock/inbox, top-procs snapshot |
| `scripts/ensure_exec_bits.sh` | script | Maintain git `100755` on CLI tools |
| `pipeline/media_layout.py` | pipeline | Catalog perms on worker start / ops |
| `/opt/jellyflam3-server` | deploy | Canonical install symlink / WorkingDirectory |

## Exit criteria

- [x] Cold reboot → services healthy (`jellyflam3-worker`, `jellyflam3-idlegate`, `jellyfin`)
- [x] Backup tarball works
- [x] `healthcheck.sh` exits 0 when healthy
- [x] `perf_healthcheck.sh` reports no FAIL on target Pi
