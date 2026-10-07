#!/usr/bin/env python3
"""Guarded, user-run Week 5 legacy attestation; dry-run is read-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.data.storage.r2 import ReadOnlyStorage
from cks_picks_cfb.ops.prospective_records import (
    ProspectiveRecordError,
    build_legacy_freeze_attestation,
    canonical_json,
    read_legacy_freeze_sources,
    register_legacy_freeze_attestation,
    verify_legacy_freeze_attestation,
    verify_prospective_record,
    write_immutable,
)
from cks_picks_cfb.ops.v5_release import assert_v5_database_environment


class Overlay:
    """Read-only remote sources plus prospective local snapshot bytes."""

    def __init__(self, storage, objects):
        self.storage, self.objects = storage, objects

    def read_bytes(self, uri):
        return (
            self.objects[uri] if uri in self.objects else self.storage.read_bytes(uri)
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--decision-ref", required=True)
    parser.add_argument("--historical-freeze-code-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    load_dotenv()
    if (
        os.getenv("CFB_STORAGE_BACKEND") != "r2"
        or os.getenv("CFB_ARTIFACT_ENV") != args.environment
    ):
        raise ProspectiveRecordError(
            "explicit R2 backend and matching artifact environment required"
        )
    prefix = "CFB_R2_PREVIEW" if args.environment == "preview" else "CFB_R2"
    if not all(
        os.getenv(prefix + "_" + key)
        for key in ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY")
    ):
        raise ProspectiveRecordError("environment R2 credentials missing")
    storage = get_storage(environment=args.environment)
    readonly = ReadOnlyStorage(storage)
    url = os.environ[
        "PREVIEW_DATABASE_URL" if args.environment == "preview" else "DATABASE_URL"
    ]
    with psycopg.connect(
        url,
        options="-c default_transaction_read_only=" + ("off" if args.apply else "on"),
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            assert_v5_database_environment(cur, args.environment)
            cur.execute("SELECT to_regclass('public.prospective_week_records')")
            if cur.fetchone()[0] is None:
                raise ProspectiveRecordError(
                    "prospective schema missing; separately authorized migration required"
                )
            cur.execute("SELECT pg_advisory_xact_lock(%s,%s)", (2026, 5))
            cur.execute(
                "SELECT season,week,run_id,freeze_receipt_uri,freeze_receipt_sha256,frozen_at,first_kickoff_utc,decision_ref FROM public.prospective_week_records WHERE season=2026 AND week=5"
            )
            prior = cur.fetchone()
            if prior:
                row = dict(
                    zip(
                        (
                            "season",
                            "week",
                            "run_id",
                            "freeze_receipt_uri",
                            "freeze_receipt_sha256",
                            "frozen_at",
                            "first_kickoff_utc",
                            "decision_ref",
                        ),
                        prior,
                        strict=True,
                    )
                )
                if (
                    row["run_id"] != args.run_id
                    or row["decision_ref"] != args.decision_ref
                    or "/legacy-attestation-v1-" not in row["freeze_receipt_uri"]
                ):
                    raise ProspectiveRecordError("existing designation conflicts")
                verify_prospective_record(
                    row, cur=cur, storage=readonly, environment=args.environment
                )
                payload = json.loads(readonly.read_bytes(row["freeze_receipt_uri"]))
                if (
                    payload["historical_freeze_code_sha"]
                    != args.historical_freeze_code_sha
                ):
                    raise ProspectiveRecordError("retry historical code differs")
                args.output.write_bytes(canonical_json(payload))
                print("Verified exact retry; zero remote writes")
                return
            for prefix in (
                "artifacts/prospective/v5/season=2026/week=5/",
                f"artifacts/{args.environment}/predictions/year=2026/week=5/run_id={args.run_id}/",
            ):
                if any(
                    "freeze-" in uri or "receipt" in uri
                    for uri in readonly.list_files(prefix)
                ):
                    raise ProspectiveRecordError(
                        "authentic receipt candidate found; verify original route first"
                    )
            sources = read_legacy_freeze_sources(
                cur, environment=args.environment, run_id=args.run_id
            )
            for pipeline in sources["pipelines"]:
                if pipeline["command"] != "freeze-week":
                    continue
                prefix = f"artifacts/{args.environment}/pipeline-runs/{pipeline['pipeline_run_id']}/"
                if readonly.list_files(prefix):
                    raise ProspectiveRecordError(
                        "retained freeze pipeline artifacts require original receipt review first"
                    )
            if any(
                ref.get("freeze_receipt_uri")
                for step in sources["steps"]
                for ref in step["output_refs"]
            ):
                raise ProspectiveRecordError(
                    "retained step references an original receipt; verify it first"
                )
            code_sha = subprocess.check_output(
                ["git", "rev-parse", args.historical_freeze_code_sha + "^{commit}"],
                text=True,
            ).strip()
            freeze_source = subprocess.check_output(
                ["git", "show", code_sha + ":scripts/pipeline/freeze_week.py"],
                text=True,
            )
            objects = {}
            refs = []
            for kind, value in (
                ("source-query", sources),
                (
                    "historical-code",
                    dict(code_sha=code_sha, freeze_source=freeze_source),
                ),
            ):
                raw = canonical_json(value)
                sha = hashlib.sha256(raw).hexdigest()
                uri = f"artifacts/prospective/v5/environment={args.environment}/season=2026/week=5/{args.run_id}/legacy-attestation-v1-{kind}-{sha}.json"
                objects[uri] = raw
                refs.append(dict(uri=uri, sha256=sha))
            run = next(r for r in sources["runs"] if r["run_id"] == args.run_id)

            def ref(uri):
                return dict(
                    uri=uri, sha256=hashlib.sha256(readonly.read_bytes(uri)).hexdigest()
                )

            manifest_uri = f"artifacts/{args.environment}/predictions/year=2026/week=5/run_id={args.run_id}/manifest.json"
            schedule_uri = next(
                r["uri"]
                for r in run["input_dataset_refs"]
                if r.get("dataset") == "games"
            )
            payload = build_legacy_freeze_attestation(
                sources=sources,
                environment=args.environment,
                run_id=args.run_id,
                decision_ref=args.decision_ref,
                historical_freeze_code_sha=code_sha,
                original_prediction_manifest=ref(manifest_uri),
                original_prediction_artifact=ref(run["artifact_uri"]),
                contemporaneous_schedule_evidence=ref(schedule_uri),
                source_snapshot_refs=refs,
            )
            verify_legacy_freeze_attestation(
                payload,
                cur=cur,
                storage=Overlay(readonly, objects),
                environment=args.environment,
            )
            raw = canonical_json(payload)
            args.output.write_bytes(raw)
            if not args.apply:
                print("Verified local dry-run candidate; no R2 or database writes")
                return
            # Only reached by a separately authorized user-run --apply operation.
            for uri, source_raw in objects.items():
                write_immutable(storage, uri, source_raw)
            register_legacy_freeze_attestation(
                cur, storage=storage, environment=args.environment, payload=payload
            )
        conn.commit()
    print("Registered exact environment-specific legacy attestation")


if __name__ == "__main__":
    main()
