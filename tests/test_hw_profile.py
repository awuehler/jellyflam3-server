from pathlib import Path

import yaml

from pipeline.hw_profile import (
    PROFILE_IDS,
    apply_profile,
    deep_merge,
    load_profile,
    resolve_profile_id,
)
from pipeline.tv_optimize import apply_gold_lite_quality


ROOT = Path(__file__).resolve().parents[1]


def test_resolve_aliases():
    assert resolve_profile_id("04") == "rpi-jellyflam3-04"
    assert resolve_profile_id("8") == "rpi-jellyflam3-08"
    assert resolve_profile_id("rpi-jellyflam3-16") == "rpi-jellyflam3-16"
    assert resolve_profile_id("rpi-jellyflam3-16a") == "rpi-jellyflam3-16"
    assert resolve_profile_id("rpi-jellyflam3-16b") == "rpi-jellyflam3-16"
    assert resolve_profile_id("rpi-jellyflam3-08a") == "rpi-jellyflam3-08"
    assert resolve_profile_id("08b") == "rpi-jellyflam3-08"
    assert resolve_profile_id("04a") == "rpi-jellyflam3-04"


def test_profiles_on_disk():
    for pid in PROFILE_IDS:
        data = load_profile(ROOT, pid)
        assert data["render"]["hw_profile"] == pid
        assert int(data["render"]["max_cpus"]) == 3
        assert int(data["render"]["quality"]) == 900


def test_deep_merge_preserves_sibling_keys():
    base = {"render": {"quality": 900, "target_width": 1920}, "vod": {"fps": 24}}
    overlay = {"render": {"edition": "compact"}, "vod": {"target_duration_sec": 19}}
    out = deep_merge(base, overlay)
    assert out["render"]["edition"] == "compact"
    assert out["render"]["target_width"] == 1920
    assert out["vod"]["fps"] == 24
    assert out["vod"]["target_duration_sec"] == 19


def test_apply_dry_run_and_write(tmp_path: Path):
    src = ROOT / "configs" / "jellyflam3.yaml.example"
    cfg = tmp_path / "jellyflam3.yaml"
    cfg.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    merged = apply_profile(cfg, ROOT, "rpi-jellyflam3-04", dry_run=True)
    assert merged["render"]["edition"] == "compact"
    assert merged["render"]["quality"] == 900
    assert merged["render"]["max_cpus"] == 3
    assert merged["vod"]["target_duration_sec"] == 19
    assert merged["vod"]["dynamic"]["base_sec"] == 23
    assert int(merged["vod"]["max_duration_sec"]) == 31
    assert int(merged["vod"]["max_duration_sec_hard"]) == 60
    before = cfg.read_text(encoding="utf-8")
    apply_profile(cfg, ROOT, "rpi-jellyflam3-04", dry_run=False)
    after = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert after["render"]["hw_profile"] == "rpi-jellyflam3-04"
    assert before != cfg.read_text(encoding="utf-8")


def test_profile_vod_bands_scale_with_hw():
    """Larger Pi class → longer soft/hard band and higher dynamic base_sec."""
    p16 = load_profile(ROOT, "rpi-jellyflam3-16")
    p08 = load_profile(ROOT, "rpi-jellyflam3-08")
    p04 = load_profile(ROOT, "rpi-jellyflam3-04")
    assert p16["vod"]["dynamic"]["base_sec"] == 43
    assert p08["vod"]["dynamic"]["base_sec"] == 31
    assert p04["vod"]["dynamic"]["base_sec"] == 23
    assert p16["vod"]["max_duration_sec"] >= p08["vod"]["max_duration_sec"] >= p04["vod"]["max_duration_sec"]
    assert (
        p16["vod"]["max_duration_sec_hard"]
        >= p08["vod"]["max_duration_sec_hard"]
        >= p04["vod"]["max_duration_sec_hard"]
    )


def test_profile_idle_breed_archive_cron_per_host():
    p16 = load_profile(ROOT, "rpi-jellyflam3-16")
    p08 = load_profile(ROOT, "rpi-jellyflam3-08")
    p04 = load_profile(ROOT, "rpi-jellyflam3-04")
    assert p16["breed"]["idle_breed"]["archive_cron_dom"] == [7, 17, 27]
    assert p16["breed"]["idle_breed"]["archive_cron_hour"] == 7
    assert p16["breed"]["idle_breed"]["archive_cron_minute"] == 27
    assert p08["breed"]["idle_breed"]["archive_cron_dom"] == [1, 11, 21]
    assert p08["breed"]["idle_breed"]["archive_cron_hour"] == 5
    assert p08["breed"]["idle_breed"]["archive_cron_minute"] == 19
    assert p04["breed"]["idle_breed"]["archive_cron_dom"] == [3, 13, 23]
    assert p04["breed"]["idle_breed"]["archive_cron_hour"] == 3
    assert p04["breed"]["idle_breed"]["archive_cron_minute"] == 17


def test_apply_merges_idle_breed_archive_cron(tmp_path: Path):
    src = ROOT / "configs" / "jellyflam3.yaml.example"
    cfg = tmp_path / "jellyflam3.yaml"
    cfg.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    merged = apply_profile(cfg, ROOT, "rpi-jellyflam3-16", dry_run=True)
    ib = merged["breed"]["idle_breed"]
    assert ib["archive_cron_dom"] == [7, 17, 27]
    assert ib["archive_cron_hour"] == 7
    assert ib["archive_cron_minute"] == 27


def test_compact_edition_same_lite_quality():
    xml = '<flame size="800 592" quality="50" temporal_samples="10" supersample="1"></flame>'
    out = apply_gold_lite_quality(xml, {"render": {"edition": "compact"}})
    assert 'quality="900"' in out
    assert 'temporal_samples="450"' in out
    assert 'supersample="2"' in out
