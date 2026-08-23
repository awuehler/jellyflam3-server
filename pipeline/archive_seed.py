"""Purpose: Discover, fetch, and TV-port Electric Sheep archive genomes into a local cache.

Requirements: Network access to electricsheep.com / sheepserver mirrors; optional sheep_tax and tv_optimize.

Usage: Import helpers from the worker/seed path, or call scrape_manifest / ensure_manifest / materialize_sheep.

Assumptions: Curated pool is gens 247/245/244/243/242/198/191/169/165 best pages 1–3 unless config overrides.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from pipeline.tv_optimize import cache_edition_key, tv_optimize_xml

log = logging.getLogger("jellyflam3.archive_seed")

DEFAULT_GENERATIONS = (247, 245, 244, 243, 242, 198, 191, 169, 165)
DEFAULT_PAGES = (1, 2, 3)
ARCHIVE_INDEX = "https://electricsheep.com/archives/"
USER_AGENT = "jellyflam3-seed/0.1 (+https://github.com/awuehler/jellyflam3-server)"

_SHEEP_VIEW = re.compile(r"/sheep/(\d+)/view\.html", re.I)
_FLAME_OK = re.compile(r"<flame\b", re.I)


@dataclass(frozen=True)
class ArchiveSheep:
    generation: int
    sheep_id: int

    @property
    def name(self) -> str:
        from pipeline.sheep_names import archive_stem

        return archive_stem(self.generation, self.sheep_id)

    @property
    def filename(self) -> str:
        from pipeline.sheep_names import archive_filename

        return archive_filename(self.generation, self.sheep_id)

    def to_dict(self) -> dict[str, int]:
        return {"generation": self.generation, "sheep_id": self.sheep_id}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ArchiveSheep":
        return cls(int(d["generation"]), int(d["sheep_id"]))


def archive_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    """Return the ``seed_archive`` config section (empty dict if missing)."""
    return dict(cfg.get("seed_archive") or {})


def default_manifest_path(cfg: dict[str, Any]) -> Path:
    """Resolved path to the archive seed manifest JSON under the repo root."""
    root = Path(cfg["_repo_root"])
    rel = archive_cfg(cfg).get("manifest") or "configs/archive_seed_manifest.json"
    p = Path(rel)
    return p if p.is_absolute() else root / p


def default_cache_dir(cfg: dict[str, Any]) -> Path:
    """Resolved directory for raw / TV-ported archive genome cache."""
    root = Path(cfg["_repo_root"])
    rel = archive_cfg(cfg).get("cache_dir") or "genomes/archive_cache"
    p = Path(rel)
    return p if p.is_absolute() else root / p


def generations(cfg: dict[str, Any] | None = None) -> list[int]:
    """Generation ids to scrape; config override or DEFAULT_GENERATIONS."""
    if cfg:
        gens = archive_cfg(cfg).get("generations")
        if gens:
            return [int(g) for g in gens]
    return list(DEFAULT_GENERATIONS)


def page_files(cfg: dict[str, Any] | None = None) -> list[int]:
    """Best-page numbers (e.g. 1,2,3); accepts ``N`` or ``N.html`` in config."""
    if cfg:
        pages = archive_cfg(cfg).get("page_files")
        if pages:
            out: list[int] = []
            for p in pages:
                s = str(p)
                if s.endswith(".html"):
                    s = s[: -len(".html")]
                out.append(int(s))
            return out
    return list(DEFAULT_PAGES)


def listing_url(generation: int, page: int) -> str:
    return f"{ARCHIVE_INDEX}generation-{generation}/best/page/{page}.html"


def flam3_url_candidates(sheep: ArchiveSheep) -> list[str]:
    """Ordered mirror URLs to try when downloading a sheep ``.flam3``."""
    gen, sid = sheep.generation, sheep.sheep_id
    name = sheep.filename
    return [
        f"http://v3d0.sheepserver.net/gen/{gen}/{sid}/{name}",
        f"http://v2d7c.sheepserver.net/gen/{gen}/{sid}/{name}",
        f"https://electricsheep.com/archives/generation-{gen}/{sid}/{name}",
        f"https://electricsheep.com/archives/generation-{gen}/sheep/{sid}/{name}",
    ]


def http_get(url: str, *, timeout: float = 60.0) -> bytes:
    """GET ``url`` with the project User-Agent; raise on network/HTTP failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_sheep_ids(html: str) -> list[int]:
    """Extract unique sheep ids from an archive best-page HTML listing."""
    return sorted({int(m.group(1)) for m in _SHEEP_VIEW.finditer(html)})


def scrape_generation(generation: int, pages: Iterable[int]) -> list[ArchiveSheep]:
    """Scrape best pages for one generation; skip failed pages and continue."""
    ids: set[int] = set()
    for page in pages:
        url = listing_url(generation, page)
        log.info("scrape %s", url)
        try:
            html = http_get(url).decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            log.warning("scrape failed %s: %s", url, exc)
            continue
        found = parse_sheep_ids(html)
        log.info("gen=%s page=%s count=%s", generation, page, len(found))
        ids.update(found)
        time.sleep(0.2)
    return [ArchiveSheep(generation, sid) for sid in sorted(ids)]


def scrape_manifest(
    *,
    gens: Iterable[int] | None = None,
    pages: Iterable[int] | None = None,
) -> dict[str, Any]:
    """Build a fresh manifest payload (sheep list + metadata) by scraping the archive."""
    gen_list = list(gens) if gens is not None else list(DEFAULT_GENERATIONS)
    page_list = list(pages) if pages is not None else list(DEFAULT_PAGES)
    sheep: list[ArchiveSheep] = []
    for gen in gen_list:
        sheep.extend(scrape_generation(gen, page_list))
    payload = {
        "source": ARCHIVE_INDEX,
        "pages": page_list,
        "generations": gen_list,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "count": len(sheep),
        "sheep": [s.to_dict() for s in sheep],
    }
    return payload


def load_manifest(path: Path) -> list[ArchiveSheep]:
    """Load ArchiveSheep entries from a manifest JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ArchiveSheep.from_dict(d) for d in data.get("sheep") or []]


def save_manifest(path: Path, payload: dict[str, Any]) -> Path:
    """Write manifest JSON (creates parent dirs). Returns ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def ensure_manifest(cfg: dict[str, Any], *, refresh: bool = False) -> list[ArchiveSheep]:
    """Load cached manifest, scraping and saving when missing or ``refresh`` is set."""
    path = default_manifest_path(cfg)
    if refresh or not path.is_file():
        payload = scrape_manifest(gens=generations(cfg), pages=page_files(cfg))
        save_manifest(path, payload)
        log.info("wrote manifest %s (%s sheep)", path, payload["count"])
    return load_manifest(path)


def pick_random(pool: list[ArchiveSheep], count: int) -> list[ArchiveSheep]:
    """Sample up to ``count`` sheep from ``pool`` (all if count >= len)."""
    if count <= 0:
        return []
    if count >= len(pool):
        return list(pool)
    return random.sample(pool, count)


def fetch_flam3(sheep: ArchiveSheep, *, timeout: float = 60.0) -> str:
    """Download genome XML from the first mirror that returns a ``<flame>`` body."""
    errors: list[str] = []
    for url in flam3_url_candidates(sheep):
        try:
            raw = http_get(url, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"{url}: {exc}")
            continue
        text = raw.decode("utf-8", "replace")
        if not _FLAME_OK.search(text):
            errors.append(f"{url}: no <flame>")
            continue
        log.info("fetched %s from %s", sheep.name, url)
        return text
    raise RuntimeError(f"failed to fetch {sheep.name}: " + "; ".join(errors[:4]))


def default_fetch_count(cfg: dict[str, Any] | None = None) -> int:
    """Random 3–7 seeds unless seed_archive.fetch_count / min/max override."""
    ac = archive_cfg(cfg) if cfg else {}
    if ac.get("fetch_count") is not None:
        return max(1, int(ac["fetch_count"]))
    lo = int(ac.get("fetch_count_min", 3))
    hi = int(ac.get("fetch_count_max", 7))
    if hi < lo:
        lo, hi = hi, lo
    return random.randint(lo, hi)


def tv_port_xml(xml_text: str, cfg: dict[str, Any]) -> str:
    """TV-port: 16:9 aspect, Gold Sheep Lite quality, ambient palette."""
    xml, _harmony = tv_optimize_xml(xml_text, cfg)
    return xml


def materialize_sheep(
    sheep: ArchiveSheep,
    cfg: dict[str, Any],
    *,
    tv_port: bool = True,
    use_cache: bool = True,
) -> Path:
    """Download (or reuse cache), optionally TV-port, write under archive cache."""
    cache = default_cache_dir(cfg)
    raw_path = cache / "raw" / str(sheep.generation) / sheep.filename
    edition = cache_edition_key(cfg) if tv_port else "raw"
    out_path = cache / edition / str(sheep.generation) / sheep.filename

    if use_cache and out_path.is_file() and out_path.stat().st_size > 32:
        return out_path

    if use_cache and raw_path.is_file() and raw_path.stat().st_size > 32:
        xml = raw_path.read_text(encoding="utf-8", errors="replace")
    else:
        xml = fetch_flam3(sheep)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(xml, encoding="utf-8")

    # Guide 06: sheep tax before TV-port (structural hygiene first).
    tax_cfg = cfg.get("sheep_tax") or {}
    if bool(tax_cfg.get("enabled", True)) and bool(tax_cfg.get("on_archive_fetch", True)):
        from pipeline.sheep_tax import tax_xml_text

        xml, tax_result = tax_xml_text(xml, cfg)
        log.info(
            "sheep tax %s: status=%s issues=%s",
            sheep.name,
            tax_result.get("status"),
            len(tax_result.get("issues") or []),
        )

    if tv_port:
        xml = tv_port_xml(xml, cfg)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(xml, encoding="utf-8")
    return out_path
