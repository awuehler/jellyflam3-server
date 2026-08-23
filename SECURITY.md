# Security policy

## Supported versions

| Version | Supported |
|---|---|
| `master` (latest) | Yes |
| Tagged releases | Yes, while listed on [GitHub Releases](https://github.com/awuehler/jellyflam3-server/releases) |
| Older tags | Best-effort |

## Reporting a vulnerability

**Do not** open a public GitHub issue for security-sensitive reports (exposed API keys, RCE, auth bypass on display-sink, share-security bypass, etc.).

Instead:

1. Use [GitHub private vulnerability reporting](https://github.com/awuehler/jellyflam3-server/security/advisories/new) if enabled, **or**
2. Open a minimal issue asking for a private contact channel.

Include steps to reproduce, affected component (`pipeline/`, Roku channel, Kodi add-on, scripts), and impact.

## Secrets hygiene (operators)

- `secrets.env` and filled `configs/jellyflam3.yaml` are **gitignored** and **host-local** — never commit, scp between Pis, or paste into issues.
- Rotate Jellyfin API keys if either file was ever committed or shared.
- Furnace-built Roku/Kodi zips embed LAN Jellyfin credentials — distribute only on your LAN.
- Tailscale pre-auth keys (`TS_AUTHKEY`) and display-sink tokens must stay out of git and public logs.

See [docs/phase1/02_REPO_AND_CONFIG.md](docs/phase1/02_REPO_AND_CONFIG.md) and [docs/phase3/08_JELLYFIN_ID_DUMP.md](docs/phase3/08_JELLYFIN_ID_DUMP.md).

## Out of scope

- Jellyfin, Syncthing, Tailscale, or Roku platform vulnerabilities (report upstream).
- Social engineering or physical access to your Pi/Roku.
