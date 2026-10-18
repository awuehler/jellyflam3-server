"""Purpose: Discover, fetch, and TV-port Electric Sheep archive genomes into a local cache.

Requirements: Network access to electricsheep.com / sheepserver mirrors; optional sheep_tax and tv_optimize.

Usage: Import helpers from the worker/seed path, or call scrape_manifest / ensure_manifest / materialize_sheep.
  ``parse_archive_sheep_token`` accepts ``247.00505``, ``247.505``, and ``electricsheep.247.00505``.
  ``fetch_flam3`` reads the named archive ``.flam3``, then the ``spex`` link on ``genome.html``.

Assumptions: Curated pool is gens 247/245/244/243/242/198/191/169/165 best pages 1–3 unless config overrides.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
import urllib.error
import urllib.parse
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
# Kept on refresh so the committed manifest still explains itself after a scrape.
MANIFEST_COMMENT = (
    "Random-pick pool for python3 -m pipeline.seed_inbox --archive and "
    "scripts/cron_archive_seed.sh. Scope: generation and sheep id from the "
    "Electric Sheep archive best pages listed in this file. No genome XML and "
    "no license. --sheep and --from-file do not read this file. "
    "--refresh-manifest replaces the sheep list from the live archive and keeps this note."
)

_SHEEP_VIEW = re.compile(r"/sheep/(\d+)/view\.html", re.I)
_FLAME_OK = re.compile(r"<flame\b", re.I)
_HREF_RE = re.compile(r"""href=["']([^"']+)["']""", re.I)
_ARCHIVE_TOKEN_RE = re.compile(
    rf"^(?:(?:{re.escape('electricsheep')}|jellyflam3)\.)?(\d+)\.(\d+)(?:\.flam3|\.flame)?$",
    re.I,
)


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


class ArchiveSheepTokenError(ValueError):
    """A requested archive id is not ``generation.sheep``."""

    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__(
            f"{token!r} is not an archive sheep id "
            "(expected generation.sheep, optional electricsheep. prefix)"
        )


def parse_archive_sheep_token(token: str) -> ArchiveSheep:
    """Parse one archive id. Leading zeros do not change the sheep."""
    raw = (token or "").strip()
    match = _ARCHIVE_TOKEN_RE.match(raw)
    if match is None:
        raise ArchiveSheepTokenError(raw or token)
    generation = int(match.group(1))
    sheep_id = int(match.group(2))
    if generation <= 0 or sheep_id <= 0:
        raise ArchiveSheepTokenError(raw)
    return ArchiveSheep(generation, sheep_id)


def split_sheep_tokens(text: str) -> list[str]:
    """Comma-separated ids, with surrounding whitespace removed."""
    return [part.strip() for part in (text or "").split(",") if part.strip()]


def sheep_tokens_from_text(text: str) -> list[str]:
    """Ids from a list file: one sheep per line, commas allowed, ``#`` lines skipped."""
    found: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        found.extend(split_sheep_tokens(stripped))
    return found


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


def archive_flam3_url(sheep: ArchiveSheep) -> str:
    """Named genome on the Electric Sheep archive."""
    return (
        f"{ARCHIVE_INDEX}generation-{sheep.generation}/"
        f"{sheep.sheep_id}/{sheep.filename}"
    )


def genome_page_url(sheep: ArchiveSheep) -> str:
    """Archive page that links to this sheep's ``spex`` genome."""
    return (
        f"{ARCHIVE_INDEX}generation-{sheep.generation}/"
        f"sheep/{sheep.sheep_id}/genome.html"
    )


def sheepserver_flam3_urls(sheep: ArchiveSheep) -> list[str]:
    """Legacy sheepserver mirrors of the named ``.flam3``."""
    name = sheep.filename
    gen, sid = sheep.generation, sheep.sheep_id
    return [
        f"http://v3d0.sheepserver.net/gen/{gen}/{sid}/{name}",
        f"http://v2d7c.sheepserver.net/gen/{gen}/{sid}/{name}",
    ]


def flam3_url_candidates(sheep: ArchiveSheep) -> list[str]:
    """Named ``.flam3`` URLs: archive file, then sheepserver mirrors.

    ``fetch_flam3`` tries the archive file first, then the ``spex`` link on
    ``genome.html``, and only then these sheepserver URLs.
    """
    return [archive_flam3_url(sheep), *sheepserver_flam3_urls(sheep)]


def spex_url_from_genome_html(page_url: str, html: str) -> str | None:
    """Resolve the first ``href`` whose path ends in ``/spex``.

    Generation 247 links ``../../18817/spex``. Generation 165 links
    ``../../old/6790/spex``. The response body is the raw genome.
    """
    for href in _HREF_RE.findall(html or ""):
        resolved = urllib.parse.urljoin(page_url, href.strip())
        path = urllib.parse.urlparse(resolved).path.rstrip("/")
        if path.endswith("/spex"):
            return resolved
    return None


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
        "_comment": MANIFEST_COMMENT,
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


def normalize_flam3_text(xml: str) -> str:
    """Return genome XML with LF newlines.

    Archive mirrors and a Windows ``Path.write_text`` both emit CRLF. Flam3
    accepts either, but the furnace files stay deterministic when every copy is LF.
    """
    return xml.replace("\r\n", "\n").replace("\r", "\n")


def write_flam3(path: Path, xml: str) -> None:
    """Write genome XML as UTF-8 LF bytes (no platform newline translation)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(normalize_flam3_text(xml).encode("utf-8"))


def ensure_flam3_lf(path: Path) -> Path:
    """Rewrite ``path`` in place when it still contains CR."""
    data = path.read_bytes()
    if b"\r" in data:
        write_flam3(path, data.decode("utf-8", "replace"))
    return path


def _flame_text(raw: bytes) -> str | None:
    """Return LF genome text when ``raw`` contains a ``<flame>`` element."""
    text = normalize_flam3_text(raw.decode("utf-8", "replace"))
    if not _FLAME_OK.search(text):
        return None
    return text


def fetch_flam3(sheep: ArchiveSheep, *, timeout: float = 60.0) -> str:
    """Download genome XML, using the archive ``spex`` link when the named file is missing.

    Order: the named archive ``.flam3``, then the ``/spex`` href on
    ``genome.html``, then the sheepserver mirrors. A hit must contain ``<flame>``.
    """
    errors: list[str] = []

    def attempt(url: str) -> str | None:
        try:
            raw = http_get(url, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"{url}: {exc}")
            return None
        text = _flame_text(raw)
        if text is None:
            errors.append(f"{url}: no <flame>")
            return None
        log.info("fetched %s from %s", sheep.name, url)
        return text

    text = attempt(archive_flam3_url(sheep))
    if text is None:
        page = genome_page_url(sheep)
        try:
            raw = http_get(page, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"{page}: {exc}")
        else:
            spex = spex_url_from_genome_html(page, raw.decode("utf-8", "replace"))
            if spex is None:
                errors.append(f"{page}: no spex link")
            else:
                text = attempt(spex)
    if text is None:
        for url in sheepserver_flam3_urls(sheep):
            text = attempt(url)
            if text is not None:
                break
    if text is None:
        raise RuntimeError(f"failed to fetch {sheep.name}: " + "; ".join(errors[:6]))
    return text


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
        return ensure_flam3_lf(out_path)

    if use_cache and raw_path.is_file() and raw_path.stat().st_size > 32:
        ensure_flam3_lf(raw_path)
        xml = raw_path.read_text(encoding="utf-8", errors="replace")
    else:
        xml = fetch_flam3(sheep)
        write_flam3(raw_path, xml)

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
    write_flam3(out_path, xml)
    return out_path
