"""Purpose: Shared sheep integrity — Ed25519 preferred, SHA-256 fallback (Phase 3 guide 05).

Requirements: ``cryptography`` for Ed25519; configs ``peering.share_security.*``.

Usage: write/verify sidecars beside ``*.flam3``; ``gen_keypair`` for device keys.

Assumptions: Fail closed on inbound missing/bad integrity when enabled. Hash is of
on-disk ``.flam3`` bytes after sheep tax (outbound).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("jellyflam3.share_security")

SIG_SUFFIX = ".jellyflam3.sig"
SHA256_SUFFIX = ".sha256"
ALG_ED25519 = "ed25519"
ALG_SHA256 = "sha256"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def share_security_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    peering = dict(cfg.get("peering") or {})
    return dict(peering.get("share_security") or {})


def security_enabled(cfg: dict[str, Any]) -> bool:
    return bool(share_security_cfg(cfg).get("enabled", True))


def allow_sha256_fallback(cfg: dict[str, Any]) -> bool:
    return bool(share_security_cfg(cfg).get("allow_sha256_fallback", True))


def _resolve_under_repo(cfg: dict[str, Any], raw: str | Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = Path(cfg["_repo_root"]) / path
    return path


def private_key_path(cfg: dict[str, Any]) -> Path:
    sc = share_security_cfg(cfg)
    raw = sc.get("private_key_file") or "var/share_security/ed25519.pem"
    return _resolve_under_repo(cfg, raw)


def public_key_path(cfg: dict[str, Any]) -> Path:
    sc = share_security_cfg(cfg)
    raw = sc.get("public_key_file") or "var/share_security/ed25519.pub"
    return _resolve_under_repo(cfg, raw)


def trusted_keys_dir(cfg: dict[str, Any]) -> Path:
    sc = share_security_cfg(cfg)
    raw = sc.get("trusted_keys_dir") or "var/share_security/trusted"
    return _resolve_under_repo(cfg, raw)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_hex(path.read_bytes())


def sig_path_for(flam3: Path) -> Path:
    return flam3.with_name(flam3.name + SIG_SUFFIX)


def sha256_sidecar_path_for(flam3: Path) -> Path:
    return flam3.with_name(flam3.name + SHA256_SUFFIX)


def _sign_message(sha_hex: str, name: str) -> bytes:
    """Canonical bytes signed by Ed25519 (UTF-8)."""
    return f"jellyflam3-share-v1\n{name}\n{sha_hex}\n".encode("utf-8")


def key_id_from_raw_public(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()[:16]


def _public_key_bytes_from_private(priv_path: Path) -> bytes | None:
    """Derive raw Ed25519 public key bytes from a PEM private key file."""
    if not priv_path.is_file():
        return None
    try:
        from cryptography.hazmat.primitives import serialization

        key = _load_private_key(priv_path)
        return key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    except Exception:  # noqa: BLE001
        return None


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)
    try:
        dir_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _resolve_public_key_bytes(pub_file: Path) -> bytes | None:
    """Load raw Ed25519 public key bytes; prefer sibling private key when present."""
    pub_file = Path(pub_file)
    for priv_guess in (pub_file.with_name("ed25519.pem"), pub_file.parent / "ed25519.pem"):
        if priv_guess.is_file():
            normalized = _public_key_bytes_from_private(priv_guess)
            if normalized is not None:
                return normalized
    if pub_file.is_file():
        return _normalize_public_key_bytes(pub_file.read_bytes())
    return None


def _ensure_public_key_file(priv_path: Path, pub_path: Path) -> bytes | None:
    """Ensure ``pub_path`` holds raw 32-byte Ed25519 public key; heal from private if needed."""
    pub_path.parent.mkdir(parents=True, exist_ok=True)
    if pub_path.is_file():
        raw = pub_path.read_bytes()
        normalized = _normalize_public_key_bytes(raw)
        if normalized is not None:
            if raw != normalized:
                _write_bytes_atomic(pub_path, normalized)
            return normalized
    pub_raw = _public_key_bytes_from_private(priv_path)
    if pub_raw is not None:
        _write_bytes_atomic(pub_path, pub_raw)
    return pub_raw


def gen_keypair(cfg: dict[str, Any], *, overwrite: bool = False) -> dict[str, Any]:
    """Generate Ed25519 PEM private + raw public key files."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv_path = private_key_path(cfg)
    pub_path = public_key_path(cfg)
    if priv_path.is_file() and not overwrite:
        pub_raw = _ensure_public_key_file(priv_path, pub_path)
        return {
            "ok": True,
            "created": False,
            "private_key_file": str(priv_path),
            "public_key_file": str(pub_path),
            "key_id": key_id_from_raw_public(pub_raw) if pub_raw is not None else None,
            "note": "existing key kept (pass overwrite=True to replace)",
        }

    key = Ed25519PrivateKey.generate()
    priv_path.parent.mkdir(parents=True, exist_ok=True)
    pub_path.parent.mkdir(parents=True, exist_ok=True)
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    priv_path.write_bytes(priv_pem)
    try:
        priv_path.chmod(0o600)
    except OSError:
        pass
    _write_bytes_atomic(pub_path, pub_raw)
    kid = key_id_from_raw_public(pub_raw)
    log.info("share_security: generated Ed25519 key_id=%s", kid)
    return {
        "ok": True,
        "created": True,
        "private_key_file": str(priv_path),
        "public_key_file": str(pub_path),
        "key_id": kid,
    }


def _load_private_key(path: Path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    data = path.read_bytes()
    key = serialization.load_pem_private_key(data, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(f"not an Ed25519 private key: {path}")
    return key


def _load_public_key_raw(raw: bytes):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if len(raw) != 32:
        raise ValueError(f"Ed25519 public key must be 32 bytes, got {len(raw)}")
    return Ed25519PublicKey.from_public_bytes(raw)


def _normalize_public_key_bytes(raw: bytes) -> bytes | None:
    """Accept raw 32-byte Ed25519 or PEM. Never strip exact-length raw keys.

    Random public keys can start/end with whitespace bytes (``0x09``/``0x0a``/
    ``0x0d``/``0x20``, …). Stripping those mutates the key and breaks trust
    enrollment intermittently (~5% of key pairs).
    """
    if not raw:
        return None
    # Exact raw Ed25519 — whitespace bytes are valid key material.
    if len(raw) == 32:
        return raw
    stripped = raw.strip()
    if stripped.startswith(b"-----BEGIN"):
        try:
            from cryptography.hazmat.primitives import serialization

            pub = serialization.load_pem_public_key(stripped)
            return pub.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        except Exception:  # noqa: BLE001
            return None
    # Allow a single trailing newline after raw 32 bytes (text-editor saves).
    return stripped if len(stripped) == 32 else None


def _load_trusted_keys(cfg: dict[str, Any]) -> dict[str, bytes]:
    """Map key_id → raw public key bytes."""
    root = trusted_keys_dir(cfg)
    out: dict[str, bytes] = {}
    if root.is_dir():
        for path in sorted(root.iterdir()):
            if not path.is_file():
                continue
            if path.suffix not in {".pub", ".pem", ".key"} and not path.name.endswith(".pub"):
                continue
            normalized = _normalize_public_key_bytes(path.read_bytes())
            if normalized is not None:
                out[key_id_from_raw_public(normalized)] = normalized
    # Always trust our own key pair (derive public from private if .pub is missing).
    priv = private_key_path(cfg)
    own = public_key_path(cfg)
    raw_pub: bytes | None = None
    if own.is_file():
        raw_pub = _normalize_public_key_bytes(own.read_bytes())
    if raw_pub is None:
        raw_pub = _public_key_bytes_from_private(priv)
    if raw_pub is not None:
        out[key_id_from_raw_public(raw_pub)] = raw_pub
    return out


def trust_public_key(cfg: dict[str, Any], pub_file: Path, *, name: str | None = None) -> dict[str, Any]:
    """Copy a peer public key into the trusted keys directory."""
    normalized = _resolve_public_key_bytes(pub_file)
    if normalized is None:
        return {"ok": False, "error": "expected 32-byte Ed25519 public key (raw or PEM)"}
    kid = key_id_from_raw_public(normalized)
    dest_dir = trusted_keys_dir(cfg)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{name or kid}.pub"
    _write_bytes_atomic(dest, normalized)
    trusted = _load_trusted_keys(cfg)
    if kid not in trusted:
        stored = _normalize_public_key_bytes(dest.read_bytes())
        if stored is None or key_id_from_raw_public(stored) != kid:
            return {"ok": False, "error": "trusted key write failed verification"}
        trusted = _load_trusted_keys(cfg)
        if kid not in trusted:
            return {"ok": False, "error": f"trusted key {kid} not visible in trust store"}
    return {"ok": True, "key_id": kid, "path": str(dest)}


def write_sha256_sidecar(flam3: Path) -> Path:
    digest = file_sha256(flam3)
    dest = sha256_sidecar_path_for(flam3)
    dest.write_text(f"{digest}  {flam3.name}\n", encoding="utf-8")
    return dest


def write_ed25519_sidecar(flam3: Path, cfg: dict[str, Any]) -> Path:
    from cryptography.hazmat.primitives import serialization

    priv = private_key_path(cfg)
    key = _load_private_key(priv)
    digest = file_sha256(flam3)
    msg = _sign_message(digest, flam3.name)
    sig = key.sign(msg)
    pub_raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    body = {
        "version": 1,
        "alg": ALG_ED25519,
        "name": flam3.name,
        "sha256": digest,
        "key_id": key_id_from_raw_public(pub_raw),
        "public_key_b64": base64.b64encode(pub_raw).decode("ascii"),
        "signature_b64": base64.b64encode(sig).decode("ascii"),
        "created_at": _utc_now(),
    }
    dest = sig_path_for(flam3)
    dest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return dest


def write_integrity(
    flam3: Path,
    cfg: dict[str, Any],
    *,
    prefer_ed25519: bool | None = None,
) -> dict[str, Any]:
    """Write integrity sidecar beside ``flam3``. Prefers Ed25519 when key exists."""
    flam3 = Path(flam3)
    sc = share_security_cfg(cfg)
    if prefer_ed25519 is None:
        prefer_ed25519 = bool(sc.get("prefer_ed25519", True))

    result: dict[str, Any] = {
        "direction": "outbound",
        "file": str(flam3),
        "sha256": file_sha256(flam3),
    }

    priv = private_key_path(cfg)
    if prefer_ed25519 and priv.is_file():
        try:
            dest = write_ed25519_sidecar(flam3, cfg)
            # Also write sha256 companion for peers that only verify hashes
            if allow_sha256_fallback(cfg):
                write_sha256_sidecar(flam3)
            result.update(
                {
                    "ok": True,
                    "result": "signed",
                    "alg": ALG_ED25519,
                    "sidecar": str(dest),
                    "reason": "ed25519",
                }
            )
            log.info(
                "share_security: %s",
                json.dumps({k: result[k] for k in ("direction", "result", "reason", "file")}),
            )
            return result
        except Exception as exc:  # noqa: BLE001 — fall back to sha256
            log.warning("Ed25519 sign failed (%s); falling back to SHA-256", exc)

    if not allow_sha256_fallback(cfg):
        result.update(
            {
                "ok": False,
                "result": "refuse",
                "alg": None,
                "reason": "no_signing_key_and_sha256_fallback_disabled",
            }
        )
        log.warning("share_security: %s", json.dumps(result))
        return result

    dest = write_sha256_sidecar(flam3)
    # Remove stale sig if we could not sign
    stale = sig_path_for(flam3)
    if stale.is_file() and not (prefer_ed25519 and priv.is_file()):
        pass
    result.update(
        {
            "ok": True,
            "result": "hashed",
            "alg": ALG_SHA256,
            "sidecar": str(dest),
            "reason": "sha256_fallback",
        }
    )
    log.info(
        "share_security: %s",
        json.dumps({k: result[k] for k in ("direction", "result", "reason", "file")}),
    )
    return result


def _verify_sha256_sidecar(flam3: Path) -> dict[str, Any]:
    side = sha256_sidecar_path_for(flam3)
    if not side.is_file():
        return {"ok": False, "reason": "missing_sha256_sidecar"}
    line = side.read_text(encoding="utf-8").strip().splitlines()[0]
    parts = line.split()
    if not parts:
        return {"ok": False, "reason": "empty_sha256_sidecar"}
    expected = parts[0].lower()
    actual = file_sha256(flam3)
    if expected != actual:
        return {
            "ok": False,
            "reason": "sha256_mismatch",
            "expected": expected,
            "actual": actual,
        }
    return {"ok": True, "reason": "sha256_ok", "alg": ALG_SHA256, "sha256": actual}


def _verify_ed25519_sidecar(flam3: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    side = sig_path_for(flam3)
    if not side.is_file():
        return {"ok": False, "reason": "missing_sig_sidecar"}
    try:
        body = json.loads(side.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "reason": f"bad_sig_json:{exc}"}

    if body.get("alg") != ALG_ED25519:
        return {"ok": False, "reason": f"unsupported_alg:{body.get('alg')}"}

    actual = file_sha256(flam3)
    expected = str(body.get("sha256") or "").lower()
    if expected != actual:
        return {
            "ok": False,
            "reason": "sha256_mismatch",
            "expected": expected,
            "actual": actual,
        }

    name = str(body.get("name") or flam3.name)
    sig_b64 = body.get("signature_b64")
    if not sig_b64:
        return {"ok": False, "reason": "missing_signature"}
    try:
        sig = base64.b64decode(sig_b64)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"bad_signature_b64:{exc}"}

    kid = str(body.get("key_id") or "")
    trusted = _load_trusted_keys(cfg)
    raw_pub = trusted.get(kid)
    if raw_pub is None and body.get("public_key_b64"):
        try:
            embedded = base64.b64decode(body["public_key_b64"])
            emb_kid = key_id_from_raw_public(embedded)
            raw_pub = trusted.get(emb_kid)
            if raw_pub is not None:
                kid = emb_kid
        except Exception:  # noqa: BLE001
            pass

    if raw_pub is None:
        return {
            "ok": False,
            "reason": "untrusted_key",
            "key_id": kid,
            "hint": "copy peer .pub into trusted_keys_dir (peering trust-key)",
        }

    try:
        pub = _load_public_key_raw(raw_pub)
        pub.verify(sig, _sign_message(actual, name))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"signature_invalid:{exc}"}

    return {
        "ok": True,
        "reason": "ed25519_ok",
        "alg": ALG_ED25519,
        "sha256": actual,
        "key_id": kid,
    }


def verify_integrity(flam3: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """Verify inbound ``.flam3`` integrity. Fail closed when security enabled."""
    flam3 = Path(flam3)
    base: dict[str, Any] = {
        "direction": "inbound",
        "file": str(flam3),
    }
    if not security_enabled(cfg):
        out = {**base, "ok": True, "result": "skipped", "reason": "share_security_disabled"}
        log.info("share_security: %s", json.dumps({k: out[k] for k in ("direction", "result", "reason")}))
        return out

    sig = sig_path_for(flam3)
    if sig.is_file():
        checked = _verify_ed25519_sidecar(flam3, cfg)
        if checked.get("ok"):
            out = {**base, **checked, "result": "verified"}
            log.info(
                "share_security: %s",
                json.dumps({k: out[k] for k in ("direction", "result", "reason", "file")}),
            )
            return out
        # Signed but invalid / untrusted — do not fall back to bare sha256 (fail closed)
        out = {
            **base,
            **checked,
            "result": "reject",
            "ok": False,
        }
        log.warning(
            "share_security: %s",
            json.dumps({k: out.get(k) for k in ("direction", "result", "reason", "file")}),
        )
        return out

    if allow_sha256_fallback(cfg):
        checked = _verify_sha256_sidecar(flam3)
        if checked.get("ok"):
            out = {**base, **checked, "result": "verified"}
            log.info(
                "share_security: %s",
                json.dumps({k: out[k] for k in ("direction", "result", "reason", "file")}),
            )
            return out
        out = {**base, **checked, "result": "reject", "ok": False}
        log.warning(
            "share_security: %s",
            json.dumps({k: out.get(k) for k in ("direction", "result", "reason", "file")}),
        )
        return out

    out = {
        **base,
        "ok": False,
        "result": "reject",
        "reason": "missing_sig_sidecar",
    }
    log.warning("share_security: %s", json.dumps(out))
    return out


def companion_integrity_paths(flam3: Path) -> list[Path]:
    """Sidecar paths that may travel with a genome."""
    return [sig_path_for(flam3), sha256_sidecar_path_for(flam3)]
