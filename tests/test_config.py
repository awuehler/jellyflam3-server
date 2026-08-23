"""Unit tests for pipeline.config (YAML load, ${ENV} expand, path resolve)."""

from __future__ import annotations

import os
from pathlib import Path

from pipeline.config import _expand, load_config, load_dotenv, resolve_path


def test_load_dotenv_setdefault_and_skips(tmp_path: Path, monkeypatch):
    env = tmp_path / "secrets.env"
    env.write_text(
        "# comment\nFOO=fromfile\nBAR=quoted\nEMPTY=\nNOEQUALS\nBAZ='wrapped'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    monkeypatch.delenv("EMPTY", raising=False)
    monkeypatch.setenv("BAR", "already")
    load_dotenv(env)
    assert os.environ["FOO"] == "fromfile"
    assert os.environ["BAR"] == "already"
    assert os.environ["BAZ"] == "wrapped"


def test_expand_nested_env(monkeypatch):
    monkeypatch.setenv("JF_HOST", "pi.local")
    monkeypatch.setenv("JF_TOKEN", "sekrit")
    out = _expand(
        {
            "url": "http://${JF_HOST}/x",
            "nested": {"t": "${JF_TOKEN}"},
            "list": ["${JF_HOST}", 3],
            "n": 7,
        }
    )
    assert out["url"] == "http://pi.local/x"
    assert out["nested"]["t"] == "sekrit"
    assert out["list"] == ["pi.local", 3]
    assert out["n"] == 7


def test_expand_tracks_missing_env(monkeypatch):
    monkeypatch.delenv("MISSING_HOST", raising=False)
    missing: list[str] = []
    out = _expand("http://${MISSING_HOST}/x", missing=missing)
    assert out == "http:///x"
    assert missing == ["MISSING_HOST"]


def test_load_config_rejects_missing_secret_env(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("JF_API_KEY", raising=False)
    monkeypatch.delenv("JELLYFLAM3_ALLOW_EMPTY_SECRETS", raising=False)
    cfg_path = tmp_path / "configs" / "jellyflam3.yaml"
    cfg_path.parent.mkdir()
    cfg_path.write_text(
        "jellyfin:\n  api_key: ${JF_API_KEY}\npaths:\n  genomes_inbox: genomes/inbox\n",
        encoding="utf-8",
    )
    try:
        load_config(cfg_path, repo_root=tmp_path)
        raised = False
    except ValueError as exc:
        raised = True
        assert "JF_API_KEY" in str(exc)
    assert raised


def test_load_config_allows_missing_secret_when_strict_off(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("JF_API_KEY", raising=False)
    monkeypatch.delenv("JELLYFLAM3_ALLOW_EMPTY_SECRETS", raising=False)
    cfg_path = tmp_path / "configs" / "jellyflam3.yaml"
    cfg_path.parent.mkdir()
    cfg_path.write_text(
        "jellyfin:\n  api_key: ${JF_API_KEY}\npaths:\n  genomes_inbox: genomes/inbox\n",
        encoding="utf-8",
    )
    cfg = load_config(cfg_path, repo_root=tmp_path, strict_secrets=False)
    assert cfg["jellyfin"]["api_key"] == ""


def test_load_config_and_resolve_path(tmp_path: Path, monkeypatch):
    abs_lib = tmp_path / "library"
    monkeypatch.setenv("JF_LIB", str(abs_lib))
    (tmp_path / "secrets.env").write_text("UNUSED=1\n", encoding="utf-8")
    cfg_path = tmp_path / "configs" / "jellyflam3.yaml"
    cfg_path.parent.mkdir()
    cfg_path.write_text(
        "paths:\n"
        "  genomes_inbox: genomes/inbox\n"
        "  media_library: ${JF_LIB}\n",
        encoding="utf-8",
    )
    cfg = load_config(cfg_path, repo_root=tmp_path)
    assert cfg["_repo_root"] == str(tmp_path)
    assert Path(cfg["_config_path"]) == cfg_path.resolve()
    inbox = resolve_path(cfg, "genomes_inbox")
    assert inbox == tmp_path / "genomes" / "inbox"
    media = resolve_path(cfg, "media_library")
    assert media == abs_lib
