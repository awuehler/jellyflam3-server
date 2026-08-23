"""Purpose: License tagging helpers and commercial filter contract for catalog items.

Requirements: Genome path/XML for inference; config ``license.commercial_mode`` / ``exclude_tags``.

Usage: ``infer_tags_from_genome`` at seed/breed time; ``filter_items_for_commercial`` for venue clients.

Assumptions: Unknown robot-style genomes default to cc-by-nc; human nick → cc-by unless already tagged.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


def infer_tags_from_genome(path: Path, xml_text: str | None = None) -> list[str]:
    """Best-effort tags from filename / XML nick / edit hints."""
    tags: list[str] = []
    name = path.name
    m = re.search(r"electricsheep\.(\d+)\.(\d+)", name, re.I)
    if m:
        tags.append(f"generation-{m.group(1)}")
        tags.append(f"sheep-{m.group(2)}")
    text = xml_text if xml_text is not None else path.read_text(encoding="utf-8", errors="replace")
    if re.search(r'nick\s*=\s*"(?!brood)[^"]+"', text, re.I):
        tags.append("human")
    if re.search(r"brood|clone brood", text, re.I):
        tags.append("brood")
    # Default unknown robot-style seeds to NC-conservative unless marked human
    if "human" in tags and "cc-by" not in tags:
        tags.append("cc-by")
    elif "cc-by-nc" not in tags and "cc-by" not in tags:
        tags.append("cc-by-nc")
    return sorted(set(tags))


def is_commercial_allowed(tags: Iterable[str], cfg: dict[str, Any]) -> bool:
    """True unless commercial_mode is on and tags intersect configured exclude_tags."""
    license_cfg = cfg.get("license") or {}
    if not license_cfg.get("commercial_mode", False):
        return True
    exclude = {t.lower() for t in license_cfg.get("exclude_tags", ["cc-by-nc"])}
    tags_l = {t.lower() for t in tags}
    return tags_l.isdisjoint(exclude)


def filter_items_for_commercial(items: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """BrightScript / API filter contract: drop NC when commercial_mode."""
    out = []
    for item in items:
        tags = item.get("Tags") or item.get("tags") or []
        if is_commercial_allowed(tags, cfg):
            out.append(item)
    return out
