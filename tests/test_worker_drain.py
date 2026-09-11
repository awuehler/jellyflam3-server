"""Worker drain: finish current inbox job, then pause claiming until cancel."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.job_recovery import utc_now
from pipeline.worker import wait_for_gate
from pipeline.worker_drain import (
    EXIT_NOT_REQUESTED,
    EXIT_OK,
    EXIT_TIMEOUT,
    cancel_drain,
    drain_path,
    is_drain_requested,
    main,
    request_drain,
    status_payload,
    wait_until_idle,
)


def _cfg(tmp_path: Path, *, drain_key: bool = True) -> dict:
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    frames = tmp_path / "frames"
    frames.mkdir()
    paths = {
        "jobs_dir": str(jobs),
        "frames_scratch": str(frames),
        "genomes_inbox": str(inbox),
        "status_file": str(tmp_path / "idle_gate_status.json"),
    }
    if drain_key:
        paths["worker_drain_file"] = str(tmp_path / "worker_drain.json")
    return {"_repo_root": str(tmp_path), "paths": paths, "idle_gate": {"enabled": True}}


def _write_job(cfg: dict, job_id: str, state: str) -> None:
    job_dir = Path(cfg["paths"]["jobs_dir"]) / job_id
    job_dir.mkdir()
    (job_dir / "job.json").write_text(
        json.dumps({"id": job_id, "state": state, "src": "/inbox/a.flam3", "updated_at": utc_now()}),
        encoding="utf-8",
    )


def test_missing_file_is_off(tmp_path: Path):
    cfg = _cfg(tmp_path)
    assert is_drain_requested(cfg) is False
    snap = status_payload(cfg)
    assert snap["phase"] == "off"
    assert snap["drain"] is False
    assert snap["in_flight"] == []


def test_default_path_beside_idle_gate_status(tmp_path: Path):
    cfg = _cfg(tmp_path, drain_key=False)
    assert drain_path(cfg) == tmp_path / "worker_drain.json"


def test_request_then_cancel_persists_flag(tmp_path: Path):
    cfg = _cfg(tmp_path)
    (Path(cfg["paths"]["genomes_inbox"]) / "a.flam3").write_text("<flame/>", encoding="utf-8")
    first = request_drain(cfg)
    assert first["drain"] is True
    assert first["phase"] == "idle"
    assert first["inbox_pending"] == 1
    assert is_drain_requested(cfg) is True
    again = request_drain(cfg)
    assert again["requested_at"] == first["requested_at"]
    cleared = cancel_drain(cfg)
    assert cleared["drain"] is False
    assert cleared["phase"] == "off"
    assert is_drain_requested(cfg) is False
    assert cleared["cleared_at"]


def test_in_flight_job_is_draining_until_terminal(tmp_path: Path):
    cfg = _cfg(tmp_path)
    _write_job(cfg, "abcabcabcabc", "rendering")
    request_drain(cfg)
    snap = status_payload(cfg)
    assert snap["phase"] == "draining"
    assert snap["in_flight"][0]["id"] == "abcabcabcabc"
    job = Path(cfg["paths"]["jobs_dir"]) / "abcabcabcabc" / "job.json"
    data = json.loads(job.read_text(encoding="utf-8"))
    data["state"] = "ingested"
    job.write_text(json.dumps(data), encoding="utf-8")
    assert status_payload(cfg)["phase"] == "idle"


def test_wait_until_idle_timeout_and_off(tmp_path: Path):
    cfg = _cfg(tmp_path)
    with pytest.raises(ValueError, match="not requested"):
        wait_until_idle(cfg, timeout_sec=0)
    request_drain(cfg)
    _write_job(cfg, "abcabcabcabc", "encoding")
    with pytest.raises(TimeoutError):
        wait_until_idle(cfg, timeout_sec=0, poll_sec=0)
    job = Path(cfg["paths"]["jobs_dir"]) / "abcabcabcabc" / "job.json"
    data = json.loads(job.read_text(encoding="utf-8"))
    data["state"] = "ingested"
    job.write_text(json.dumps(data), encoding="utf-8")
    snap = wait_until_idle(cfg, timeout_sec=0, poll_sec=0)
    assert snap["phase"] == "idle"


def test_wait_for_gate_aborts_on_drain(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path)
    request_drain(cfg)
    monkeypatch.setattr("pipeline.worker.is_gate_open", lambda _cfg: False)
    slept: list[float] = []
    monkeypatch.setattr("pipeline.worker.time.sleep", slept.append)
    wait_for_gate(cfg, abort_if_drain=True)
    assert slept == []

    def sleep_then_open(sec: float) -> None:
        slept.append(sec)
        monkeypatch.setattr("pipeline.worker.is_gate_open", lambda _cfg: True)

    monkeypatch.setattr("pipeline.worker.time.sleep", sleep_then_open)
    wait_for_gate(cfg, abort_if_drain=False)
    assert slept == [15]


def test_cli_status_wait_cancel(tmp_path: Path, capsys):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    cfg_path = tmp_path / "jellyflam3.yaml"
    cfg_path.write_text(
        "paths:\n"
        f"  jobs_dir: {jobs.as_posix()}\n"
        f"  genomes_inbox: {inbox.as_posix()}\n"
        f"  frames_scratch: {(tmp_path / 'frames').as_posix()}\n"
        f"  worker_drain_file: {(tmp_path / 'drain.json').as_posix()}\n"
        f"  status_file: {(tmp_path / 'idle.json').as_posix()}\n",
        encoding="utf-8",
    )
    assert main(["--config", str(cfg_path), "status"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["phase"] == "off"
    assert main(["--config", str(cfg_path), "wait", "--timeout-sec", "0"]) == EXIT_NOT_REQUESTED
    capsys.readouterr()
    assert main(["--config", str(cfg_path), "request"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["drain"] is True
    assert main(["--config", str(cfg_path), "status"]) == EXIT_OK
    st = json.loads(capsys.readouterr().out)
    assert st["phase"] == "idle"
    assert main(["--config", str(cfg_path), "cancel"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["drain"] is False


def test_cli_wait_timeout_while_in_flight(tmp_path: Path, capsys):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    cfg_path = tmp_path / "jellyflam3.yaml"
    cfg_path.write_text(
        "paths:\n"
        f"  jobs_dir: {jobs.as_posix()}\n"
        f"  genomes_inbox: {inbox.as_posix()}\n"
        f"  frames_scratch: {(tmp_path / 'frames').as_posix()}\n"
        f"  worker_drain_file: {(tmp_path / 'drain.json').as_posix()}\n",
        encoding="utf-8",
    )
    job_dir = jobs / "abcabcabcabc"
    job_dir.mkdir()
    (job_dir / "job.json").write_text(
        json.dumps({"state": "gating", "src": "x.flam3"}), encoding="utf-8"
    )
    assert main(["--config", str(cfg_path), "request"]) == EXIT_OK
    capsys.readouterr()
    assert main(["--config", str(cfg_path), "wait", "--timeout-sec", "0"]) == EXIT_TIMEOUT
    st = json.loads(capsys.readouterr().out)
    assert st["phase"] == "draining"
