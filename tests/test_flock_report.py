"""Read-only flock report: live counts, votes, history, and alias lookup."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pipeline.flock_report import build_report, format_report, main

STEM_A = "electricsheep.247.16653"
STEM_B = "electricsheep.244.01221"
STEM_T = "electricsheep.tuple.247.16653_to_244.01221"
PARKED = "electricsheep.247.34067"


def _cfg(tmp: Path) -> dict:
    media = tmp / "media"
    inbox = tmp / "genomes" / "inbox"
    quarantine = tmp / "genomes" / "quarantine"
    done = tmp / "genomes" / "done"
    jobs = tmp / "jobs"
    frames = tmp / "frames"
    peers = tmp / "genomes" / "peers"
    state = tmp / "state"
    for directory in (
        media,
        inbox,
        quarantine,
        done,
        jobs,
        frames,
        peers / "inbox",
        peers / "share-out",
        state,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return {
        "_repo_root": str(tmp),
        "paths": {
            "genomes_inbox": str(inbox),
            "genomes_quarantine": str(quarantine),
            "genomes_done": str(done),
            "jobs_dir": str(jobs),
            "frames_scratch": str(frames),
            "media_library": str(media),
            "status_file": str(state / "idle_gate_status.json"),
            "worker_drain_file": str(state / "worker_drain.json"),
        },
        "peering": {"peers_dir": str(peers)},
        "breed": {
            "idle_breed": {"history_file": str(state / "breed_idle_history.json")},
        },
        "idle_gate": {"enabled": True, "poll_interval_sec": 20},
        "jellyfin": {"url": "", "api_key": ""},
    }


def _live(media: Path, stem: str, gen: str, payload: dict, *, poster: bool) -> None:
    folder = media / "by-generation" / gen
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{stem}.mp4").write_bytes(b"mp4-bytes")
    (folder / f"{stem}.jellyflam3.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    if poster:
        stills = folder / "stills" / stem
        stills.mkdir(parents=True, exist_ok=True)
        (stills / f"{stem}-poster.jpg").write_bytes(b"jpg")


def _genome(directory: Path, stem: str) -> None:
    (directory / f"{stem}.flam3").write_text("<flame/>", encoding="utf-8")


def _catalog(tmp: Path) -> dict:
    cfg = _cfg(tmp)
    media = Path(cfg["paths"]["media_library"])
    _live(
        media,
        STEM_A,
        "247",
        {
            "id": STEM_A,
            "license": "cc-by",
            "alias": "quiet_turing",
            "alias_source": "human",
            "duration_sec": 29.0,
            "type": "loop",
            "signals": {"orbit_frozen": False},
            "viewer_feedback": {
                "likes": 3,
                "loves": 1,
                "votes": 4,
                "last_voted_at": "2026-10-03T00:00:00Z",
                "share_candidate": True,
            },
            "refactor": [
                {
                    "ts": "2026-10-04T00:00:00Z",
                    "status": "apply",
                    "reason": ["palette complementary"],
                }
            ],
        },
        poster=True,
    )
    _live(
        media,
        STEM_B,
        "244",
        {
            "id": STEM_B,
            "license": "cc-by-nc",
            "duration_sec": 19.0,
            "type": "loop",
        },
        poster=False,
    )
    _live(
        media,
        STEM_T,
        "tuple",
        {
            "id": STEM_T,
            "license": "cc-by",
            "alias": "amber_salk",
            "alias_source": "auto",
            "duration_sec": 40.0,
            "type": "tuple",
            "viewer_feedback": {
                "likes": 1,
                "loves": 0,
                "votes": 1,
                "last_voted_at": "2026-10-02T00:00:00Z",
                "share_candidate": True,
            },
        },
        poster=True,
    )
    parked = media / "_refactor-quarantine" / "247"
    parked.mkdir(parents=True)
    parked_mp4 = parked / f"{PARKED}.mp4"
    parked_mp4.write_bytes(b"parked")
    preview = media / "_refactor-preview" / "247"
    preview.mkdir(parents=True)
    (preview / f"{STEM_A}.mp4").write_bytes(b"preview")

    done = Path(cfg["paths"]["genomes_done"])
    for stem in (STEM_A, STEM_B, STEM_T):
        _genome(done, stem)
    quarantined = Path(cfg["paths"]["genomes_quarantine"]) / f"{PARKED}.flam3"
    quarantined.write_text("<flame/>", encoding="utf-8")
    old = datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()
    os.utime(parked_mp4, (old, old))
    os.utime(quarantined, (old, old))

    inbox = Path(cfg["paths"]["genomes_inbox"])
    older = inbox / "electricsheep.242.00001.flam3"
    newer = inbox / "electricsheep.242.00002.flam3"
    older.write_text("<flame/>", encoding="utf-8")
    newer.write_text("<flame/>", encoding="utf-8")
    older_stat = older.stat()
    newer_stat = newer.stat()
    ledger = tmp / "state" / "inbox_fifo.json"
    ledger.write_text(
        json.dumps(
            {
                "next_seq": 3,
                "files": {
                    newer.name: {
                        "seq": 1,
                        "dev": newer_stat.st_dev,
                        "ino": newer_stat.st_ino,
                    },
                    older.name: {
                        "seq": 2,
                        "dev": older_stat.st_dev,
                        "ino": older_stat.st_ino,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    before = ledger.read_bytes()

    history = tmp / "state" / "breed_idle_history.json"
    history.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "at": "2026-10-01T00:00:00Z",
                        "method": "cross",
                        "cross_method": "alternate",
                        "parents": [str(done / f"{STEM_A}.flam3"), str(done / f"{STEM_B}.flam3")],
                        "staged": [str(inbox / "electricsheep.pedigree.cross.abc.flam3")],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    job = Path(cfg["paths"]["jobs_dir"]) / "abc123"
    job.mkdir()
    (job / "job.json").write_text(
        json.dumps(
            {
                "state": "ingested",
                "src": str(done / f"{STEM_B}.flam3"),
                "updated_at": "2026-09-01T00:00:00Z",
                "duration_sec": 19.0,
            }
        ),
        encoding="utf-8",
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    Path(cfg["paths"]["status_file"]).write_text(
        json.dumps({"gate": "open", "updated_at": now}),
        encoding="utf-8",
    )
    share = Path(cfg["peering"]["peers_dir"]) / "share-out" / f"{STEM_A}.flam3"
    share.write_text("<flame/>", encoding="utf-8")
    cfg["_ledger_before"] = before
    cfg["_ledger_path"] = str(ledger)
    return cfg


def test_live_flock_excludes_parks_and_ranks_votes(tmp_path: Path):
    cfg = _catalog(tmp_path)
    report = build_report(cfg, host="sample", generated_at="2026-10-10T17:09:00-07:00")
    size = report["size"]
    assert size["sheep"] == 3
    assert size["loops"] == 2
    assert size["tuples"] == 1
    assert size["parked_catalog"] == 1
    assert size["preview_catalog"] == 1
    assert size["alias_present"] == 2
    assert size["alias_missing"] == 1
    assert size["license"]["cc-by"] == 2
    assert size["license"]["cc-by-nc"] == 1
    assert size["inbox_flam3"] == 2
    assert size["inbox_head"] == "electricsheep.242.00002"
    assert size["quarantine_flam3"] == 1
    assert Path(cfg["_ledger_path"]).read_bytes() == cfg["_ledger_before"]

    condition = report["condition"]
    assert condition["missing_poster"] == [STEM_B]
    assert PARKED not in condition["catalog_without_genome"]
    assert condition["signals_recorded"] == 1
    assert condition["score"] is None

    assert report["status"]["idle_gate"] == "open"
    assert report["status"]["drain"] == "off"
    assert report["status"]["worker"]["state"] == "idle"
    assert report["status"]["share_out_files"] == [f"{STEM_A}.flam3"]

    voting = report["voting"]
    assert voting["with_votes"] == 2
    assert voting["unvoted"] == 1
    assert voting["votes"] == 5
    assert voting["likes"] == 4
    assert voting["loves"] == 1
    assert voting["share_candidate"] == 2
    assert [row["stem"] for row in voting["top"]] == [STEM_A, STEM_T]
    assert STEM_B not in [row["stem"] for row in voting["top"]]

    kinds = [event["kind"] for event in report["history"]["events"]]
    assert kinds[0] == "refactor"
    assert "vote" in kinds
    assert "breed" in kinds
    assert kinds.index("vote") < kinds.index("breed")

    text = format_report(report)
    assert "== voting ==" in text
    assert "== history ==" in text
    assert "quiet_turing" in text
    assert "omitted   pass --score" in text
    assert STEM_B not in text.split("== voting ==")[1].split("== history ==")[0]


def test_alias_stem_and_unknown_alias(tmp_path: Path, capsys):
    cfg = _catalog(tmp_path)
    report = build_report(cfg, stem=STEM_A, host="sample")
    assert report["scope"] == STEM_A
    assert report["size"]["alias"] == "quiet_turing"
    assert report["size"]["in_catalog"] is True
    assert report["voting"]["votes"] == 4
    assert report["voting"]["unvoted"] == 0
    assert report["status"]["sheep"] == "live"
    assert all(STEM_A in event["stems"] for event in report["history"]["events"])

    yaml_path = tmp_path / "configs" / "jellyflam3.yaml"
    yaml_path.parent.mkdir()
    lines = ["paths:"]
    for key, value in cfg["paths"].items():
        lines.append(f"  {key}: {Path(value).as_posix()}")
    lines.append("peering:")
    lines.append(f"  peers_dir: {Path(cfg['peering']['peers_dir']).as_posix()}")
    lines.append("breed:")
    lines.append("  idle_breed:")
    history_file = Path(cfg["breed"]["idle_breed"]["history_file"]).as_posix()
    lines.append(f"    history_file: {history_file}")
    lines.append("idle_gate:")
    lines.append("  enabled: true")
    lines.append("  poll_interval_sec: 20")
    yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    missing = main(["--config", str(yaml_path), "--stem", "missing_name"])
    assert missing == 2
    assert "alias not found: missing_name" in capsys.readouterr().err

    found = main(["--config", str(yaml_path), "--stem", "quiet_turing", "--json"])
    assert found == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stem"] == STEM_A
    assert payload["voting"]["votes"] == 4


def test_score_flag_uses_scan_counts(tmp_path: Path, monkeypatch):
    cfg = _catalog(tmp_path)

    class Row:
        def __init__(self, verdict: str) -> None:
            self.verdict = verdict

    def fake_scan(_cfg, sheep_id=None, limit=None):
        assert sheep_id is None
        return [Row("ok"), Row("ok"), Row("candidate")]

    monkeypatch.setattr("pipeline.refactor_scan.scan_catalog", fake_scan)
    report = build_report(cfg, score=True, host="sample")
    assert report["condition"]["score"] == {
        "ok": 2,
        "candidate": 1,
        "quarantine": 0,
    }
    assert "ok 2  candidate 1  quarantine 0" in format_report(report)
