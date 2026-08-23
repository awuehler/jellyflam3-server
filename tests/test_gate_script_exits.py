"""Gate / ops script exit contracts (smoke, healthcheck queue, bringup footer).

Mirrors scripts/bringup_check.sh footer:
  FAIL>0 → exit 1
  STRICT=1 and WARN>0 → exit 1
  otherwise → exit 0

Bash-backed cases skip when shutil.which("bash") is None.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="bash not available")

# Prefer Git Bash on Windows so repo paths resolve; WSL bash is often first on PATH.
_GIT_BASH_CANDIDATES = (
    Path(r"C:\Program Files\Git\bin\bash.exe"),
    Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
)


def _bash() -> str:
    for p in _GIT_BASH_CANDIDATES:
        if p.is_file():
            return str(p)
    assert BASH is not None
    return BASH


# Exact queue probe body from scripts/healthcheck.sh (JF_CFG / JF_ROOT).
_QUEUE_PROBE_PY = textwrap.dedent(
    """\
    from pathlib import Path
    import os
    import sys
    import yaml
    cfg_path = Path(os.environ["JF_CFG"])
    root = Path(os.environ["JF_ROOT"])
    if not cfg_path.is_file():
        print("FAIL config missing", cfg_path)
        sys.exit(1)
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    paths = cfg.get("paths") or {}
    if "genomes_inbox" not in paths:
        print("FAIL paths.genomes_inbox missing in", cfg_path)
        sys.exit(1)
    inbox = Path(paths["genomes_inbox"])
    if not inbox.is_absolute():
        inbox = root / inbox
    print("inbox", inbox, "count", len(list(inbox.glob("*.flam3"))))
    """
)


def _run_bash(args: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None):
    return subprocess.run(
        [_bash(), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or ROOT),
        env=env,
    )


def _path_without_flam3() -> str:
    """Like PATH=/usr/bin:/bin but keep python; drop dirs that contain flam3-genome.

    smoke_render.sh prepends /usr/local/bin by default; gate tests set
    JELLYFLAM3_SMOKE_PREPEND_LOCAL=0 so a stripped PATH fails before render.
    """
    kept: list[str] = ["/usr/bin", "/bin"]
    seen = set(kept)
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d or d in seen:
            continue
        p = Path(d)
        if (p / "flam3-genome").exists() or (p / "flam3-genome.exe").exists():
            continue
        kept.append(d)
        seen.add(d)
    # Ensure the interpreter running pytest is findable as python3 when needed.
    py_dir = str(Path(sys.executable).resolve().parent)
    if py_dir not in seen:
        kept.append(py_dir)
    return os.pathsep.join(kept)


def test_smoke_render_fails_without_flam3_on_path(tmp_path: Path):
    env = os.environ.copy()
    env["PATH"] = _path_without_flam3()
    # Windows often only ships `python`; smoke_render.sh calls `python3`.
    shim_dir = tmp_path / "py_shim"
    shim_dir.mkdir()
    shim = shim_dir / "python3"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{Path(sys.executable).as_posix()}" "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    os.chmod(shim, 0o755)
    env["PATH"] = f"{shim_dir.as_posix()}{os.pathsep}{env['PATH']}"
    env.pop("JELLYFLAM3_SMOKE_ROOT", None)
    env["JELLYFLAM3_SMOKE_PREPEND_LOCAL"] = "0"
    script = SCRIPTS / "smoke_render.sh"
    proc = _run_bash([str(script)], env=env)
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0
    assert re.search(r"flam3-genome|ERROR", combined, re.I), combined


def test_healthcheck_queue_probe_missing_key(tmp_path: Path):
    cfg = tmp_path / "no_inbox.yaml"
    cfg.write_text("paths: {}\n", encoding="utf-8")
    env = os.environ.copy()
    env["JF_CFG"] = str(cfg)
    env["JF_ROOT"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, "-c", _QUEUE_PROBE_PY],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    assert proc.returncode != 0
    assert "paths.genomes_inbox missing" in (proc.stdout + proc.stderr)


def test_healthcheck_queue_probe_missing_file(tmp_path: Path):
    missing = tmp_path / "does_not_exist.yaml"
    env = os.environ.copy()
    env["JF_CFG"] = str(missing)
    env["JF_ROOT"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, "-c", _QUEUE_PROBE_PY],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    assert proc.returncode != 0
    assert "config missing" in (proc.stdout + proc.stderr)


def test_bringup_check_contains_gate_exit_block():
    text = (SCRIPTS / "bringup_check.sh").read_text(encoding="utf-8")
    assert 'if [[ "$FAIL" -gt 0 ]]; then' in text
    assert "exit 1" in text
    assert 'if [[ "$STRICT" -eq 1 && "$WARN" -gt 0 ]]; then' in text
    # Footer contract comment
    assert "Gate mode" in text or "STRICT" in text


@pytest.mark.parametrize(
    "fail,warn,strict,expected",
    [
        (1, 0, 0, 1),
        (0, 1, 0, 0),
        (0, 1, 1, 1),
        (0, 0, 1, 0),
    ],
)
def test_bringup_exit_contract_matrix(fail: int, warn: int, strict: int, expected: int):
    """Small bash matrix mirroring bringup_check.sh footer gate."""
    snippet = textwrap.dedent(
        f"""\
        set -euo pipefail
        FAIL={fail}
        WARN={warn}
        STRICT={strict}
        if [[ "$FAIL" -gt 0 ]]; then
          exit 1
        fi
        if [[ "$STRICT" -eq 1 && "$WARN" -gt 0 ]]; then
          exit 1
        fi
        exit 0
        """
    )
    proc = _run_bash(["-c", snippet])
    assert proc.returncode == expected, (proc.stdout, proc.stderr)
