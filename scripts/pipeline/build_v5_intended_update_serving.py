#!/usr/bin/env python3
"""Build retrospective serving predictions and grades from pinned market quotes."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from omegaconf import OmegaConf

from cks_picks_cfb.artifacts import dataframe_csv_bytes
from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.inference.v5_serving import build_v5_serving_rows
from cks_picks_cfb.inference.weekly import resolve_label_thresholds
from cks_picks_cfb.ratings_lab.artifacts import canonical_json
from scripts.pipeline.build_v5_intended_update_forecasts import (
    OUTPUT_ROOT as FORECAST_ROOT,
)
from scripts.pipeline.score_weekly_bets import score_bets

OUTPUT_ROOT = (
    "artifacts/research/data-first-football-v1/forecasts/intended-update/2026-serving"
)
SCHEMA = "v5_intended_update_2026_serving_manifest_v1"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _market_frame(
    ref: dict[str, Any], *, cache: Path | None, week: int, kind: str, storage: Any
) -> pd.DataFrame:
    if cache is None:
        raw = storage.read_bytes(ref["uri"])
    else:
        raw = (cache / f"{kind}_w{week}.source.parquet").read_bytes()
    if _sha(raw) != ref["content_sha"]:
        raise ValueError(f"Week {week} {kind} does not match pinned market object")
    return pd.read_parquet(io.BytesIO(raw))


def _forecast(
    forecast_dir: Path | None,
    week: int,
    source_lock_sha: str,
    *,
    release_tag: str,
    storage: Any,
) -> tuple[pd.DataFrame, dict[str, Any], str]:
    if forecast_dir is None:
        prefix = f"{FORECAST_ROOT}/{release_tag}/week={week}"
        manifest_raw = storage.read_bytes(f"{prefix}/forecast-manifest.json")
    else:
        root = forecast_dir / f"week={week}"
        manifest_raw = (root / "forecast-manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    verify_signed_payload(manifest, label="repaired forecast")
    if (
        manifest.get("schema_version") != "v5_intended_update_2026_forecast_manifest_v1"
        or manifest.get("state") != "frozen"
        or manifest.get("timing_class") != "replay"
        or manifest["parents"]["source_lock_sha256"] != source_lock_sha
    ):
        raise ValueError(f"Week {week} forecast lineage differs")
    raw = (
        storage.read_bytes(manifest["prediction_ref"]["uri"])
        if forecast_dir is None
        else (root / "predictions.csv").read_bytes()
    )
    if _sha(raw) != manifest["prediction_ref"]["raw_sha256"]:
        raise ValueError(f"Week {week} forecast child differs")
    return pd.read_csv(io.BytesIO(raw)), manifest, _sha(manifest_raw)


def build(
    *,
    source_lock: Path,
    forecast_dir: Path | None,
    schedule_cache: Path | None,
    output: Path,
    market_cache: Path | None,
    code_sha: str,
    release_tag: str,
) -> dict[int, dict[str, Any]]:
    lock_raw = source_lock.read_bytes()
    lock = json.loads(lock_raw)
    lock_sha = _sha(lock_raw)
    if not lock.get("market_sources") or not lock.get("selected_runs"):
        raise ValueError("source lock lacks pinned market or selected-run sources")
    game_columns = lock["games"]["columns"]
    games = pd.DataFrame(lock["games"]["rows"], columns=game_columns)
    storage = (
        get_storage(environment="preview")
        if (market_cache is None or forecast_dir is None or schedule_cache is None)
        else None
    )
    if schedule_cache is None:
        parent = lock["research_source_import"]["replay_parents"]
        raw = storage.read_bytes(parent["schedule_uri"])
        if _sha(raw) != parent["schedule_content_sha256"]:
            raise ValueError("pinned serving schedule checksum differs")
        schedule = pd.read_parquet(io.BytesIO(raw))
    else:
        schedule = pd.read_parquet(schedule_cache)
    schedule = schedule[
        schedule.home_classification.eq("fbs") & schedule.away_classification.eq("fbs")
    ].copy()
    schedule["start_date"] = schedule["kickoff_utc"]
    result = {}
    for old in lock["selected_runs"]:
        week = int(old["week"])
        if week >= int(lock["active_week"]["week"]):
            continue
        if old["state"] != "scored":
            raise ValueError(f"Week {week} original run is not certified scored")
        source = lock["market_sources"][str(week)]
        markets = _market_frame(
            source["market_snapshots"],
            cache=market_cache,
            week=week,
            kind="markets",
            storage=storage,
        )
        quotes = _market_frame(
            source["market_quotes"],
            cache=market_cache,
            week=week,
            kind="quotes",
            storage=storage,
        )
        forecast, forecast_manifest, forecast_sha = _forecast(
            forecast_dir, week, lock_sha, release_tag=release_tag, storage=storage
        )
        config_path = Path(source["config"])
        if _sha(config_path.read_bytes()) != source["config_sha256"]:
            raise ValueError(f"Week {week} threshold config changed")
        config = OmegaConf.load(config_path)
        thresholds = resolve_label_thresholds(config)
        run_id = forecast_manifest["identity"]["run_id"]
        serving = build_v5_serving_rows(
            forecast,
            schedule,
            schedule,
            markets,
            forecast_run_id=run_id,
            forecast_manifest_sha256=forecast_sha,
            year=2026,
            week=week,
            as_of=source["as_of"],
            run_id=run_id,
            spread_threshold=thresholds[0],
            spread_threshold_high=thresholds[1],
            total_threshold=thresholds[2],
            timing_class="replay",
            market_quotes=quotes,
        )
        expected = set(games.loc[games.week.eq(week), "game_id"].astype(int))
        if (
            len(serving) != len(expected)
            or set(serving.game_id.astype(int)) != expected
        ):
            raise ValueError(
                f"Week {week} serving game keys differ from locked selection"
            )
        if serving.spread_market_quote_id.isna().any():
            raise ValueError(f"Week {week} has an unquoted spread")
        missing_totals = set(
            serving.loc[serving.total_market_quote_id.isna(), "game_id"].astype(int)
        )
        gaps = lock["market_selection_gap"]
        if isinstance(gaps, dict):
            gaps = [gaps]
        allowed_missing = {
            int(gap["game_id"])
            for gap in gaps
            if int(gap["week"]) == week and gap["target"] == "total"
        }
        if missing_totals != allowed_missing:
            raise ValueError(
                f"Week {week} total quote gaps differ: {missing_totals ^ allowed_missing}"
            )
        week_games = games.loc[
            games.week.eq(week), ["game_id", "home_points", "away_points"]
        ].copy()
        if week_games[["home_points", "away_points"]].isna().any().any():
            raise ValueError(f"Week {week} lacks certified final scores")
        scored = score_bets(
            serving,
            week_games.rename(columns={"game_id": "id"}),
        )
        if float(config.total_edge_threshold) > 0.0:
            scored.loc[
                scored["total_line"].notna()
                & scored["edge_total"].lt(float(config.total_edge_threshold)),
                "Total Bet Result",
            ] = "No Bet"
        # Deterministic row order: upstream schedule order differs between the
        # local-cache and R2 source paths, so sort by game_id for byte-stable
        # artifacts (the --apply evidence guard requires exact equality).
        serving = serving.sort_values("game_id", kind="mergesort").reset_index(
            drop=True
        )
        scored = scored.sort_values("game_id", kind="mergesort").reset_index(drop=True)
        if (
            len(scored) != len(expected)
            or scored[["home_points", "away_points"]].isna().any().any()
        ):
            raise ValueError(f"Week {week} scoring coverage differs")
        week_dir = output / f"week={week}"
        week_dir.mkdir(parents=True, exist_ok=True)
        prediction_raw = dataframe_csv_bytes(serving)
        score_raw = dataframe_csv_bytes(scored)
        (week_dir / "predictions.csv").write_bytes(prediction_raw)
        (week_dir / "scored.csv").write_bytes(score_raw)
        prefix = f"{OUTPUT_ROOT}/{run_id}"
        manifest = signed_payload(
            {
                "schema_version": SCHEMA,
                "state": "candidate",
                "evidence_class": "replay",
                "identity": {
                    "run_id": run_id,
                    "season": 2026,
                    "week": week,
                    "code_sha": code_sha,
                },
                "parents": {
                    "source_lock_sha256": lock_sha,
                    "forecast_manifest_raw_sha256": forecast_sha,
                    "market_snapshot_content_sha256": source["market_snapshots"][
                        "content_sha"
                    ],
                    "market_quote_content_sha256": source["market_quotes"][
                        "content_sha"
                    ],
                    "original_selected_run_id": old["run_id"],
                    "original_data_as_of": old["data_as_of"],
                    "original_final_rows_sha256": lock["game_rows_sha256"],
                },
                "prediction_ref": {
                    "uri": f"{prefix}/predictions.csv",
                    "raw_sha256": _sha(prediction_raw),
                    "rows": len(serving),
                },
                "scored_ref": {
                    "uri": f"{prefix}/scored.csv",
                    "raw_sha256": _sha(score_raw),
                    "rows": len(scored),
                },
                "quote_count": int(
                    serving.spread_market_quote_id.notna().sum()
                    + serving.total_market_quote_id.notna().sum()
                ),
                "game_count": len(expected),
                "data_as_of": source["as_of"],
                "production_activation_authorized": False,
            }
        )
        (week_dir / "serving-manifest.json").write_bytes(canonical_json(manifest))
        result[week] = manifest
    return result


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--forecast-dir", type=Path)
    parser.add_argument("--schedule-cache", type=Path)
    parser.add_argument("--market-cache", type=Path)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--local-output", type=Path, required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--preflight-evidence", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if not head.startswith(args.expected_code_sha):
        raise SystemExit("checked-out code differs from expected parent")
    if args.apply and (args.forecast_dir or args.schedule_cache or args.market_cache):
        raise SystemExit("serving apply must re-read all pinned R2 parents")
    output = args.local_output.resolve()
    forbidden = Path(__file__).resolve().parents[2] / "data"
    if output == forbidden or forbidden in output.parents:
        raise SystemExit("serving output cannot use repository ./data")
    result = build(
        source_lock=args.source_lock,
        forecast_dir=args.forecast_dir,
        schedule_cache=args.schedule_cache,
        output=output,
        market_cache=args.market_cache,
        code_sha=head,
        release_tag=args.release_tag,
    )
    if args.apply:
        if not args.preflight_evidence or json.loads(
            args.preflight_evidence.read_bytes()
        ) != {str(week): manifest for week, manifest in result.items()}:
            raise SystemExit("serving apply differs from reviewed preflight")
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], text=True
        ).strip()
        if dirty or head != args.expected_code_sha:
            raise SystemExit("serving publication requires exact clean committed code")
        storage = get_storage(environment="preview")
        for week, manifest in result.items():
            root = output / f"week={week}"
            for name, ref in (
                ("predictions.csv", manifest["prediction_ref"]),
                ("scored.csv", manifest["scored_ref"]),
            ):
                raw = (root / name).read_bytes()
                if storage.exists(ref["uri"]):
                    if storage.read_bytes(ref["uri"]) != raw:
                        raise ValueError("immutable successor serving child collision")
                else:
                    storage.write_bytes(raw, ref["uri"])
            manifest_uri = (
                f"{OUTPUT_ROOT}/{manifest['identity']['run_id']}/serving-manifest.json"
            )
            raw = (root / "serving-manifest.json").read_bytes()
            if storage.exists(manifest_uri):
                if storage.read_bytes(manifest_uri) != raw:
                    raise ValueError("immutable successor serving manifest collision")
            else:
                storage.write_bytes(raw, manifest_uri)
    print(
        json.dumps(
            {
                week: {
                    "run_id": m["identity"]["run_id"],
                    "games": m["game_count"],
                    "quotes": m["quote_count"],
                }
                for week, m in result.items()
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
