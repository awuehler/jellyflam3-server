"""Purpose: Canonical .flam3 sheep filename convention.

Requirements: None beyond stdlib (re, time, uuid, pathlib).

Usage: Import helpers (``normalize_filename``, ``archive_filename``, …) from seed/worker/catalog code.

Assumptions: Format ``electricsheep.<kind>.<id>[.<more>].flam3``; legacy ``jellyflam3.*``
accepted on read and normalized when staging. Sidecars stay ``*.jellyflam3.json``.

Examples:

======= =====================================
kind    example
======= =====================================
247     electricsheep.247.00505.flam3   (archive Free Sheep)
smoke   electricsheep.smoke.480p.flam3  (encode template)
tv      electricsheep.tv.1080p.flam3    (encode template)
demo    electricsheep.demo.seed.flam3   (legacy kind; file retired — use genomes/pedigree/smoke/)
pedigree electricsheep.pedigree.smoke.0001.flam3 / .mutate.<id>.flam3
random  electricsheep.random.20260807120000.deadbeef.flam3
mutate  electricsheep.mutate.deadbeef.flam3
reclaim electricsheep.reclaim.34f3d01c592b.flam3
======= =====================================
"""

from __future__ import annotations

import re
import time
import uuid
from pathlib import Path

SHEEP_PREFIX = "electricsheep"
LEGACY_PREFIX = "jellyflam3"

# Template genomes — not flock sheep; excluded from --samples pools.
TEMPLATE_KINDS = frozenset({"smoke", "tv"})

_ARCHIVE_RE = re.compile(
    rf"(?:{SHEEP_PREFIX}|{LEGACY_PREFIX})\.(\d+)\.(\d+)",
    re.I,
)
_PREFIXED_STEM_RE = re.compile(
    rf"^(?:{SHEEP_PREFIX}|{LEGACY_PREFIX})\.(.+)$",
    re.I,
)


def ensure_flam3(name: str) -> str:
    n = name if name.lower().endswith(".flam3") else f"{name}.flam3"
    return n


def stem_of(path_or_name: Path | str) -> str:
    """Basename without .flam3/.flame suffix when present."""
    p = Path(path_or_name)
    return p.stem if p.suffix.lower() in {".flam3", ".flame"} else p.name


def is_prefixed_stem(stem: str) -> bool:
    """True if stem already uses electricsheep. or legacy jellyflam3. prefix."""
    s = stem.lower()
    return s.startswith(f"{SHEEP_PREFIX}.") or s.startswith(f"{LEGACY_PREFIX}.")


def kind_of(stem: str) -> str | None:
    """Return the kind segment (generation digits or type token), if prefixed."""
    parts = stem.split(".")
    if len(parts) < 3:
        return None
    if parts[0].lower() not in {SHEEP_PREFIX, LEGACY_PREFIX}:
        return None
    return parts[1]


def is_template_genome(path_or_name: Path | str) -> bool:
    """True for smoke/tv encode templates (excluded from sample pools)."""
    kind = kind_of(stem_of(path_or_name))
    return kind is not None and kind.lower() in TEMPLATE_KINDS


def catalog_generation(stem: str) -> str:
    """Folder under by-generation/: numeric gen, else kind token, else misc."""
    kind = kind_of(stem)
    if kind is None:
        return "misc"
    if kind.isdigit():
        return kind
    return kind.lower()


def normalize_stem(stem: str) -> str:
    """Force electricsheep. prefix; strip .flam3 if present."""
    s = stem_of(stem)
    m = _PREFIXED_STEM_RE.match(s)
    if m:
        return f"{SHEEP_PREFIX}.{m.group(1)}"
    return f"{SHEEP_PREFIX}.{s}"


def normalize_filename(path_or_name: Path | str) -> str:
    """Inbox / catalog basename ending in .flam3 under the electricsheep. convention."""
    name = Path(path_or_name).name
    # Prefer embedded archive id if present anywhere in the name.
    m = _ARCHIVE_RE.search(name)
    if m:
        gen, sid = m.group(1), int(m.group(2))
        return archive_filename(int(gen), sid)
    return ensure_flam3(normalize_stem(name))


def archive_filename(generation: int, sheep_id: int) -> str:
    """Canonical archive sheep basename: electricsheep.<gen>.<id:05d>.flam3."""
    return f"{SHEEP_PREFIX}.{generation}.{sheep_id:05d}.flam3"


def archive_stem(generation: int, sheep_id: int) -> str:
    return f"{SHEEP_PREFIX}.{generation}.{sheep_id:05d}"


def template_smoke_480p() -> str:
    return f"{SHEEP_PREFIX}.smoke.480p.flam3"


def template_tv_1080p() -> str:
    return f"{SHEEP_PREFIX}.tv.1080p.flam3"


def demo_seed_filename() -> str:
    """Legacy ``electricsheep.demo.seed.flam3`` basename (file retired; kind still parseable)."""
    return f"{SHEEP_PREFIX}.demo.seed.flam3"


def pedigree_filename(mode: str, short_id: str | None = None) -> str:
    """Pedigree child basename for a breed mode (mutate/cross/…)."""
    sid = short_id or uuid.uuid4().hex[:8]
    return f"{SHEEP_PREFIX}.pedigree.{mode}.{sid}.flam3"


def random_filename() -> str:
    """Timestamped random genome basename for flam3-genome output."""
    stamp = time.strftime("%Y%m%d%H%M%S")
    return f"{SHEEP_PREFIX}.random.{stamp}.{uuid.uuid4().hex[:8]}.flam3"


def mutate_filename(short_id: str | None = None) -> str:
    """Basename for a flam3-genome mutate child."""
    sid = short_id or uuid.uuid4().hex[:8]
    return f"{SHEEP_PREFIX}.mutate.{sid}.flam3"


def reclaim_filename(job_id: str) -> str:
    """Basename for a genome reclaimed from an orphaned job."""
    return f"{SHEEP_PREFIX}.reclaim.{job_id}.flam3"
