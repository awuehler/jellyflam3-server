"""Purpose: Load jellyflam3 YAML config with secrets.env and ${ENV} expansion.

Requirements: PyYAML; optional secrets.env at repo root; config path relative to repo.

Usage: ``cfg = load_config("configs/jellyflam3.yaml")`` then ``resolve_path(cfg, key)``.

Assumptions: Repo root is two parents above the config file unless ``repo_root`` is passed;
``_repo_root`` / ``_config_path`` are injected into the returned dict.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
# Names that must not silently expand to "" (override with JELLYFLAM3_ALLOW_EMPTY_SECRETS=1).
_SECRET_ENV_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "AUTHKEY")

log = logging.getLogger("jellyflam3.config")


def load_dotenv(path: Path) -> None:
    """Load KEY=VAL lines into os.environ (setdefault; skips comments/blank)."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def _is_secret_env_name(name: str) -> bool:
    upper = name.upper()
    return any(marker in upper for marker in _SECRET_ENV_MARKERS)


def _expand(value: Any, *, missing: list[str] | None = None) -> Any:
    """Recursively replace ``${VAR}`` in strings using the process environment.

    Unset variables expand to ``\"\"``. When ``missing`` is provided, each unset
    name is appended so callers can warn or fail closed.
    """
    if isinstance(value, str):

        def repl(m: re.Match[str]) -> str:
            key = m.group(1)
            if key not in os.environ:
                if missing is not None:
                    missing.append(key)
                return ""
            return os.environ[key]

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand(v, missing=missing) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v, missing=missing) for v in value]
    return value


def load_config(
    config_path: str | Path,
    repo_root: Path | None = None,
    *,
    strict_secrets: bool = True,
) -> dict[str, Any]:
    """Load YAML, expand env placeholders, attach ``_repo_root`` and ``_config_path``.

    Unset ``${ENV}`` placeholders log a warning. Unset *secret-like* names
    (TOKEN / SECRET / PASSWORD / API_KEY / AUTHKEY) raise ``ValueError`` unless
    ``strict_secrets`` is False or ``JELLYFLAM3_ALLOW_EMPTY_SECRETS=1``.
    """
    path = Path(config_path)
    root = repo_root or path.resolve().parent.parent
    load_dotenv(root / "secrets.env")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    missing: list[str] = []
    cfg = _expand(raw, missing=missing)
    if missing:
        uniq = sorted(set(missing))
        log.warning(
            "config ${ENV} unset (expanded to empty): %s",
            ", ".join(uniq),
        )
        secret_missing = [k for k in uniq if _is_secret_env_name(k)]
        allow = os.environ.get("JELLYFLAM3_ALLOW_EMPTY_SECRETS", "").strip() in (
            "1",
            "true",
            "yes",
        )
        if secret_missing and strict_secrets and not allow:
            raise ValueError(
                "missing secret env vars (set them in secrets.env or export "
                f"JELLYFLAM3_ALLOW_EMPTY_SECRETS=1): {', '.join(secret_missing)}"
            )
    cfg["_repo_root"] = str(root)
    cfg["_config_path"] = str(path.resolve())
    return cfg


def resolve_path(cfg: dict[str, Any], key: str) -> Path:
    """Resolve ``paths[key]`` relative to ``_repo_root`` when not absolute."""
    root = Path(cfg["_repo_root"])
    p = Path(cfg["paths"][key])
    if not p.is_absolute():
        p = root / p
    return p
