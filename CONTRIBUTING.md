# Contributing

Thanks for your interest in JellyFlam3 Server. This project is documentation-heavy and Pi-oriented — read the guides before large changes. Be excellent to each other — see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Where to start

| Audience | Start here |
|---|---|
| End user / viewer | [docs/USER_GUIDE_AND_RUNBOOK.md](docs/USER_GUIDE_AND_RUNBOOK.md) — Layer 1 |
| Operator / homelab | Same guide — Layer 2; install: [docs/phase2/09_PI_FROM_SCRATCH.md](docs/phase2/09_PI_FROM_SCRATCH.md) |
| Architecture | [docs/Pi5_Flam3_VoD_Pipeline.md](docs/Pi5_Flam3_VoD_Pipeline.md) (source of truth) |
| Feature work | [docs/README.md](docs/README.md) — phased guides 1–3 complete |
| Vocabulary | [docs/glossary.md](docs/glossary.md) |

## Development setup

```bash
git clone https://github.com/awuehler/jellyflam3-server.git
cd jellyflam3-server
pip install -r requirements.txt
python -m pytest tests/ -q
```

On a furnace Pi, also run `./scripts/healthcheck.sh` and (when flam3 is installed) `./scripts/smoke_render.sh`. Full contributor notes: [USER_GUIDE Layer 3](docs/USER_GUIDE_AND_RUNBOOK.md#layer-3--contributor).

## Pull requests

1. **Scope** — One logical change per PR; match existing style in the file you touch.
2. **Tests** — Run `python -m pytest tests/ -q`. CI must stay green (`.github/workflows/tests.yml`).
3. **Secrets** — Never commit `secrets.env`, filled `configs/jellyflam3.yaml`, API keys, or LAN-specific credentials. Use placeholders in docs (`192.168.X.Y`, `<RPi_IP_Address>`).
4. **Scripts** — New or renamed `scripts/*.{sh,py,ps1}` and `pipeline/*.py` CLI entrypoints need the executable bit (`./scripts/ensure_exec_bits.sh`).
5. **Docs** — If behavior changes, update the relevant phase guide or [USER_GUIDE_AND_RUNBOOK.md](docs/USER_GUIDE_AND_RUNBOOK.md). Architecture changes belong in `docs/Pi5_Flam3_VoD_Pipeline.md`.

## Reporting issues

Use GitHub Issues — choose **Bug report** or **Question** (templates under `.github/ISSUE_TEMPLATE/`). Include Pi hardware class (`16`/`08`/`04`), `git rev-parse --short HEAD`, client versions (Roku manifest / Kodi add-on), and `./scripts/healthcheck.sh` output when reporting runtime problems. See [SECURITY.md](SECURITY.md) for vulnerability reports.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
