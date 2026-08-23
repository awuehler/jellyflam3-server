"""Resolve configured tool binaries with a single fallback rule."""

from __future__ import annotations

from typing import Any


def tool(cfg: dict[str, Any], name: str) -> str:
    """Return cfg['tools'][name] if set, else hyphenated name (flam3_animate → flam3-animate)."""
    tools = cfg.get("tools") or {}
    raw = tools.get(name)
    if raw:
        return str(raw)
    return name.replace("_", "-")
