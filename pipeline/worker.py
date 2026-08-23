"""Purpose: Job queue worker — genome → MP4 → ffprobe gates → catalog ingest.

Requirements: flam3-genome/animate, ffmpeg/ffprobe, configs/jellyflam3.yaml; idle gate, sheep tax, TV-optimize.

Usage: ``python3 -m pipeline.worker [--once GENOME]`` (polls genomes_inbox by default).

Assumptions: Single-threaded; sheep tax then TV-port before render; successful genomes archive to genomes_done.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from pipeline.choose_duration import (
    assert_duration_in_band,
    choose_nframes,
    duration_for_nframes,
)
from pipeline.genome_signals import estimate_queue_pressure, extract_genome_signals
from pipeline.config import load_config, resolve_path
from pipeline.cpu_limit import effective_cpus, ffmpeg_thread_args, flam3_nthreads, wrap_cmd
from pipeline.flock_artwork import apply_flock_artwork
from pipeline.idle_gate import is_gate_open
from pipeline.license_filter import infer_tags_from_genome
from pipeline.job_recovery import reclaim_orphans
from pipeline.media_layout import (
    ensure_catalog_dir,
    ensure_catalog_file_mode,
    repair_by_generation_perms,
)
from pipeline.tv_optimize import tv_optimize_file
from pipeline.tool_lookup import tool as _tool

log = logging.getLogger("jellyflam3.worker")


def install_catalog_mp4(out_tmp: Path, dest: Path) -> None:
    """Move encode output into the catalog path, rotating any prior MP4 to ``*.mp4.prev``.

    Same-Id re-furnace (shears modify / refactor apply) is allowed; one prior
    generation is kept so a bad encode does not silently erase the flock copy.
    """
    if dest.is_file():
        prev = dest.with_suffix('.mp4.prev')
        if prev.is_file():
            try:
                prev.unlink()
            except OSError as exc:
                log.warning("could not remove stale catalog prev %s: %s", prev, exc)
        try:
            dest.replace(prev)
            log.warning("catalog replace: moved existing %s -> %s", dest.name, prev.name)
        except OSError as exc:
            raise RuntimeError(
                f"catalog MP4 already exists and could not be rotated aside: {dest} ({exc})"
            ) from exc
    shutil.move(str(out_tmp), str(dest))


def quarantine_genome(src: Path, quarantine: Path, *, remove_src: bool = False) -> Path:
    """Copy ``src`` into quarantine; raise if the copy cannot be written."""
    quarantine.mkdir(parents=True, exist_ok=True)
    dest = quarantine / src.name
    if dest.exists():
        dest = quarantine / f"{src.stem}.{uuid.uuid4().hex[:8]}{src.suffix}"
    try:
        shutil.copy2(src, dest)
    except OSError as exc:
        raise RuntimeError(f"quarantine copy failed {src} -> {dest}: {exc}") from exc
    if remove_src:
        try:
            src.unlink(missing_ok=True)
        except OSError as exc:
            raise RuntimeError(f"quarantine remove failed for {src}: {exc}") from exc
    return dest


def claim_inbox_genome(src: Path, work: Path, inbox: Path) -> Path:
    """Atomically move an inbox genome into ``work`` so concurrent seeders cannot overwrite it.

    If ``src`` is not under ``inbox``, return ``src`` unchanged (e.g. ``--once`` paths).
    """
    try:
        src_res = src.resolve()
        inbox_res = inbox.resolve()
    except OSError:
        return src
    if src_res.parent != inbox_res:
        return src
    claimed = work / src.name
    try:
        os.replace(src_res, claimed)
    except OSError as exc:
        raise RuntimeError(f"inbox claim failed for {src.name}: {exc}") from exc
    return claimed


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_job_state(work: Path, state: dict[str, Any]) -> None:
    """Persist job.json under the work dir with an updated_at stamp."""
    state["updated_at"] = _utc_now()
    (work / "job.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _run(
    cmd: list[str],
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    *,
    cfg: dict[str, Any] | None = None,
    limit_cpu: bool = False,
) -> None:
    """Run subprocess (optionally CPU-wrapped); raise on non-zero exit."""
    argv = wrap_cmd(cfg, cmd) if (limit_cpu and cfg is not None) else cmd
    log.info("exec: %s", " ".join(argv))
    subprocess.run(argv, check=True, env=env, cwd=str(cwd) if cwd else None)


def free_space_gb(path: Path) -> float:
    """Free disk space under ``path`` in GiB (creates path if needed)."""
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    return usage.free / (1024**3)


def ffprobe_duration(ffprobe: str, media: Path) -> float:
    """Return media duration seconds via ffprobe format.duration."""
    out = subprocess.check_output(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media),
        ],
        text=True,
    ).strip()
    return float(out)


def ffprobe_video_ok(ffprobe: str, media: Path, cfg: dict[str, Any]) -> None:
    """Assert first video stream is h264 with expected pix_fmt; raise ValueError if not."""
    out = subprocess.check_output(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,profile,pix_fmt",
            "-of",
            "json",
            str(media),
        ],
        text=True,
    )
    data = json.loads(out)
    streams = data.get("streams") or []
    if not streams:
        raise ValueError("no video stream")
    s = streams[0]
    if s.get("codec_name") != "h264":
        raise ValueError(f"expected h264, got {s.get('codec_name')}")
    enc = cfg.get("encode") or {}
    want_pix = enc.get("pix_fmt", "yuv420p")
    if s.get("pix_fmt") and s.get("pix_fmt") != want_pix:
        raise ValueError(f"expected pix_fmt {want_pix}, got {s.get('pix_fmt')}")


def wait_for_gate(cfg: dict[str, Any]) -> None:
    """Block until idle gate is open (no-op if idle_gate disabled)."""
    ig = cfg.get("idle_gate") or {}
    if not ig.get("enabled", True):
        return
    while not is_gate_open(cfg):
        log.info("gate closed; sleeping 15s")
        time.sleep(15)


def sheep_basename(src: Path) -> str:
    """Normalized electricsheep stem used for catalog MP4 / sidecar names."""
    from pipeline.sheep_names import normalize_filename, stem_of

    return stem_of(normalize_filename(src))


def genomes_done_dir(cfg: dict[str, Any]) -> Path:
    """Post-render genome archive (pedigree parent pool). Falls back beside inbox."""
    paths = cfg.get("paths") or {}
    if "genomes_done" in paths:
        return resolve_path(cfg, "genomes_done")
    return resolve_path(cfg, "genomes_inbox").parent / "done"


def archive_rendered_genome(cfg: dict[str, Any], src: Path) -> Path:
    """Move a successfully rendered inbox genome to ``genomes_done``.

    Keeps parents available for Phase 2 pedigree breeding (guide 07).
    """
    done = genomes_done_dir(cfg)
    done.mkdir(parents=True, exist_ok=True)
    dest = done / src.name
    if dest.exists():
        dest = done / f"{src.stem}.{uuid.uuid4().hex[:8]}{src.suffix}"
    shutil.move(str(src), str(dest))
    log.info("archived genome %s -> %s", src.name, dest)
    return dest


def process_genome(cfg: dict[str, Any], src: Path) -> Path:
    """Render one genome through tax → TV-port → animate → encode → catalog.

    Returns destination MP4 path. On failure updates job.json, copies to quarantine, re-raises.
    """
    render = cfg.get("render") or {}
    vod = cfg.get("vod") or {}
    enc = cfg.get("encode") or {}
    tools = cfg.get("tools") or {}

    frames_root = resolve_path(cfg, "frames_scratch")
    media_root = resolve_path(cfg, "media_library")
    template = resolve_path(cfg, "template")
    jobs_dir = resolve_path(cfg, "jobs_dir")
    quarantine = resolve_path(cfg, "genomes_quarantine")

    min_free = float(render.get("free_space_gb_min", 8))
    if free_space_gb(frames_root) < min_free:
        raise RuntimeError(f"insufficient free space under {frames_root} (< {min_free} GiB)")

    wait_for_gate(cfg)

    job_id = uuid.uuid4().hex[:12]
    work = jobs_dir / job_id
    frame_dir = frames_root / job_id
    work.mkdir(parents=True, exist_ok=True)
    frame_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "id": job_id,
        "src": str(src),
        "state": "queued",
        "started_at": _utc_now(),
    }
    _write_job_state(work, state)

    try:
        inbox = resolve_path(cfg, "genomes_inbox")
        claimed = claim_inbox_genome(src, work, inbox)
        state["claimed"] = claimed != src
        src = claimed
        state["src"] = str(src)
        _write_job_state(work, state)

        seed_src = src
        tax_opts = cfg.get("sheep_tax") or {}
        if bool(tax_opts.get("enabled", True)) and bool(
            tax_opts.get("on_worker_ingest", True)
        ):
            from pipeline.sheep_tax import scan_file

            taxed = work / "taxed.flam3"
            shutil.copy2(src, taxed)
            tax = scan_file(taxed, cfg)
            state["sheep_tax"] = {
                "status": tax.get("status"),
                "issues": tax.get("issues"),
                "ok": tax.get("ok"),
            }
            if not tax.get("ok"):
                quarantine_genome(src, quarantine, remove_src=bool(state.get("claimed")))
                raise RuntimeError(
                    f"sheep tax quarantine: {[i.get('code') for i in (tax.get('issues') or [])]}"
                )
            seed_src = taxed
            log.info(
                "sheep tax %s: status=%s",
                src.name,
                tax.get("status"),
            )

        # TV-port: 16:9 aspect + Gold Sheep Lite quality + ambient OkLCh palette
        optimized = work / "tv_optimized.flam3"
        _dest, harmony = tv_optimize_file(seed_src, optimized, cfg)
        seed_for_sequence = optimized

        genome_xml = optimized.read_text(encoding="utf-8", errors="replace")
        signals = extract_genome_signals(genome_xml)
        try:
            inbox = resolve_path(cfg, "genomes_inbox")
            pending = len(list(inbox.glob("*.flam3"))) if inbox.is_dir() else 0
            signals["queue_pressure"] = estimate_queue_pressure(pending)
        except Exception:  # noqa: BLE001
            signals["queue_pressure"] = 0.0

        job_ctx: dict[str, Any] = {"src": str(src), "signals": signals}
        nframes = choose_nframes(cfg, job_ctx)
        fps = int(vod.get("fps", 24))
        duration_target = duration_for_nframes(nframes, fps)
        state.update(
            {
                "state": "rendering",
                "nframes": nframes,
                "fps": fps,
                "duration_target_sec": duration_target,
                "signals": {
                    k: signals[k]
                    for k in (
                        "complexity",
                        "xform_count",
                        "animate_count",
                        "flame_count",
                        "multi_flame_risk",
                        "rotate_deg",
                        "rotate_turns",
                        "rotate_closed",
                        "queue_pressure",
                        "period_candidates_sec",
                        "fundamental_period_sec",
                    )
                    if k in signals
                },
                "duration_meta": job_ctx.get("duration_meta"),
            }
        )
        if harmony is not None:
            state["palette"] = {
                "mode": harmony.mode,
                "seed_hex": harmony.seed_hex,
                "complement_hex": harmony.complement_hex,
            }
        _write_job_state(work, state)

        sequenced = work / "sequenced.flam3"
        env = os.environ.copy()
        env["sequence"] = str(seed_for_sequence)
        env["nframes"] = str(nframes)
        if template.is_file():
            env["template"] = str(template)
        genome_bin = _tool(cfg, "flam3_genome")
        with sequenced.open("w", encoding="utf-8") as out:
            subprocess.run([genome_bin], check=True, env=env, stdout=out)

        wait_for_gate(cfg)
        animate_bin = _tool(cfg, "flam3_animate")
        prefix = str(frame_dir / "f")
        env_a = os.environ.copy()
        env_a["in"] = str(sequenced)
        env_a["prefix"] = prefix
        env_a["format"] = "png"
        nthreads = flam3_nthreads(cfg)
        if nthreads > 0:
            env_a["nthreads"] = str(nthreads)
        cpus = effective_cpus(cfg)
        log.info("cpu limit: max_cpus=%s flam3_nthreads=%s", cpus, nthreads or "auto")
        _run([animate_bin], env=env_a, cfg=cfg, limit_cpu=True)

        state["state"] = "encoding"
        _write_job_state(work, state)
        wait_for_gate(cfg)

        # Discover first frame pattern
        frames = sorted(frame_dir.glob("*.png"))
        if not frames:
            frames = sorted(frame_dir.glob("f*.png"))
        if not frames:
            raise RuntimeError(f"no frames produced in {frame_dir}")

        # flam3-animate naming varies; build concat-friendly pattern if possible
        sample = frames[0].name
        # Prefer %05d style if numeric suffix
        pattern = str(frame_dir / "f%05d.png")
        if not (frame_dir / "f00000.png").exists() and not (frame_dir / "f0000.png").exists():
            # fallback: use first file's glob via concat demuxer
            concat = work / "concat.txt"
            with concat.open("w", encoding="utf-8") as fh:
                for f in frames:
                    fh.write(f"file '{f.resolve().as_posix()}'\n")
                    fh.write(f"duration {1/fps}\n")
            ffmpeg = _tool(cfg, "ffmpeg")
            out_tmp = work / "out.mp4"
            _run(
                [
                    ffmpeg,
                    "-y",
                    *ffmpeg_thread_args(cfg),
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat),
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-c:v",
                    "libx264",
                    "-profile:v",
                    str(enc.get("profile", "high")),
                    "-level",
                    str(enc.get("level", "4.2")),
                    "-pix_fmt",
                    str(enc.get("pix_fmt", "yuv420p")),
                    "-b:v",
                    str(enc.get("video_bitrate", "4M")),
                    "-maxrate",
                    str(enc.get("maxrate", "6M")),
                    "-bufsize",
                    str(enc.get("bufsize", "8M")),
                    "-g",
                    str(nframes),
                    "-c:a",
                    "aac",
                    "-shortest",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-movflags",
                    "+faststart",
                    str(out_tmp),
                ],
                cfg=cfg,
                limit_cpu=True,
            )
        else:
            ffmpeg = _tool(cfg, "ffmpeg")
            out_tmp = work / "out.mp4"
            # try 5-digit then 4-digit
            for pat in (str(frame_dir / "f%05d.png"), str(frame_dir / "f%04d.png"), pattern):
                try:
                    _run(
                        [
                            ffmpeg,
                            "-y",
                            *ffmpeg_thread_args(cfg),
                            "-framerate",
                            str(fps),
                            "-i",
                            pat,
                            "-f",
                            "lavfi",
                            "-i",
                            "anullsrc=channel_layout=stereo:sample_rate=48000",
                            "-c:v",
                            "libx264",
                            "-profile:v",
                            str(enc.get("profile", "high")),
                            "-level",
                            str(enc.get("level", "4.2")),
                            "-pix_fmt",
                            str(enc.get("pix_fmt", "yuv420p")),
                            "-b:v",
                            str(enc.get("video_bitrate", "4M")),
                            "-maxrate",
                            str(enc.get("maxrate", "6M")),
                            "-bufsize",
                            str(enc.get("bufsize", "8M")),
                            "-g",
                            str(nframes),
                            "-c:a",
                            "aac",
                            "-shortest",
                            "-map",
                            "0:v:0",
                            "-map",
                            "1:a:0",
                            "-movflags",
                            "+faststart",
                            str(out_tmp),
                        ],
                        cfg=cfg,
                        limit_cpu=True,
                    )
                    break
                except subprocess.CalledProcessError:
                    continue
            if not out_tmp.is_file():
                raise RuntimeError("ffmpeg encode failed for all frame patterns")

        state["state"] = "gating"
        _write_job_state(work, state)
        ffprobe = _tool(cfg, "ffprobe")
        dur = ffprobe_duration(ffprobe, out_tmp)
        assert_duration_in_band(dur, cfg)
        ffprobe_video_ok(ffprobe, out_tmp, cfg)

        from pipeline.sheep_names import catalog_generation

        base = sheep_basename(src)
        gen = catalog_generation(base)
        dest_dir = ensure_catalog_dir(media_root / "by-generation" / gen)
        dest = dest_dir / f"{base}.mp4"
        install_catalog_mp4(out_tmp, dest)

        tags = infer_tags_from_genome(src)
        # Phase 1 license SoT: sidecar next to MP4 (Items API Tags are best-effort).
        sidecar: dict[str, Any] = {
            "id": base,
            "license": "cc-by-nc" if "cc-by-nc" in tags else ("cc-by" if "cc-by" in tags else "unknown"),
            "tags": tags,
            "nframes": nframes,
            "fps": fps,
            "duration_sec": dur,
            "duration_target_sec": duration_target,
            "edition": (cfg.get("render") or {}).get("edition") or "gold_sheep_lite",
            "signals": state.get("signals"),
            "duration_meta": state.get("duration_meta"),
        }
        if harmony is not None:
            sidecar["palette"] = {
                "mode": harmony.mode,
                "seed_hex": harmony.seed_hex,
                "complement_hex": harmony.complement_hex,
            }
        # Piece D: mid-loop poster on disk + Jellyfin Primary (soft-fail; never fail ingest).
        try:
            apply_flock_artwork(
                cfg,
                dest,
                sidecar,
                duration_sec=dur,
                tags=tags,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("flock artwork hooks failed for %s: %s", dest, exc)
            sidecar.setdefault(
                "jellyfin_image",
                {"ok": False, "status": "failed", "error": str(exc)},
            )

        # Preserve Pathway B refactor history across ingest (worker rebuilds sidecar).
        try:
            from pipeline.refactor import merge_pending_refactor_into_sidecar

            merge_pending_refactor_into_sidecar(
                sidecar,
                catalog_mp4=dest,
                inbox_flam3=src,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("refactor history merge failed for %s: %s", dest, exc)

        (dest_dir / f"{base}.jellyflam3.json").write_text(
            json.dumps(sidecar, indent=2), encoding="utf-8"
        )
        ensure_catalog_file_mode(dest)
        ensure_catalog_file_mode(dest_dir / f"{base}-poster.jpg")
        ensure_catalog_file_mode(dest_dir / f"{base}.jellyflam3.json")

        state.update({"state": "ingested", "dest": str(dest), "duration_sec": dur, "tags": tags})
        _write_job_state(work, state)
        shutil.rmtree(frame_dir, ignore_errors=True)
        # Claimed genomes live under the job work dir; archive them here so callers
        # that still hold the old inbox path do not miss the move to genomes_done.
        if state.get("claimed") and src.is_file():
            archive_rendered_genome(cfg, src)
        return dest
    except Exception as exc:
        state["state"] = "failed"
        state["error"] = str(exc)
        _write_job_state(work, state)
        if src.is_file():
            try:
                quarantine_genome(src, quarantine, remove_src=bool(state.get("claimed")))
            except RuntimeError as qexc:
                log.error("%s", qexc)
                state["quarantine_error"] = str(qexc)
                _write_job_state(work, state)
        shutil.rmtree(frame_dir, ignore_errors=True)
        raise


def poll_inbox(cfg: dict[str, Any]) -> None:
    """Watch genomes_inbox forever: reclaim orphans, process .flam3/.flame, archive done."""
    inbox = resolve_path(cfg, "genomes_inbox")
    inbox.mkdir(parents=True, exist_ok=True)
    # Single-threaded worker: reclaim in-flight jobs with no live animate/ffmpeg.
    wr = cfg.get("worker") or {}
    if wr.get("reclaim_orphans_on_start", True):
        actions = reclaim_orphans(cfg, startup=False, requeue=wr.get("requeue_orphans", True))
        n = sum(1 for a in actions if a.outcome in ("orphaned", "superseded"))
        log.info("startup orphan reclaim: %s job(s)", n)
    log.info("watching inbox %s", inbox)
    while True:
        wait_for_gate(cfg)
        files = sorted(inbox.glob("*.flam3")) + sorted(inbox.glob("*.flame"))
        for src in files:
            log.info("processing %s", src)
            try:
                dest = process_genome(cfg, src)
                log.info("ingested %s", dest)
                # Non-inbox --once-style paths are not claimed; archive leftover inbox file.
                if src.is_file():
                    archive_rendered_genome(cfg, src)
            except Exception as exc:  # noqa: BLE001
                log.exception("job failed for %s: %s", src, exc)
                # Claim moves the genome into the job work dir; process_genome quarantines.
                # If claim never ran, best-effort quarantine any leftover inbox file.
                if src.is_file():
                    try:
                        quarantine_genome(src, resolve_path(cfg, "genomes_quarantine"), remove_src=True)
                    except RuntimeError as qexc:
                        log.error("post-fail quarantine incomplete for %s: %s", src, qexc)
        time.sleep(10)


def main(argv: list[str] | None = None) -> int:
    """CLI: ensure runtime dirs, optional --once genome, else poll inbox."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="JellyFlam3 render worker")
    p.add_argument("--config", default="configs/jellyflam3.yaml")
    p.add_argument("--once", type=Path, help="Process a single genome file and exit")
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    # Ensure runtime dirs exist
    for key in ("jobs_dir", "frames_scratch", "media_library", "genomes_inbox", "genomes_quarantine"):
        try:
            resolve_path(cfg, key).mkdir(parents=True, exist_ok=True)
        except Exception:  # noqa: BLE001
            pass
    try:
        genomes_done_dir(cfg).mkdir(parents=True, exist_ok=True)
    except Exception:  # noqa: BLE001
        pass
    # Jellyfin (group jellyflam3) needs group-write on by-generation/* for .trickplay
    try:
        media = resolve_path(cfg, "media_library")
        stats = repair_by_generation_perms(media)
        log.info(
            "catalog perms: dirs=%s files=%s dir_errors=%s file_errors=%s",
            stats["dirs"],
            stats["files"],
            stats["dir_errors"],
            stats["file_errors"],
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("catalog perms repair skipped: %s", exc)
    if args.once:
        src = Path(args.once)
        dest = process_genome(cfg, src)
        if src.is_file():
            archive_rendered_genome(cfg, src)
        print(dest)
        return 0
    poll_inbox(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
