"""Purpose: Sheep tax — scan & safe repair of .flam3 genomes (Phase 2 guide 06).

Requirements: configs/jellyflam3.yaml ``sheep_tax.*``; stdlib XML.

Usage: ``python3 -m pipeline.sheep_tax scan|batch``; ``scan_file(path, cfg)`` from peering/worker.

Assumptions: Every genome pays tax before furnace trust or peer promote (well-formed XML,
structure, vocabulary, key–values). Order vs TV-port: tax first, then TV-optimize.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import load_config, resolve_path

log = logging.getLogger("jellyflam3.sheep_tax")

# Child tags we expect under <flame> (others logged; optionally stripped).
KNOWN_CHILD_TAGS = frozenset({"xform", "finalxform", "color", "palette", "symmetry", "edit"})

# Common flame attributes (unknown attrs kept + logged).
KNOWN_FLAME_ATTRS = frozenset(
    {
        "version",
        "time",
        "name",
        "size",
        "width",
        "height",
        "center",
        "scale",
        "rotate",
        "supersample",
        "filter",
        "filter_shape",
        "temporal_filter_type",
        "temporal_filter_width",
        "quality",
        "passes",
        "temporal_samples",
        "background",
        "brightness",
        "gamma",
        "highlight_power",
        "vibrancy",
        "estimator_radius",
        "estimator_minimum",
        "estimator_curve",
        "gamma_threshold",
        "palette_mode",
        "interpolation",
        "interpolation_type",
        "palette",
        "nick",
        "url",
        "brood",
        "notes",
        "singularity",
        "gene",
        "hsv",
        "hue",
        "batches",
        "nbatches",
        "transparency",
    }
)

DEFAULT_SIZE = (800, 592)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tax_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    return dict(cfg.get("sheep_tax") or {})


def _issue(code: str, message: str, *, severity: str = "info") -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity}


def parse_flam3_xml(xml_text: str) -> tuple[ET.Element, bool, str]:
    """Return (root, multi_root, decl). Raises ValueError if unparseable."""
    decl = ""
    m = re.match(r"^\s*<\?xml[^>]+\?>\s*", xml_text)
    if m:
        decl = m.group(0)
        xml_text = xml_text[m.end() :]
    body = xml_text.strip()
    if not body:
        raise ValueError("empty genome")
    if "<flame" not in body.lower():
        raise ValueError("no <flame> tag")
    multi_root = False
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        try:
            root = ET.fromstring(f"<flames>{body}</flames>")
            multi_root = True
        except ET.ParseError as exc:
            raise ValueError(f"XML parse failed: {exc}") from exc
    return root, multi_root, decl


def flame_elements(root: ET.Element) -> list[ET.Element]:
    """All ``<flame>`` elements under root (or ``[root]`` if root is a flame)."""
    if root.tag == "flame":
        return [root]
    return list(root.iter("flame"))


def serialize_flam3(root: ET.Element, *, multi_root: bool, decl: str = "") -> str:
    """Serialize flame tree back to XML text, preserving multi-root concat form."""
    if multi_root or root.tag == "flames":
        return decl + "".join(ET.tostring(child, encoding="unicode") for child in list(root))
    return decl + ET.tostring(root, encoding="unicode")


def _parse_size(flame: ET.Element) -> tuple[int, int] | None:
    """Parse size/width/height attrs; None if missing or unparseable."""
    size = flame.get("size")
    if size:
        parts = size.split()
        if len(parts) >= 2:
            try:
                return int(float(parts[0])), int(float(parts[1]))
            except ValueError:
                return None
    w, h = flame.get("width"), flame.get("height")
    if w and h:
        try:
            return int(float(w)), int(float(h))
        except ValueError:
            return None
    return None


def _repair_flame(
    flame: ET.Element,
    *,
    strip_unknown_elements: bool,
    repair: bool,
    issues: list[dict[str, str]],
) -> bool:
    """Inspect flame; mutate when ``repair`` is True. Return True if repaired."""
    changed = False

    for attr in list(flame.attrib):
        if attr not in KNOWN_FLAME_ATTRS:
            issues.append(_issue("unknown_flame_attr", f"<{flame.tag} {attr}=…> kept"))

    if _parse_size(flame) is None:
        issues.append(
            _issue(
                "missing_size",
                f"would set size={DEFAULT_SIZE[0]} {DEFAULT_SIZE[1]}",
                severity="repair" if repair else "warn",
            )
        )
        if repair:
            flame.set("size", f"{DEFAULT_SIZE[0]} {DEFAULT_SIZE[1]}")
            changed = True

    scale = flame.get("scale")
    bad_scale = (
        scale is None
        or str(scale).strip() == ""
        or str(scale).lower() == "nan"
    )
    if not bad_scale and scale is not None:
        try:
            val = float(scale)
            if math.isnan(val) or math.isinf(val) or val <= 0:
                bad_scale = True
        except ValueError:
            bad_scale = True
    if bad_scale:
        _w, h = _parse_size(flame) or DEFAULT_SIZE
        issues.append(
            _issue(
                "missing_scale" if scale is None else "bad_scale",
                f"would set scale={h}",
                severity="repair" if repair else "warn",
            )
        )
        if repair:
            flame.set("scale", str(float(h)))
            changed = True

    for child in list(flame):
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag not in KNOWN_CHILD_TAGS:
            issues.append(_issue("unknown_element", f"<{tag}> under flame"))
            if repair and strip_unknown_elements:
                flame.remove(child)
                issues.append(
                    _issue("stripped_element", f"removed <{tag}>", severity="repair")
                )
                changed = True
            continue
        if tag == "color":
            idx = child.get("index")
            if idx is not None:
                try:
                    n = int(float(idx))
                    if n < 0 or n > 255:
                        clamped = max(0, min(255, n))
                        issues.append(
                            _issue(
                                "color_index_clamp",
                                f"index {n} → {clamped}",
                                severity="repair" if repair else "warn",
                            )
                        )
                        if repair:
                            child.set("index", str(clamped))
                            changed = True
                except ValueError:
                    issues.append(
                        _issue(
                            "bad_color_index",
                            f"unparseable index={idx!r}",
                            severity="warn",
                        )
                    )
            rgb = child.get("rgb")
            if rgb:
                parts = rgb.split()
                if len(parts) >= 3:
                    try:
                        cols = [max(0, min(255, int(float(p)))) for p in parts[:3]]
                        new = f"{cols[0]} {cols[1]} {cols[2]}"
                        if new != " ".join(parts[:3]):
                            issues.append(
                                _issue(
                                    "rgb_clamp",
                                    "clamped rgb channels",
                                    severity="repair" if repair else "warn",
                                )
                            )
                            if repair:
                                child.set("rgb", new)
                                changed = True
                    except ValueError:
                        issues.append(
                            _issue("bad_rgb", f"rgb={rgb!r}", severity="warn")
                        )

    xforms = [
        c
        for c in flame
        if (c.tag.split("}")[-1] if "}" in c.tag else c.tag) == "xform"
    ]
    if not xforms:
        issues.append(_issue("no_xform", "flame has no <xform>", severity="warn"))

    return changed


def tax_xml(xml_text: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Scan/repair XML text. Returns result dict; includes repaired ``xml`` when ok."""
    cfg = cfg or {}
    tc = tax_cfg(cfg)
    multi_policy = str(tc.get("multi_flame") or "strip_to_first").lower()
    strip_unknown = bool(tc.get("strip_unknown_elements", False))
    do_repair = bool(tc.get("repair", True))

    issues: list[dict[str, str]] = []
    try:
        root, multi_root, decl = parse_flam3_xml(xml_text)
    except ValueError as exc:
        return {
            "ok": False,
            "status": "quarantined",
            "issues": [_issue("xml_invalid", str(exc), severity="error")],
            "xml": None,
            "flame_count": 0,
        }

    flames = flame_elements(root)
    if not flames:
        return {
            "ok": False,
            "status": "quarantined",
            "issues": [_issue("no_flame", "no <flame> elements", severity="error")],
            "xml": None,
            "flame_count": 0,
        }

    changed = False
    if len(flames) > 1:
        issues.append(
            _issue(
                "multi_flame",
                f"{len(flames)} flames (policy={multi_policy})",
                severity="warn",
            )
        )
        if multi_policy in ("reject", "quarantine"):
            return {
                "ok": False,
                "status": "quarantined",
                "issues": issues,
                "xml": None,
                "flame_count": len(flames),
            }
        if multi_policy in ("strip_to_first", "strip", "first") and do_repair:
            keep = flames[0]
            root = keep
            multi_root = False
            flames = [keep]
            issues.append(
                _issue("stripped_extra_flames", "kept first <flame> only", severity="repair")
            )
            changed = True

    for flame in flames:
        if _repair_flame(
            flame,
            strip_unknown_elements=strip_unknown,
            repair=do_repair,
            issues=issues,
        ):
            changed = True

    if not do_repair:
        return {
            "ok": True,
            "status": "ok",
            "issues": issues,
            "xml": xml_text,
            "flame_count": len(flames),
            "changed": False,
        }

    out_xml = serialize_flam3(root, multi_root=multi_root, decl=decl)
    status = "repaired" if changed else "ok"
    return {
        "ok": True,
        "status": status,
        "issues": issues,
        "xml": out_xml,
        "flame_count": len(flames),
        "changed": changed,
        "repaired_at": _utc_now() if changed else None,
    }


def scan_file(path: Path | str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Scan (and repair in place when ``sheep_tax.repair`` is true).

    Returns ``{ok, status, issues, ...}`` for peering promote / callers.
    """
    cfg = cfg or {}
    path = Path(path)
    tc = tax_cfg(cfg)
    if not bool(tc.get("enabled", True)):
        return {"ok": True, "status": "skipped", "issues": [], "path": str(path)}

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {
            "ok": False,
            "status": "quarantined",
            "issues": [_issue("read_error", str(exc), severity="error")],
            "path": str(path),
        }

    result = tax_xml(text, cfg)
    result["path"] = str(path)
    if result.get("ok") and result.get("changed") and result.get("xml") is not None:
        try:
            path.write_text(result["xml"], encoding="utf-8")
        except OSError as exc:
            result["ok"] = False
            result["status"] = "quarantined"
            result["issues"] = list(result.get("issues") or []) + [
                _issue("write_error", str(exc), severity="error")
            ]
    return result


def tax_path(
    path: Path,
    cfg: dict[str, Any],
    *,
    quarantine_dir: Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Tax a file; on failure optionally move to quarantine."""
    result = scan_file(path, cfg)
    if result.get("ok"):
        return result
    if quarantine_dir is not None and write:
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        dest = quarantine_dir / path.name
        if dest.exists():
            dest = quarantine_dir / f"{path.stem}.bad{path.suffix}"
        try:
            shutil.move(str(path), str(dest))
            result["quarantine_path"] = str(dest)
        except OSError as exc:
            result["issues"] = list(result.get("issues") or []) + [
                _issue("quarantine_move_failed", str(exc), severity="error")
            ]
    return result


def tax_xml_text(xml_text: str, cfg: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    """Convenience for archive pipeline: return (xml, result). Raises on quarantine."""
    result = tax_xml(xml_text, cfg)
    if not result.get("ok") or result.get("xml") is None:
        raise ValueError(
            "sheep tax quarantine: "
            + ", ".join(i.get("code", "?") for i in (result.get("issues") or []))
        )
    return str(result["xml"]), result


def _cli_row(result: dict[str, Any]) -> dict[str, Any]:
    """JSON-friendly summary without dumping full genome XML."""
    return {k: v for k, v in result.items() if k != "xml"}


def main(argv: list[str] | None = None) -> int:
    """CLI entry for scan/batch; returns 0 if all ok else 1."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--config", default="configs/jellyflam3.yaml")

    ap = argparse.ArgumentParser(
        description="JellyFlam3 sheep tax — scan/repair .flam3 genomes (guide 06)",
        parents=[parent],
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Scan file(s); repair in place by default", parents=[parent])
    p_scan.add_argument("paths", nargs="+", type=Path)
    p_scan.add_argument(
        "--no-repair",
        action="store_true",
        help="Report only (still uses tax_xml with repair=false via config override)",
    )
    p_scan.add_argument("--json", action="store_true")

    p_batch = sub.add_parser(
        "batch", help="Recurse a directory for *.flam3", parents=[parent]
    )
    p_batch.add_argument("path", type=Path)
    p_batch.add_argument("--quarantine", action="store_true", help="Move failures to quarantine")
    p_batch.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)
    cfg_path = Path(args.config)
    if cfg_path.is_file():
        cfg = load_config(cfg_path)
    else:
        # Scan/repair works with defaults; batch --quarantine needs a real config.
        log.warning("config not found (%s); using sheep_tax defaults", cfg_path)
        cfg = {"sheep_tax": {"enabled": True, "repair": True}, "_repo_root": str(Path.cwd())}
    if getattr(args, "no_repair", False):
        cfg = dict(cfg)
        st = dict(cfg.get("sheep_tax") or {})
        st["repair"] = False
        cfg["sheep_tax"] = st

    if args.cmd == "scan":
        rows = [scan_file(p, cfg) for p in args.paths]
        if args.json:
            print(json.dumps([_cli_row(r) for r in rows], indent=2))
        else:
            for r in rows:
                print(
                    f"{r.get('path')}: status={r.get('status')} ok={r.get('ok')} "
                    f"issues={len(r.get('issues') or [])}"
                )
        return 0 if all(r.get("ok") for r in rows) else 1

    if args.cmd == "batch":
        root = args.path
        files = sorted(root.rglob("*.flam3")) if root.is_dir() else [root]
        qdir = resolve_path(cfg, "genomes_quarantine") if args.quarantine else None
        rows = []
        for p in files:
            if args.quarantine:
                rows.append(tax_path(p, cfg, quarantine_dir=qdir, write=True))
            else:
                rows.append(scan_file(p, cfg))
        if args.json:
            print(json.dumps([_cli_row(r) for r in rows], indent=2))
        else:
            ok_n = sum(1 for r in rows if r.get("ok"))
            print(f"taxed {len(rows)} file(s): ok={ok_n} fail={len(rows) - ok_n}")
            for r in rows:
                if not r.get("ok"):
                    print(f"  FAIL {r.get('path')}: {[i.get('code') for i in r.get('issues') or []]}")
        return 0 if all(r.get("ok") for r in rows) else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
