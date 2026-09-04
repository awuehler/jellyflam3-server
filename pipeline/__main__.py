"""Purpose: Package entry when invoked as ``python -m pipeline``.

Requirements: N/A (prints usage and exits).
Usage: Prefer ``python -m pipeline.worker`` (and other module entrypoints); bare ``-m pipeline`` is not a runner.
Assumptions: Exit code 2; lists common submodule CLIs on stderr.
"""

import sys

if __name__ == "__main__":
    print(
        "Use: python -m pipeline.worker | python -m pipeline.idle_gate | "
        "python -m pipeline.seed_inbox | python -m pipeline.job_recovery | "
        "python -m pipeline.backfill_posters | python -m pipeline.shears | "
        "python -m pipeline.hammer | python -m pipeline.breed_idle | "
        "python -m pipeline.refactor | python -m pipeline.link_capacity",
        file=sys.stderr,
    )
    sys.exit(2)
