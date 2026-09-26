#!/usr/bin/env python3
"""Production release tooling for V5 best-quote replacement runs (Task 6).

The replacement artifacts were verified on Preview (batch
``2026w{0..4}-v5replay-bestquote-20260926-r2``). This driver promotes them
to production without touching Neon until the authorized release steps:

  prepare --week N   Copy one verified Preview run into the production R2
                     namespace (byte-identical CSVs; manifest rewritten only
                     for its artifact URIs). R2 writes only.
  packet  --week N   Emit the exact authorization-record JSON from the
                     production manifest. Local file only.
  score   --week N   Threshold-aware scoring of a published production run
                     (Weeks 0-3 only; all spreads, totals at edge >= 1.5).
  verify  --week N   Read-only verification against production: forecast
                     equality with the selected original, selection lineage,
                     grade settlement, market-tick lines, and run state.

Release run IDs are identical across namespaces (prior lane precedent).
``score`` and ``verify`` require CFB_ARTIFACT_ENV=production and refuse
any Preview database URL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from omegaconf import OmegaConf

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "pipeline"))

from cks_picks_cfb.artifacts import (  # noqa: E402
    prediction_run_artifact_path,
    prediction_run_features_path,
    prediction_run_manifest_path,
)
from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from scripts.pipeline.rehearse_v5_bestquote_replay_preview import (  # noqa: E402
    SCORED_WEEKS,
    WEEK_DATASETS,
    _score_week,
    verify_forecast_equality,
    verify_grades,
    verify_selections,
)

DECISION_REF = "v5-bestquote-replacement-review-2026-09-26"

RELEASE_RUNS = {
    0: "2026w0-v5replay-bestquote-20260926-r2",
    1: "2026w1-v5replay-bestquote-20260926-r2",
    2: "2026w2-v5replay-bestquote-20260926-r2",
    3: "2026w3-v5replay-bestquote-20260926-r2",
    4: "2026w4-v5replay-bestquote-20260926-r2",
}


def run_id_for(week: int) -> str:
    return RELEASE_RUNS[week]


def production_manifest(preview_manifest: dict[str, Any]) -> dict[str, Any]:
    """Rewrite a verified Preview manifest for the production namespace.

    Only the internal artifact pointers move; every identity, parent, and
    validation field is preserved, so the packet validator and the replay
    authorization boundary see the same evidence.
    """
    manifest = dict(preview_manifest)
    for key in ("artifact_uri", "feature_snapshot_uri"):
        uri = str(manifest.get(key) or "")
        if not uri.startswith("artifacts/preview/"):
            raise ValueError(
                f"production promotion refuses non-preview manifest URI: {uri}"
            )
        manifest[key] = "artifacts/production/" + uri[len("artifacts/preview/") :]
    return manifest


def prepare_week(week: int, *, dry_run: bool = False) -> dict[str, Any]:
    src = get_storage(environment="preview")
    dst = get_storage(environment="production")
    run_id = run_id_for(week)
    receipt: dict[str, Any] = {"week": week, "run_id": run_id, "files": {}}

    csv_uri = prediction_run_artifact_path(2026, week, run_id)
    features_uri = prediction_run_features_path(2026, week, run_id)
    manifest_uri = prediction_run_manifest_path(2026, week, run_id)
    csv_bytes = src.read_bytes(csv_uri)
    features_bytes = src.read_bytes(features_uri)
    preview_manifest = json.loads(src.read_bytes(manifest_uri))
    manifest = production_manifest(preview_manifest)
    manifest_bytes = json.dumps(manifest, sort_keys=True, indent=1).encode()

    # Byte identity of the CSVs pins the reviewed evidence.
    assert hashlib.sha256(csv_bytes).hexdigest() == manifest["artifact_sha256"], (
        f"Week {week}: preview artifact SHA differs from its manifest"
    )
    dst_csv = csv_uri.replace("artifacts/preview/", "artifacts/production/", 1)
    dst_features = features_uri.replace(
        "artifacts/preview/", "artifacts/production/", 1
    )
    dst_manifest = manifest_uri.replace(
        "artifacts/preview/", "artifacts/production/", 1
    )
    assert manifest["artifact_uri"] == dst_csv
    assert manifest["feature_snapshot_uri"] == dst_features

    for dst_uri, payload in (
        (dst_csv, csv_bytes),
        (dst_features, features_bytes),
        (dst_manifest, manifest_bytes),
    ):
        if dst.exists(dst_uri):
            existing = dst.read_bytes(dst_uri)
            if existing != payload:
                raise FileExistsError(
                    f"Week {week}: production object {dst_uri} exists with "
                    "different bytes; refusing to overwrite an immutable run"
                )
            receipt["files"][dst_uri] = "already-present-byte-identical"
        else:
            if not dry_run:
                dst.write_bytes(payload, dst_uri)
            receipt["files"][dst_uri] = "written" if not dry_run else "dry-run"
    print(f"Week {week} prepared: {run_id} ({receipt['files']})")
    return receipt


def authorization_record(
    week: int, manifest: Mapping[str, Any], *, decision_ref: str = DECISION_REF
) -> dict[str, Any]:
    replay_uri = str(manifest["v5_replay_manifest_uri"])
    record = {
        "authorization_id": (
            f"v5-bestquote-2026w{week}-{manifest['artifact_sha256'][:8]}"
        ),
        "environment": "production",
        "season": 2026,
        "week": week,
        "prediction_run_id": manifest["run_id"],
        "model_id": manifest["model_id"],
        "inference_bundle_sha256": manifest["inference_bundle_sha256"],
        "replay_manifest_uri": replay_uri,
        "replay_manifest_sha256": manifest["v5_replay_manifest_sha256"],
        "verifier_uri": (
            f"{replay_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
        ),
        "verifier_sha256": manifest["replay_verification_sha256"],
        "serving_config_sha256": manifest["config_sha"],
        "prediction_artifact_uri": manifest["artifact_uri"],
        "prediction_artifact_sha256": manifest["artifact_sha256"],
        "decision_ref": decision_ref,
    }
    if any(v is None for v in record.values()):
        missing = [k for k, v in record.items() if v is None]
        raise ValueError(f"Week {week}: authorization record lacks {missing}")
    if record["prediction_run_id"] != run_id_for(week):
        raise ValueError(
            f"Week {week}: manifest run {record['prediction_run_id']} is not "
            f"the release run {run_id_for(week)}"
        )
    return record


def packet_week(week: int, out_dir: Path) -> Path:
    dst = get_storage(environment="production")
    run_id = run_id_for(week)
    manifest = json.loads(
        dst.read_bytes(prediction_run_manifest_path(2026, week, run_id))
    )
    record = authorization_record(week, manifest)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"bestquote-2026w{week}-{run_id}.json"
    path.write_text(json.dumps(record, sort_keys=True, indent=1) + "\n")
    print(f"Week {week} packet: {path} ({record['authorization_id']})")
    return path


def _production_db_url() -> str:
    if os.getenv("CFB_ARTIFACT_ENV") != "production":
        raise SystemExit("production score/verify require CFB_ARTIFACT_ENV=production")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    if url == os.getenv("PREVIEW_DATABASE_URL"):
        raise SystemExit("refusing to treat a Preview URL as production")
    return url


def _thresholds(week: int) -> tuple[float, float]:
    cfg = OmegaConf.load(WEEK_DATASETS[week]["config"])
    return float(cfg.spread_edge_threshold), float(cfg.total_edge_threshold)


def score_week(week: int) -> None:
    if week not in SCORED_WEEKS:
        raise SystemExit(f"Week {week} has no certified finals; scoring refused")
    db_url = _production_db_url()
    spread_threshold, total_threshold = _thresholds(week)
    _score_week(
        db_url,
        week,
        run_id_for(week),
        spread_threshold=spread_threshold,
        total_threshold=total_threshold,
    )


def verify_market_ticks(db_url: str, week: int, run_id: str) -> None:
    """Every served line must be a real market increment (.0/.5)."""
    import psycopg

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  COUNT(*) FILTER (WHERE COALESCE(pms_s.point, p.home_team_spread_line) * 2
                    <> floor(COALESCE(pms_s.point, p.home_team_spread_line) * 2)),
                  COUNT(*) FILTER (WHERE COALESCE(pms_t.point, p.total_line) * 2
                    <> floor(COALESCE(pms_t.point, p.total_line) * 2))
                FROM predictions p
                LEFT JOIN prediction_market_selections pms_s
                  ON pms_s.run_id = p.run_id AND pms_s.game_id = p.game_id
                 AND pms_s.target = 'spread'
                LEFT JOIN prediction_market_selections pms_t
                  ON pms_t.run_id = p.run_id AND pms_t.game_id = p.game_id
                 AND pms_t.target = 'total'
                WHERE p.run_id = %s
                """,
                (run_id,),
            )
            bad_spread, bad_total = cur.fetchone()
    assert bad_spread == 0 and bad_total == 0, (
        f"Week {week}: {bad_spread} spread / {bad_total} total served lines "
        "are not real market increments"
    )
    print("  market ticks: all served lines are real increments ✓")


def verify_week(week: int) -> dict[str, Any]:
    db_url = _production_db_url()
    run_id = run_id_for(week)
    spread_threshold, total_threshold = _thresholds(week)
    verify_forecast_equality(db_url, week, run_id)
    verify_selections(db_url, week, run_id)
    if week in SCORED_WEEKS:
        verify_grades(
            db_url,
            week,
            run_id,
            spread_threshold=spread_threshold,
            total_threshold=total_threshold,
        )
    verify_market_ticks(db_url, week, run_id)
    print(f"Week {week} {run_id}: production verification passed ✓")
    return {"week": week, "run_id": run_id}


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "packet", "score", "verify"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--week", type=int, choices=range(5), required=True)
        if name == "packet":
            cmd.add_argument(
                "--out",
                type=Path,
                default=Path("artifacts/release-packets"),
                help="Directory for authorization-record JSON files",
            )
    cmd_args = parser.parse_args()
    if cmd_args.command == "prepare":
        prepare_week(cmd_args.week)
    elif cmd_args.command == "packet":
        packet_week(cmd_args.week, cmd_args.out)
    elif cmd_args.command == "score":
        score_week(cmd_args.week)
    elif cmd_args.command == "verify":
        verify_week(cmd_args.week)


if __name__ == "__main__":
    main()
