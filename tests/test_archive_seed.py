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
    from pipeline.archive_seed import archive_flam3_url, sheepserver_flam3_urls

    sheep = ArchiveSheep(247, 505)
    urls = flam3_url_candidates(sheep)
    assert urls[0] == archive_flam3_url(sheep)
    assert urls[1:] == sheepserver_flam3_urls(sheep)
    assert "generation-247/505/electricsheep.247.00505.flam3" in urls[0]
    assert all("/sheep/505/" not in url for url in urls)


def test_spex_url_from_genome_html_resolves_relative_links():
    from pipeline.archive_seed import spex_url_from_genome_html

    page = "https://electricsheep.com/archives/generation-247/sheep/18817/genome.html"
    assert (
        spex_url_from_genome_html(page, '<a href="../../18817/spex">genome</a>')
        == "https://electricsheep.com/archives/generation-247/18817/spex"
    )
    old = "https://electricsheep.com/archives/generation-165/sheep/6790/genome.html"
    assert (
        spex_url_from_genome_html(old, '<a href="../../old/6790/spex">genome</a>')
        == "https://electricsheep.com/archives/generation-165/old/6790/spex"
    )
    assert spex_url_from_genome_html(page, '<a href="../../18817/spex.html">x</a>') is None
    assert spex_url_from_genome_html(page, "<html>no link</html>") is None


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


def test_parse_archive_sheep_token_accepts_prefix_and_padding():
    import pytest

    from pipeline.archive_seed import ArchiveSheepTokenError, parse_archive_sheep_token

    bare = parse_archive_sheep_token("247.505")
    padded = parse_archive_sheep_token("electricsheep.247.00505.flam3")
    legacy = parse_archive_sheep_token("jellyflam3.247.00505")
    assert bare == padded == legacy
    assert bare.filename == "electricsheep.247.00505.flam3"
    for bad in ("", "tuple", "electricsheep.tuple.247.00505_to_245.00061", "247", "0.5", "247.0"):
        with pytest.raises(ArchiveSheepTokenError):
            parse_archive_sheep_token(bad)
    flame = parse_archive_sheep_token("  electricsheep.245.00061.flame  ")
    assert flame == parse_archive_sheep_token("245.61")


def test_sheep_list_text_keeps_file_order():
    from pipeline.archive_seed import sheep_tokens_from_text, split_sheep_tokens

    assert split_sheep_tokens(" 247.00505, 245.61 , ,") == ["247.00505", "245.61"]
    text = "# night batch\n\n245.00061\n243.16930, 242.100\n"
    assert sheep_tokens_from_text(text) == ["245.00061", "243.16930", "242.100"]


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


def test_fetch_flam3_normalizes_crlf(monkeypatch):
    from pipeline.archive_seed import archive_flam3_url, fetch_flam3

    payload = b'<flame name="electricsheep.247.00001" time="0" size="800 592"></flame>\r\n'
    calls: list[str] = []

    def fake_get(url, timeout=60.0):
        calls.append(url)
        return payload

    monkeypatch.setattr("pipeline.archive_seed.http_get", fake_get)
    sheep = ArchiveSheep(247, 1)
    text = fetch_flam3(sheep)
    assert calls == [archive_flam3_url(sheep)]
    assert "\r" not in text
    assert text == payload.decode().replace("\r\n", "\n")


def _http_404(url: str):
    import urllib.error

    return urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)


def test_fetch_flam3_uses_spex_when_named_file_is_missing(monkeypatch):
    from pipeline.archive_seed import archive_flam3_url, fetch_flam3, genome_page_url

    sheep = ArchiveSheep(165, 6790)
    calls: list[str] = []
    spex = "https://electricsheep.com/archives/generation-165/old/6790/spex"

    def fake_get(url, timeout=60.0):
        calls.append(url)
        if url == archive_flam3_url(sheep):
            raise _http_404(url)
        if url == genome_page_url(sheep):
            return b'<a href="../../old/6790/spex">genome</a>'
        if url == spex:
            return b'<flame time="0" size="640 480" palette="76"></flame>\r\n'
        raise AssertionError(url)

    monkeypatch.setattr("pipeline.archive_seed.http_get", fake_get)
    text = fetch_flam3(sheep)
    assert calls == [archive_flam3_url(sheep), genome_page_url(sheep), spex]
    assert text == '<flame time="0" size="640 480" palette="76"></flame>\n'


def test_fetch_flam3_continues_when_spex_link_or_body_is_unusable(monkeypatch):
    from pipeline.archive_seed import archive_flam3_url, fetch_flam3, genome_page_url, sheepserver_flam3_urls

    sheep = ArchiveSheep(198, 1288)
    servers = sheepserver_flam3_urls(sheep)
    calls: list[str] = []

    def fake_get(url, timeout=60.0):
        calls.append(url)
        if url == archive_flam3_url(sheep):
            raise _http_404(url)
        if url == genome_page_url(sheep):
            return b"<html>no spex here</html>"
        if url == servers[0]:
            return b'<flame time="0" size="1280 960"></flame>'
        raise AssertionError(url)

    monkeypatch.setattr("pipeline.archive_seed.http_get", fake_get)
    assert "<flame" in fetch_flam3(sheep)
    assert calls == [archive_flam3_url(sheep), genome_page_url(sheep), servers[0]]

    calls.clear()

    def spex_html(url, timeout=60.0):
        calls.append(url)
        if url == archive_flam3_url(sheep):
            raise _http_404(url)
        if url == genome_page_url(sheep):
            return b'<a href="../../1288/spex">genome</a>'
        if url.endswith("/spex"):
            return b"<html>not a genome</html>"
        if url == servers[0]:
            return b'<flame time="0"></flame>'
        raise AssertionError(url)

    monkeypatch.setattr("pipeline.archive_seed.http_get", spex_html)
    assert fetch_flam3(sheep).startswith("<flame")
    assert calls[-1] == servers[0]
    assert any(url.endswith("/1288/spex") for url in calls)


def test_fetch_flam3_raises_after_named_spex_and_mirrors_miss(monkeypatch):
    import pytest

    from pipeline.archive_seed import fetch_flam3

    def fake_get(url, timeout=60.0):
        raise _http_404(url)

    monkeypatch.setattr("pipeline.archive_seed.http_get", fake_get)
    with pytest.raises(RuntimeError, match="electricsheep.169.00050"):
        fetch_flam3(ArchiveSheep(169, 50))


def test_materialize_crlf_download_is_lf_in_cache_and_inbox(tmp_path, monkeypatch):
    from pipeline.archive_seed import materialize_sheep
    from pipeline.seed_inbox import stage_file

    crlf = '<flame name="electricsheep.247.00001" time="0" size="800 592"></flame>\r\n'
    monkeypatch.setattr(
        "pipeline.archive_seed.fetch_flam3",
        lambda sheep, timeout=60.0: crlf,
    )
    cfg = {"_repo_root": str(tmp_path), "sheep_tax": {"enabled": False}}
    out = materialize_sheep(ArchiveSheep(247, 1), cfg, tv_port=False, use_cache=False)
    data = out.read_bytes()
    assert b"\r" not in data
    assert data == crlf.replace("\r\n", "\n").encode()

    staged = stage_file(out, tmp_path / "inbox")
    assert staged is not None
    assert staged.read_bytes() == data


def test_cached_crlf_genome_is_rewritten_lf(tmp_path, monkeypatch):
    from pipeline.archive_seed import materialize_sheep

    sheep = ArchiveSheep(247, 1)
    raw = tmp_path / "genomes" / "archive_cache" / "raw" / "247" / sheep.filename
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b'<flame name="electricsheep.247.00001" time="0" size="800 592"></flame>\r\n')

    def boom(*_args, **_kwargs):
        raise AssertionError("cache hit must not download")

    monkeypatch.setattr("pipeline.archive_seed.fetch_flam3", boom)
    cfg = {"_repo_root": str(tmp_path), "sheep_tax": {"enabled": False}}
    out = materialize_sheep(sheep, cfg, tv_port=False, use_cache=True)
    assert out == raw
    assert b"\r" not in out.read_bytes()
