#!/usr/bin/env python3
"""Prepare or inspect one immutable fixed-model season run; release separately."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.season.runner import prepare, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preparation = commands.add_parser(
        "prepare", help="reconstruct completed weeks and prepare the next slate"
    )
    preparation.add_argument("--model-manifest", type=Path, required=True)
    preparation.add_argument("--revision-manifest", type=Path, required=True)
    preparation.add_argument("--through-week", type=int, required=True)
    preparation.add_argument("--next-week", type=int)
    preparation.add_argument(
        "--reconstruct-next-week",
        action="store_true",
        help="reconstruct the full next slate at its pinned pre-week cutoff",
    )
    preparation.add_argument("--as-of", required=True)
    preparation.add_argument("--output", type=Path, required=True)
    preparation.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    inspection = commands.add_parser(
        "status", help="inspect and recheck retained output checksums"
    )
    inspection.add_argument("--output", type=Path, required=True)
    for verb in ("release", "rollback"):
        command = commands.add_parser(verb)
        command.add_argument(
            "--environment", choices=("preview", "production"), required=True
        )
        command.add_argument("--expected-previous-release-id")
        command.add_argument("--initial", action="store_true")
        if verb == "release":
            command.add_argument("--run-manifest", type=Path, required=True)
            command.add_argument("--projection-payload", type=Path, required=True)
            command.add_argument("--projection-payload-sha256", required=True)
        else:
            command.add_argument("--season", type=int, default=2026)
            command.add_argument("--release-id", required=True)
            command.add_argument("--decision-ref", required=True)
            command.add_argument("--owner-authorized", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "status":
        print(json.dumps(status(args.output), sort_keys=True))
        return 0
    if args.command == "prepare":
        if os.getenv("CFB_STORAGE_BACKEND") != "r2":
            raise ValueError("operational preparation requires explicit R2 backend")
        if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
            raise ValueError("operational preparation requires clean committed code")
        code_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
        manifest = prepare(
            model_raw=args.model_manifest.read_bytes(),
            revision_raw=args.revision_manifest.read_bytes(),
            reader=get_storage(environment=args.environment),
            through_week=args.through_week,
            next_week=args.next_week,
            as_of=args.as_of,
            output=args.output,
            code_sha=code_sha,
            reconstruct_next_week=args.reconstruct_next_week,
        )
        print(json.dumps(manifest, sort_keys=True))
        return 0
    return _release(args)


def _release(args: argparse.Namespace) -> int:
    import psycopg

    from cks_picks_cfb.season.manifest import canonical, sha
    from cks_picks_cfb.season.release import (
        activate_release,
        rollback_release,
        stage_release,
    )

    if bool(args.initial) == bool(args.expected_previous_release_id):
        raise ValueError("choose --initial or --expected-previous-release-id")
    if (
        os.getenv("CFB_STORAGE_BACKEND") != "r2"
        or os.getenv("CFB_ARTIFACT_ENV") != args.environment
    ):
        raise ValueError("release requires matching explicit R2 environment")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise ValueError("release requires clean committed code")
    executing_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    key = "PREVIEW_DATABASE_URL" if args.environment == "preview" else "DATABASE_URL"
    url = os.getenv(key)
    if not url:
        raise ValueError(f"{key} is required")
    with psycopg.connect(url) as conn:
        if args.command == "rollback":
            result = rollback_release(
                conn,
                environment=args.environment,
                season=args.season,
                release_id=args.release_id,
                expected_previous_release_id=args.expected_previous_release_id,
                owner_authorized=args.owner_authorized,
                decision_ref=args.decision_ref,
            )
        else:
            raw = args.run_manifest.read_bytes()
            manifest = json.loads(raw)
            if manifest["code_sha"] != executing_sha or manifest["config_sha"] != sha(
                canonical({})
            ):
                raise ValueError(
                    "executing code/config differs from prepared candidate"
                )
            projection = args.projection_payload.read_bytes()
            if sha(projection) != args.projection_payload_sha256:
                raise ValueError("projection payload checksum differs")
            release_id = stage_release(
                conn,
                manifest_raw=raw,
                run_manifest_uri=str(args.run_manifest.resolve()),
                verification_raw=Path(manifest["verification_uri"]).read_bytes(),
                projection_raw=projection,
                environment=args.environment,
            )
            if args.environment == "production":
                preview_url = os.getenv("PREVIEW_DATABASE_URL")
                if not preview_url:
                    raise ValueError(
                        "Production requires separate Preview rehearsal connection"
                    )
                with psycopg.connect(
                    preview_url, options="-c default_transaction_read_only=on"
                ) as preview:
                    preview.read_only = True
                    result = activate_release(
                        conn,
                        environment=args.environment,
                        season=manifest["season"],
                        release_id=release_id,
                        expected_previous_release_id=args.expected_previous_release_id,
                        preview_conn=preview,
                    )
            else:
                result = activate_release(
                    conn,
                    environment=args.environment,
                    season=manifest["season"],
                    release_id=release_id,
                    expected_previous_release_id=args.expected_previous_release_id,
                )
        conn.commit()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
