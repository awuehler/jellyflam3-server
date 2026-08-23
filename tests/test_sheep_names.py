from pathlib import Path

from pipeline.sheep_names import (
    archive_filename,
    catalog_generation,
    demo_seed_filename,
    is_template_genome,
    mutate_filename,
    normalize_filename,
    normalize_stem,
    pedigree_filename,
    random_filename,
    reclaim_filename,
    template_smoke_480p,
    template_tv_1080p,
)


def test_archive_and_templates():
    assert archive_filename(247, 505) == "electricsheep.247.00505.flam3"
    assert template_smoke_480p() == "electricsheep.smoke.480p.flam3"
    assert template_tv_1080p() == "electricsheep.tv.1080p.flam3"
    assert demo_seed_filename() == "electricsheep.demo.seed.flam3"


def test_normalize_legacy_jellyflam3_prefix():
    assert normalize_stem("jellyflam3.pedigree.mutate.abc") == (
        "electricsheep.pedigree.mutate.abc"
    )
    assert normalize_filename("jellyflam3.local.demo.flam3") == (
        "electricsheep.local.demo.flam3"
    )
    assert normalize_filename("my_seed.flam3") == "electricsheep.my_seed.flam3"


def test_normalize_extracts_archive_id_from_messy_name():
    assert (
        normalize_filename("copy of electricsheep.247.00505 (1).flam3")
        == "electricsheep.247.00505.flam3"
    )


def test_catalog_generation():
    assert catalog_generation("electricsheep.247.00505") == "247"
    assert catalog_generation("electricsheep.pedigree.mutate.abc") == "pedigree"
    assert catalog_generation("electricsheep.random.20260101.deadbeef") == "random"
    assert catalog_generation("plain") == "misc"


def test_template_detection():
    assert is_template_genome("electricsheep.smoke.480p.flam3")
    assert is_template_genome(Path("configs/templates/electricsheep.tv.1080p.flam3"))
    assert is_template_genome(Path("configs/templates/electricsheep.smoke.480p.flam3"))
    assert not is_template_genome("electricsheep.247.00505.flam3")
    assert not is_template_genome("electricsheep.demo.seed.flam3")


def test_generated_names():
    assert pedigree_filename("mutate", "abc12def") == (
        "electricsheep.pedigree.mutate.abc12def.flam3"
    )
    assert mutate_filename("deadbeef") == "electricsheep.mutate.deadbeef.flam3"
    assert reclaim_filename("34f3d01c592b") == (
        "electricsheep.reclaim.34f3d01c592b.flam3"
    )
    r = random_filename()
    assert r.startswith("electricsheep.random.")
    assert r.endswith(".flam3")
