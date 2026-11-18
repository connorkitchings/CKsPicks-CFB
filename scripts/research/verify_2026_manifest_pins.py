"""Read-only check that every 2026 revision manifest's pins are still recoverable.

Each manifest pins a raw SHA-256 of ``score_reconciliation_exceptions.json``, a
repository file that was later edited in place. This script finds the git version
whose bytes match the pin, restores it into a temporary root, points
``season.inputs.REPOSITORY`` at that root and runs the same validation and input
loading ``prepare`` uses. It reads R2 (Preview credentials) and writes nothing
outside a temporary directory and the measurement cache.

Run (from the repository root)::

    CFB_STORAGE_BACKEND=r2 PYTHONPATH=.:src bash scripts/ops/with_preview_env.sh \\
        uv run python scripts/research/verify_2026_manifest_pins.py --cache-dir <dir>

Stop gate: a failure that is not the exceptions pin stops the run and exits 1.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.season import inputs
from cks_picks_cfb.season.manifest import sha, validate_model, validate_revision

SEASON_DIR = Path("conf/season/2026")
EXCEPTIONS = SEASON_DIR / "score_reconciliation_exceptions.json"


def _git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=inputs.REPOSITORY)


def exceptions_versions() -> dict[str, tuple[str, bytes]]:
    """``{sha256: (commit, bytes)}`` for every git version of the exceptions file."""
    versions: dict[str, tuple[str, bytes]] = {}
    for commit in _git("log", "--format=%h", "--", str(EXCEPTIONS)).decode().split():
        raw = _git("show", f"{commit}:{EXCEPTIONS}")
        versions.setdefault(sha(raw), (commit, raw))
    return versions


def through_week(revision: dict) -> int:
    """The last completed week: the newest week with a post-week cutoff."""
    return max(int(week) for week in revision["post_week_cutoffs"])


def verify(
    path: Path, model: dict, reader, versions: dict, cache_dir: Path
) -> tuple[str, str, str]:
    """``(pinned exceptions sha, matching commit, outcome)`` for one manifest."""
    revision = json.loads(path.read_bytes())
    pinned = revision["score_reconciliation_exceptions"]["sha256"]
    commit, raw = versions.get(pinned, ("none", b""))
    if commit == "none":
        return pinned, commit, "FAIL exceptions pin: no git version matches"
    with tempfile.TemporaryDirectory() as root:
        target = Path(root) / EXCEPTIONS
        target.parent.mkdir(parents=True)
        target.write_bytes(raw)
        original, inputs.REPOSITORY = inputs.REPOSITORY, Path(root)
        try:
            validate_model(model)
            validate_revision(revision)
            inputs.load_inputs(
                reader,
                model,
                revision,
                through_week(revision),
                cache_dir=cache_dir,
            )
        except Exception as error:  # report any pin failure with its reason
            return pinned, commit, f"FAIL {type(error).__name__}: {error}"
        finally:
            inputs.REPOSITORY = original
    return pinned, commit, f"PASS through week {through_week(revision)}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    load_dotenv()  # R2 credentials live in the repository-root .env
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("requires CFB_STORAGE_BACKEND=r2")
    missing = [
        name
        for name in ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY")
        if not os.getenv(f"CFB_R2_PREVIEW_{name}")
    ]
    if missing:
        raise SystemExit(f"missing CFB_R2_PREVIEW_ variables: {missing}")
    from cks_picks_cfb.data.storage import get_storage

    reader = get_storage(environment="preview")
    model = json.loads(
        (inputs.REPOSITORY / SEASON_DIR / "model_manifest_v1.json").read_bytes()
    )
    versions = exceptions_versions()
    paths = sorted(
        (inputs.REPOSITORY / SEASON_DIR).glob("revision_manifest_w*_v*.json"),
        key=lambda p: tuple(
            int(x) for x in p.stem.removeprefix("revision_manifest_w").split("_v")
        ),
    )
    failed = False
    print("manifest | pinned exceptions sha256 | git commit | result")
    for path in paths:
        pinned, commit, outcome = verify(path, model, reader, versions, args.cache_dir)
        print(
            f"{path.stem.removeprefix('revision_manifest_')} | {pinned} | {commit} | {outcome}",
            flush=True,
        )
        if outcome.startswith("FAIL"):
            failed = True
            if "exceptions pin" not in outcome:
                print(
                    "STOP: a pin other than the exceptions file failed", file=sys.stderr
                )
                break
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
