from pathlib import Path

from pipeline.archive_seed import (
    ArchiveSheep,
    flam3_url_candidates,
    parse_sheep_ids,
    pick_random,
)


def test_parse_sheep_ids_from_listing_html():
    html = """
    <a href="../../sheep/505/view.html">x</a>
    <a href="../../sheep/18817/view.html">y</a>
    <a href="../../sheep/505/view.html">dup</a>
    """
    assert parse_sheep_ids(html) == [505, 18817]


def test_flam3_url_candidates_include_sheepserver_and_archives():
    sheep = ArchiveSheep(247, 505)
    urls = flam3_url_candidates(sheep)
    assert any("v3d0.sheepserver.net/gen/247/505/electricsheep.247.00505.flam3" in u for u in urls)
    assert any("generation-247/505/electricsheep.247.00505.flam3" in u for u in urls)


def test_pick_random_count():
    pool = [ArchiveSheep(247, i) for i in range(10)]
    picked = pick_random(pool, 3)
    assert len(picked) == 3
    assert set(picked).issubset(set(pool))


def test_tv_port_xml_rewrites_size():
    from pipeline.archive_seed import tv_port_xml

    xml = '<flame time="0" size="800 592" scale="100"><color index="0" rgb="40 180 200" /></flame>'
    out = tv_port_xml(
        xml,
        {
            "render": {"target_width": 1920, "target_height": 1080, "edition": "gold_sheep_lite"},
            "palette": {"mode": "complementary"},
        },
    )
    assert 'size="1920 1080"' in out
    assert "800 592" not in out
    assert 'quality="900"' in out


def test_archive_sheep_filename():
    assert ArchiveSheep(244, 128).filename == "electricsheep.244.00128.flam3"


def test_parse_sheep_ids_empty_html():
    assert parse_sheep_ids("") == []
    assert parse_sheep_ids("<html><body>no sheep here</body></html>") == []


def test_pick_random_zero_returns_empty():
    pool = [ArchiveSheep(247, i) for i in range(3)]
    assert pick_random(pool, 0) == []


def test_archive_sheep_from_dict_requires_keys():
    import pytest

    with pytest.raises(KeyError):
        ArchiveSheep.from_dict({"generation": 247})
