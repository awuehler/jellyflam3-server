"""Purpose: Stage .flam3 genomes into the worker inbox for ingest.

Requirements: configs/jellyflam3.yaml; optional flam3-genome; archive_seed for --archive.

Usage: ``python3 -m pipeline.seed_inbox`` with PATH(s), --samples, --archive, --generate, and/or --mutate.

Assumptions: Feedstock = local samples/paths, flam3-genome random|mutate, or Electric Sheep archive pick + TV-port; inbox names via sheep_names.
"""

from __future__ import annotations

import argparse
import logging
import random
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

from pipeline.archive_seed import default_fetch_count, ensure_manifest, materialize_sheep, pick_random
from pipeline.config import load_config, resolve_path
from pipeline.tool_lookup import tool as _tool

log = logging.getLogger("jellyflam3.seed_inbox")

_FLAME_SUFFIXES = {".flam3", ".flame"}


def inbox_filename(src: Path) -> str:
    """Normalize inbox basename to electricsheep.<kind>.<id>.flam3."""
    from pipeline.sheep_names import normalize_filename

    return normalize_filename(src)


def sample_pool(repo_root: Path) -> list[Path]:
    """Collect non-template .flam3/.flame under ``genomes/samples`` only.

    Encode templates live under ``configs/templates/`` (not in this pool).
    Phase 3 may later prefer ``genomes/pedigree/`` when present.
    """
    from pipeline.sheep_names import is_template_genome

    d = repo_root / "genomes" / "samples"
    if not d.is_dir():
        return []
    return sorted(
        p
        for p in d.iterdir()
        if p.suffix.lower() in _FLAME_SUFFIXES and not is_template_genome(p)
    )


def catalog_mp4_exists(cfg: dict[str, Any], inbox_name: str) -> bool:
    """True if media_library already has a catalog MP4 for this inbox basename."""
    from pipeline.sheep_names import catalog_generation, stem_of

    media = resolve_path(cfg, "media_library")
    base = stem_of(inbox_name)
    gen = catalog_generation(base)
    return (media / "by-generation" / gen / f"{base}.mp4").is_file()


def stage_file(
    src: Path,
    inbox: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
    move: bool = False,
) -> Path | None:
    """Copy or move a genome into inbox under normalized name; None if skipped."""
    if not src.is_file():
        raise FileNotFoundError(src)
    if src.suffix.lower() not in _FLAME_SUFFIXES:
        raise ValueError(f"not a genome file: {src}")

    dest = inbox / inbox_filename(src)
    if dest.exists() and not force:
        log.info("skip (already in inbox): %s", dest.name)
        return None
    if dry_run:
        log.info("dry-run would %s %s -> %s", "move" if move else "copy", src, dest)
        return dest
    inbox.mkdir(parents=True, exist_ok=True)
    if move:
        shutil.move(str(src), str(dest))
    else:
        shutil.copy2(src, dest)
    log.info("staged %s", dest)
    return dest


def generate_random(cfg: dict[str, Any], inbox: Path, *, dry_run: bool = False) -> Path:
    """Create one random genome via flam3-genome into inbox; return dest path."""
    import os

    from pipeline.sheep_names import random_filename

    genome_bin = _tool(cfg, "flam3_genome")
    name = random_filename()
    dest = inbox / name
    if dry_run:
        log.info("dry-run would generate %s via %s", dest, genome_bin)
        return dest
    inbox.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    template = resolve_path(cfg, "template")
    if template.is_file():
        env["template"] = str(template)
    with dest.open("w", encoding="utf-8") as out:
        subprocess.run([genome_bin], check=True, stdout=out, env=env)
    if dest.stat().st_size < 32:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"{genome_bin} produced empty genome")
    log.info("generated %s", dest)
    return dest


def mutate_seed(
    cfg: dict[str, Any],
    seed: Path,
    inbox: Path,
    *,
    dry_run: bool = False,
) -> Path:
    """Mutate ``seed`` with flam3-genome into inbox; return dest path."""
    import os

    from pipeline.sheep_names import mutate_filename

    genome_bin = _tool(cfg, "flam3_genome")
    name = mutate_filename()
    dest = inbox / name
    if dry_run:
        log.info("dry-run would mutate %s -> %s", seed, dest)
        return dest
    inbox.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "mutate": str(seed)}
    template = resolve_path(cfg, "template")
    if template.is_file():
        env["template"] = str(template)
    with dest.open("w", encoding="utf-8") as out:
        subprocess.run([genome_bin], check=True, stdout=out, env=env)
    if dest.stat().st_size < 32:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"{genome_bin} mutate produced empty genome")
    log.info("mutated %s -> %s", seed, dest)
    return dest


def select_samples(pool: list[Path], count: int | None, *, all_samples: bool) -> list[Path]:
    """Pick all samples, a random subset of size ``count``, or empty."""
    if not pool:
        return []
    if all_samples or count is None:
        return list(pool)
    if count <= 0:
        return []
    if count >= len(pool):
        return list(pool)
    return random.sample(pool, count)


def stage_archive(
    cfg: dict[str, Any],
    *,
    count: int = 1,
    refresh_manifest: bool = False,
    tv_port: bool = True,
    dry_run: bool = False,
    force: bool = False,
    skip_catalog: bool = True,
) -> list[Path]:
    """Fetch random archive sheep, optionally TV-port, stage into inbox."""
    pool = ensure_manifest(cfg, refresh=refresh_manifest)
    if not pool:
        raise RuntimeError("archive seed manifest is empty — try --refresh-manifest")
    inbox = resolve_path(cfg, "genomes_inbox")
    staged: list[Path] = []
    attempts = max(count * 4, count + 8)
    candidates = pick_random(pool, min(attempts, len(pool)))
    for sheep in candidates:
        if len(staged) >= count:
            break
        name = sheep.filename
        if skip_catalog and catalog_mp4_exists(cfg, name):
            log.info("skip (catalog exists): %s", name)
            continue
        dest = inbox / name
        if dest.exists() and not force and not dry_run:
            log.info("skip (already in inbox): %s", name)
            continue
        if dry_run:
            log.info("dry-run would fetch+stage %s (tv_port=%s)", sheep.name, tv_port)
            staged.append(dest)
            continue
        try:
            local = materialize_sheep(sheep, cfg, tv_port=tv_port)
        except Exception as exc:  # noqa: BLE001
            log.warning("archive fetch failed for %s: %s", sheep.name, exc)
            continue
        out = stage_file(local, inbox, dry_run=False, force=force, move=False)
        if out is not None:
            staged.append(out)
    if len(staged) < count:
        log.warning("staged %s/%s archive seeds (some fetches/skips failed)", len(staged), count)
    return staged


def run(
    cfg: dict[str, Any],
    *,
    paths: Iterable[Path] = (),
    use_samples: bool = False,
    all_samples: bool = False,
    count: int | None = None,
    generate: int = 0,
    mutate: Path | None = None,
    archive: bool = False,
    refresh_manifest: bool = False,
    tv_port: bool = True,
    dry_run: bool = False,
    force: bool = False,
    move: bool = False,
    skip_catalog: bool = True,
) -> list[Path]:
    """Orchestrate staging from archive/samples/paths/mutate/generate; return staged paths."""
    inbox = resolve_path(cfg, "genomes_inbox")
    staged: list[Path] = []
    sources: list[Path] = []

    if archive:
        n = count if count is not None and count > 0 else default_fetch_count(cfg)
        log.info("archive fetch_count=%s", n)
        staged.extend(
            stage_archive(
                cfg,
                count=n,
                refresh_manifest=refresh_manifest,
                tv_port=tv_port,
                dry_run=dry_run,
                force=force,
                skip_catalog=skip_catalog,
            )
        )

    if use_samples or all_samples:
        pool = sample_pool(Path(cfg["_repo_root"]))
        sources.extend(select_samples(pool, count if use_samples else None, all_samples=all_samples))
    sources.extend(Path(p) for p in paths)

    for src in sources:
        name = inbox_filename(src)
        if skip_catalog and catalog_mp4_exists(cfg, name):
            log.info("skip (catalog exists): %s", name)
            continue
        dest = stage_file(src, inbox, dry_run=dry_run, force=force, move=move)
        if dest is not None:
            staged.append(dest)

    if mutate is not None:
        n = count if count and count > 0 else 1
        for _ in range(n):
            staged.append(mutate_seed(cfg, mutate, inbox, dry_run=dry_run))

    for _ in range(max(0, generate)):
        staged.append(generate_random(cfg, inbox, dry_run=dry_run))

    return staged


def main(argv: list[str] | None = None) -> int:
    """CLI entry for seed-inbox; returns process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(
        description="Seed .flam3 genomes into the JellyFlam3 worker inbox",
    )
    p.add_argument("--config", default="configs/jellyflam3.yaml")
    p.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Local .flam3 / .flame files to copy into the inbox",
    )
    p.add_argument(
        "--samples",
        action="store_true",
        help="Stage from genomes/samples (non-template flock seeds)",
    )
    p.add_argument(
        "--all-samples",
        action="store_true",
        help="Stage every sample (implies --samples)",
    )
    p.add_argument(
        "--archive",
        action="store_true",
        help="Random-pick from Electric Sheep archive pool (gens 247–165 best 1.html/2.html/3.html), fetch, TV-port, stage",
    )
    p.add_argument(
        "--refresh-manifest",
        action="store_true",
        help="Re-scrape archive listing pages into configs/archive_seed_manifest.json",
    )
    p.add_argument(
        "--no-tv-port",
        action="store_true",
        help="With --archive: stage raw genome size (worker still resizes later)",
    )
    p.add_argument(
        "--count",
        type=int,
        default=None,
        help="With --archive: N seeds (default: random 3–7). With --samples: random N. With --mutate: N mutants",
    )
    p.add_argument(
        "--fetch-count",
        type=int,
        default=None,
        dest="fetch_count",
        help="Alias for --count when using --archive (limit random downloads)",
    )
    p.add_argument(
        "--generate",
        type=int,
        default=0,
        metavar="N",
        help="Create N random genomes via flam3-genome into the inbox",
    )
    p.add_argument(
        "--mutate",
        type=Path,
        default=None,
        help="Mutate this seed with flam3-genome into the inbox",
    )
    p.add_argument("--move", action="store_true", help="Move (not copy) PATH arguments")
    p.add_argument("--force", action="store_true", help="Overwrite matching inbox files")
    p.add_argument(
        "--skip-catalog",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Skip seeds that already have a catalog MP4 under media_library "
            "(default: on). Daily idle-breed plus ~10-day archive fill keep the "
            "furnace busy without re-rendering catalog sheep. "
            "Use --no-skip-catalog to re-stage / re-render existing catalog items."
        ),
    )
    p.add_argument("--dry-run", action="store_true", help="Print actions only")
    args = p.parse_args(argv)

    if not any(
        [
            args.paths,
            args.samples,
            args.all_samples,
            args.generate,
            args.mutate,
            args.archive,
            args.refresh_manifest,
        ]
    ):
        p.error(
            "provide PATH(s), --samples / --all-samples, --archive, --generate N, and/or --mutate SEED"
        )

    cfg_path = Path(args.config)
    if not cfg_path.is_file():
        alt = Path("configs/jellyflam3.yaml.example")
        if alt.is_file():
            log.warning("config %s missing; using %s", cfg_path, alt)
            cfg_path = alt
        else:
            raise SystemExit(f"config not found: {args.config}")

    cfg = load_config(cfg_path)

    count = args.count
    if args.fetch_count is not None:
        count = args.fetch_count

    if args.refresh_manifest and not args.archive:
        from pipeline.archive_seed import default_manifest_path

        pool = ensure_manifest(cfg, refresh=True)
        print(f"manifest {default_manifest_path(cfg)} count={len(pool)}")
        return 0

    staged = run(
        cfg,
        paths=args.paths,
        use_samples=args.samples or args.all_samples,
        all_samples=args.all_samples,
        count=count,
        generate=args.generate,
        mutate=args.mutate,
        archive=args.archive,
        refresh_manifest=args.refresh_manifest,
        tv_port=not args.no_tv_port,
        dry_run=args.dry_run,
        force=args.force,
        move=args.move,
        skip_catalog=args.skip_catalog,
    )
    print(f"staged {len(staged)} genome(s) into {resolve_path(cfg, 'genomes_inbox')}")
    for d in staged:
        print(d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
