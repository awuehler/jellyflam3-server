"""Ops/script contracts for the end-to-end furnace (RC threshold).

These are not live cron runs. They keep script headers, crontab examples, PATH
fixes, and docs from drifting the way 02:00 vs 05:11 / 11-day vs ~10-day did.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

PATH_EXPORT = 'export PATH="/usr/local/bin'


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_cron_wrappers_prepend_usr_local_bin():
    for name in ("cron_breed_idle.sh", "cron_archive_seed.sh"):
        text = _read(f"scripts/{name}")
        assert PATH_EXPORT in text, f"{name} must prepend /usr/local/bin for cron PATH"


def test_health_bringup_perf_smoke_prepend_usr_local_bin():
    for name in (
        "healthcheck.sh",
        "bringup_check.sh",
        "perf_healthcheck.sh",
        "smoke_render.sh",
        "install_flam3.sh",
    ):
        text = _read(f"scripts/{name}")
        assert "/usr/local/bin" in text and "export PATH=" in text, (
            f"{name} should export PATH including /usr/local/bin"
        )


def test_archive_cron_defaults_skip_catalog():
    text = _read("scripts/cron_archive_seed.sh")
    assert 'ARCHIVE_SKIP_CATALOG:-1' in text
    assert "CMD+=(--skip-catalog)" in text
    assert "CMD+=(--no-skip-catalog)" in text


def test_lab_idle_breed_crontab_is_0511():
    breed = _read("scripts/cron_breed_idle.sh")
    assert "11 5 * * *" in breed
    assert "05:11" in breed
    assert "0 2 * * *" not in breed
    docs = _read("docs/phase2/07_PEDIGREE_BREEDING.md")
    assert "11 5 * * *" in docs
    assert "05:11" in docs
    assert "0 2 * * *" not in docs


def test_lab_archive_crontab_staggered_dom():
    script = _read("scripts/cron_archive_seed.sh")
    docs = _read("docs/phase2/01_ARCHIVE_SEED_LIBRARY.md")
    for blob in (script, docs):
        assert "7,17,27" in blob
        assert "1,11,21" in blob
        assert "3,13,23" in blob
        assert "1,12,23" not in blob


def test_yaml_example_documents_per_host_archive_cron():
    text = _read("configs/jellyflam3.yaml.example")
    assert "04a" in text
    assert "7,17,27" in text
    assert "1,11,21" in text
    assert "11 5 * * *" in text
    assert "archive_cron_dom: [3, 13, 23]" in text


def test_operator_scripts_have_purpose_headers():
    missing: list[str] = []
    for path in sorted(SCRIPTS.iterdir()):
        if path.suffix.lower() not in {".sh", ".ps1", ".py"}:
            continue
        if path.name.startswith("."):
            continue
        head = path.read_text(encoding="utf-8")[:2500]
        if "Purpose:" not in head:
            missing.append(path.name)
    assert missing == [], f"scripts missing Purpose header: {missing}"


def test_seed_inbox_cli_skip_catalog_default_on():
    text = _read("pipeline/seed_inbox.py")
    chunk = text.split("--skip-catalog", 1)[1][:800]
    assert "BooleanOptionalAction" in chunk
    assert "default=True" in chunk
    assert "--no-skip-catalog" in chunk


def test_healthcheck_peering_uses_live_share_probe():
    text = _read("scripts/healthcheck.sh")
    peering = text.split("== peering (guide 05) ==", 1)[1].split("== throttle ==", 1)[0]
    assert "assess_peering_readiness" in peering
    assert "share_live" in peering
    assert "BAD share not live" in peering
    assert "WARN jellyflam3-syncthing not active while Opt In" not in peering


def test_healthcheck_queue_probe_does_not_swallow_with_or_true():
    text = _read("scripts/healthcheck.sh")
    queue = text.split("== queue ==", 1)[1]
    # Must fail closed: no `python3 ... || true` on the queue probe.
    assert "|| true" not in queue
    assert "FAIL queue probe" in queue
    assert 'if "genomes_inbox" not in paths' in queue or "genomes_inbox" in queue


def test_bringup_maps_healthcheck_failure_to_bad_not_warn():
    text = _read("scripts/bringup_check.sh")
    assert 'bad "healthcheck.sh failed' in text
    assert 'warn "healthcheck.sh failed' not in text
