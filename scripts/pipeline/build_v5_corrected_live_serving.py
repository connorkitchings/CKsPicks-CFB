#!/usr/bin/env python3
"""Build the serving rows of a corrected live week (pending, candidate; Preview).

The Week 5 builder (`build_v5_intended_update_live_serving.py`) stays as it was. This one
takes the week from the corrected successor lock's ``active_week``. By default every game of
the week must still be ahead of the cutoff, exactly as before. ``--display-only`` (Contract
04, Amendment 9) lets the run cover only the games that have not kicked off at the cutoff: the
rest are listed in the manifest, nothing is given an earlier timestamp, the evidence class
stays ``pending`` and the run is never frozen or closed.

    zsh scripts/ops/with_preview_env.sh uv run python \\
        scripts/pipeline/build_v5_corrected_live_serving.py \\
        --source-lock <lock> --release-tag <tag> --market-ref-uri <snapshots ref> \\
        --as-of <ISO time> --local-output <dir> [--display-only]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from omegaconf import OmegaConf

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.artifacts import dataframe_csv_bytes  # noqa: E402
from cks_picks_cfb.data.data_first_phase2d import (  # noqa: E402
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.inference.v5_serving import build_v5_serving_rows  # noqa: E402
from cks_picks_cfb.inference.weekly import resolve_label_thresholds  # noqa: E402
from cks_picks_cfb.ratings_lab.artifacts import canonical_json  # noqa: E402
from cks_picks_cfb.rebuild.live_week import kicked_off_game_ids  # noqa: E402
from cks_picks_cfb.rebuild.successor_sources import (  # noqa: E402
    is_corrected,
    lineage,
    lock_schedule,
)
from scripts.pipeline.build_v5_intended_update_forecasts import (  # noqa: E402
    OUTPUT_ROOT as FORECAST_ROOT,
)
from scripts.pipeline.build_v5_intended_update_serving import (  # noqa: E402
    OUTPUT_ROOT as SERVING_ROOT,
)

CONFIG = REPO_ROOT / "conf/weekly_bets/v5_intended_update_2026.yaml"
MAX_DISPLAY_AGE_HOURS = 6


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def live_week(lock: dict[str, Any]) -> int:
    """The lock's live week (the corrected lock must name one)."""
    if not is_corrected(lock) or not lineage(lock).get("live_week"):
        raise ValueError("the source lock names no live week")
    week = int(lock["active_week"]["week"])
    if int(lineage(lock)["live_week"]["week"]) != week:
        raise ValueError("the lock's live week differs from its active week")
    return week


def run_uris(week: int, release_tag: str) -> tuple[str, str, str]:
    if not re.fullmatch(r"[a-z0-9-]+", release_tag):
        raise ValueError("invalid live release tag")
    run_id = f"2026w{week}-v5repair-{release_tag}"
    return (
        run_id,
        f"{FORECAST_ROOT}/{release_tag}/week={week}/forecast-manifest.json",
        f"{SERVING_ROOT}/{run_id}/serving-manifest.json",
    )


def receipt_uri(week: int, release_tag: str) -> str:
    serving = run_uris(week, release_tag)[2]
    return f"{serving.rsplit('/', 1)[0]}/verification/verifier-manifest.json"


def _frame(storage: Any, ref: dict[str, Any]) -> pd.DataFrame:
    raw = storage.read_bytes(ref["uri"])
    if _sha(raw) != ref["content_sha"]:
        raise ValueError("market parent changed")
    return pd.read_parquet(io.BytesIO(raw))


def market_refs(storage: Any, market_ref_uri: str) -> dict[str, dict[str, Any]]:
    """The fresh snapshot and quote refs (the quote ref sits beside the snapshot ref)."""
    out = {}
    for dataset, uri in (
        ("market_snapshots", market_ref_uri),
        ("market_quotes", f"{market_ref_uri.rsplit('/', 1)[0]}/market_quotes_ref.json"),
    ):
        raw = storage.read_bytes(uri)
        ref = json.loads(raw)
        if ref.get("dataset") != dataset:
            raise ValueError(f"market ref {uri} has another dataset")
        out[dataset] = {"ref": ref, "uri": uri, "raw_sha256": _sha(raw)}
    return out


def serving_slate(
    schedule: pd.DataFrame, week: int, cutoff: pd.Timestamp, *, display_only: bool
) -> tuple[pd.DataFrame, list[int]]:
    """(games to serve, ids already kicked off). Without display-only any kickoff is an error."""
    kicked = kicked_off_game_ids(schedule, week, str(cutoff.isoformat()))
    if kicked and not display_only:
        raise ValueError(
            f"{len(kicked)} week-{week} games kicked off at or before the cutoff; "
            "a display-only run is required"
        )
    slate = schedule[schedule["week"].astype(int).eq(week)]
    return slate[~slate["game_id"].astype(int).isin(kicked)].copy(), kicked


def build(
    storage: Any,
    lock_raw: bytes,
    *,
    release_tag: str,
    market_ref_uri: str,
    as_of: str,
    display_only: bool,
    now: pd.Timestamp | None = None,
) -> tuple[dict[str, Any], bytes]:
    lock = json.loads(lock_raw)
    week = live_week(lock)
    run_id, forecast_uri, _ = run_uris(week, release_tag)
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None:
        raise ValueError("the serving cutoff must be timezone-aware")
    cutoff = cutoff.tz_convert("UTC")
    if cutoff > (now or pd.Timestamp.now(tz="UTC")):
        raise ValueError("the serving cutoff is in the future")

    forecast_raw = storage.read_bytes(forecast_uri)
    forecast = json.loads(forecast_raw)
    verify_signed_payload(forecast, label="corrected live forecast")
    if (
        forecast.get("state") != "candidate"
        or forecast.get("timing_class") != "live"
        or forecast.get("evidence_class") != "pending"
        or forecast.get("identity", {}).get("run_id") != run_id
        or forecast.get("parents", {}).get("source_lock_sha256") != _sha(lock_raw)
    ):
        raise ValueError("the forecast is not this lock's live candidate")
    live = forecast.get("live") or {}
    if display_only and (
        not live.get("display_only") or pd.Timestamp(live["as_of"]) != cutoff
    ):
        raise ValueError(
            "a display-only serving needs the forecast built at the same cutoff"
        )
    forecast_csv = storage.read_bytes(forecast["prediction_ref"]["uri"])
    if _sha(forecast_csv) != forecast["prediction_ref"]["raw_sha256"]:
        raise ValueError("forecast child changed")

    refs = market_refs(storage, market_ref_uri)
    markets = _frame(storage, refs["market_snapshots"]["ref"])
    quotes = _frame(storage, refs["market_quotes"]["ref"])
    schedule = lock_schedule(storage, lock, canonical=False)
    schedule = schedule[
        schedule["home_classification"].eq("fbs")
        & schedule["away_classification"].eq("fbs")
    ].copy()
    schedule["start_date"] = schedule["kickoff_utc"]
    slate, kicked = serving_slate(schedule, week, cutoff, display_only=display_only)
    if sorted(live.get("omitted_kicked_off_game_ids", [])) != kicked and display_only:
        raise ValueError("the forecast omitted a different set of games")

    config = OmegaConf.load(CONFIG)
    thresholds = resolve_label_thresholds(config)
    rows = (
        build_v5_serving_rows(
            pd.read_csv(io.BytesIO(forecast_csv)),
            slate,
            slate,
            markets,
            forecast_run_id=run_id,
            forecast_manifest_sha256=_sha(forecast_raw),
            year=2026,
            week=week,
            as_of=str(cutoff.isoformat()),
            run_id=run_id,
            spread_threshold=thresholds[0],
            spread_threshold_high=thresholds[1],
            total_threshold=thresholds[2],
            timing_class="live",
            market_quotes=quotes,
        )
        .sort_values("game_id", kind="mergesort")
        .reset_index(drop=True)
    )
    expected = set(slate["game_id"].astype(int))
    if len(rows) != len(expected) or set(rows["game_id"].astype(int)) != expected:
        raise ValueError("live serving game population differs")
    unlined = sorted(
        int(g)
        for g in rows.loc[
            rows[["home_team_spread_line", "total_line"]].isna().any(axis=1), "game_id"
        ]
    )
    if unlined and not display_only:
        raise ValueError("live serving lacks a complete market")
    raw = dataframe_csv_bytes(rows)
    first_included = min(pd.to_datetime(slate["kickoff_utc"], utc=True))
    manifest = signed_payload(
        {
            "schema_version": "v5_intended_update_2026_serving_manifest_v1",
            "state": "candidate",
            "evidence_class": "pending",
            "identity": {
                "run_id": run_id,
                "season": 2026,
                "week": week,
                "code_sha": forecast["identity"]["code_sha"],
            },
            "parents": {
                "source_lock_sha256": _sha(lock_raw),
                "forecast_manifest_raw_sha256": _sha(forecast_raw),
                "market_snapshots_ref_uri": refs["market_snapshots"]["uri"],
                "market_snapshots_ref_raw_sha256": refs["market_snapshots"][
                    "raw_sha256"
                ],
                "market_quotes_ref_uri": refs["market_quotes"]["uri"],
                "market_quotes_ref_raw_sha256": refs["market_quotes"]["raw_sha256"],
                "market_snapshot_content_sha256": refs["market_snapshots"]["ref"][
                    "content_sha"
                ],
                "market_quote_content_sha256": refs["market_quotes"]["ref"][
                    "content_sha"
                ],
            },
            "prediction_ref": {
                "uri": f"{SERVING_ROOT}/{run_id}/predictions.csv",
                "raw_sha256": _sha(raw),
                "rows": len(rows),
            },
            "quote_count": int(
                rows["spread_market_quote_id"].notna().sum()
                + rows["total_market_quote_id"].notna().sum()
            ),
            "game_count": len(rows),
            "data_as_of": str(cutoff.isoformat()),
            "display_only": bool(display_only),
            "omitted_kicked_off_game_ids": kicked,
            "unlined_game_ids": unlined,
            "first_included_kickoff_utc": first_included.isoformat(),
            "production_activation_authorized": False,
        }
    )
    return manifest, raw


def _write_once(storage: Any, uri: str, raw: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != raw:
            raise FileExistsError(f"immutable live serving collision: {uri}")
    else:
        storage.write_bytes(raw, uri)


def apply_window_open(
    manifest: dict[str, Any], *, now: pd.Timestamp, display_only: bool
) -> bool:
    """May this manifest still be published? (the guard, relaxed only for display-only)."""
    if display_only:
        age = now - pd.Timestamp(manifest["data_as_of"])
        return pd.Timedelta(0) <= age <= pd.Timedelta(hours=MAX_DISPLAY_AGE_HOURS)
    return now < pd.Timestamp(manifest["first_included_kickoff_utc"])


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--market-ref-uri", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--local-output", type=Path, required=True)
    parser.add_argument("--display-only", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-manifest-sha")
    parser.add_argument("--expected-code-sha")
    args = parser.parse_args()
    if (
        os.getenv("CFB_STORAGE_BACKEND") != "r2"
        or os.getenv("CFB_ARTIFACT_ENV") != "preview"
    ):
        raise SystemExit("corrected live serving requires Preview R2")
    if args.local_output.resolve().is_relative_to(REPO_ROOT / "data"):
        raise SystemExit("output cannot be repository ./data")
    storage = get_storage(environment="preview")
    lock_raw = args.source_lock.read_bytes()
    manifest, predictions_raw = build(
        storage,
        lock_raw,
        release_tag=args.release_tag,
        market_ref_uri=args.market_ref_uri,
        as_of=args.as_of,
        display_only=args.display_only,
    )
    manifest_raw = canonical_json(manifest)
    args.local_output.mkdir(parents=True, exist_ok=True)
    (args.local_output / "serving-manifest.json").write_bytes(manifest_raw)
    (args.local_output / "predictions.csv").write_bytes(predictions_raw)
    digest = _sha(manifest_raw)
    if args.apply:
        if not apply_window_open(
            manifest, now=pd.Timestamp.now(tz="UTC"), display_only=args.display_only
        ):
            raise SystemExit(
                "the publication window is closed (a display-only run must be at most "
                f"{MAX_DISPLAY_AGE_HOURS} hours old)"
                if args.display_only
                else "the prospective serving window has closed"
            )
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], text=True
        ).strip()
        if (
            dirty
            or head != args.expected_code_sha
            or digest != args.expected_manifest_sha
        ):
            raise SystemExit(
                "publication requires reviewed output and clean committed code"
            )
        week = int(manifest["identity"]["week"])
        _write_once(storage, manifest["prediction_ref"]["uri"], predictions_raw)
        _write_once(storage, run_uris(week, args.release_tag)[2], manifest_raw)
    print(
        json.dumps(
            {
                "run_id": manifest["identity"]["run_id"],
                "manifest_sha256": digest,
                "games": manifest["game_count"],
                "omitted_kicked_off": len(manifest["omitted_kicked_off_game_ids"]),
                "unlined": len(manifest["unlined_game_ids"]),
                "display_only": manifest["display_only"],
                "applied": args.apply,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
