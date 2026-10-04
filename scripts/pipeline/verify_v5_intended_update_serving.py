#!/usr/bin/env python3
"""Independently check repaired serving quotes and grades against locked sources."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings_lab.artifacts import canonical_json
from scripts.pipeline.build_v5_intended_update_serving import OUTPUT_ROOT

SCHEMA = "v5_intended_update_2026_serving_verification_v1"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _frame(path: Path | None, sha: str, *, uri: str, storage: Any) -> pd.DataFrame:
    raw = path.read_bytes() if path is not None else storage.read_bytes(uri)
    if _sha(raw) != sha:
        raise ValueError(f"source checksum differs: {uri}")
    return pd.read_parquet(io.BytesIO(raw))


def _result(side: str, *, target: str, line: float, home: int, away: int) -> str:
    if side == "No Bet":
        return "No Bet"
    delta = (home - away + line) if target == "spread" else (home + away - line)
    if delta == 0:
        return "Push"
    favorable = side in ({"Home", "Over"} if delta > 0 else {"Away", "Under"})
    return "Win" if favorable else "Loss"


def _verify_target(row: pd.Series, quotes: pd.DataFrame, *, target: str) -> None:
    spread = target == "spread"
    canonical = row["canonical_spread_line" if spread else "canonical_total_line"]
    prediction = float(row["Spread Prediction" if spread else "Total Prediction"])
    selected_id = row["spread_market_quote_id" if spread else "total_market_quote_id"]
    selected_point = row["home_team_spread_line" if spread else "total_line"]
    selected_price = row[
        "spread_market_quote_price" if spread else "total_market_quote_price"
    ]
    bet = row["Spread Bet" if spread else "Total Bet"]
    if pd.isna(canonical):
        if pd.notna(selected_id) or pd.notna(selected_point) or bet != "No Bet":
            raise ValueError("unlined target has selected quote or bet")
        return
    direction = (
        ("Home" if prediction + canonical > 0 else "Away")
        if spread
        else ("Over" if prediction > canonical else "Under")
    )
    linked = set(json.loads(row["source_quote_ids"]))
    candidates = (
        quotes[
            quotes.game_id.eq(int(row["game_id"]))
            & quotes.quote_id.isin(linked)
            & pd.to_datetime(quotes.captured_at, utc=True).lt(
                pd.Timestamp(row["start_date"])
            )
        ]
        .dropna(subset=["spread" if spread else "total"])
        .copy()
    )
    if candidates.empty:
        if pd.notna(selected_id) or pd.notna(selected_point) or bet != "No Bet":
            raise ValueError("missing candidate target has a quote or bet")
        return
    point_col = "spread" if spread else "total"
    # Home-signed spreads: highest line is best for Home, lowest for Away.
    # Totals: lowest is best for Over, highest for Under.
    ascending = direction == "Away" if spread else direction == "Over"
    candidates = candidates.sort_values(
        [point_col, "quote_id"], ascending=[ascending, True]
    )
    best = candidates.iloc[0]
    if (
        str(selected_id) != str(best["quote_id"])
        or abs(float(selected_point) - float(best[point_col])) > 1e-9
        or abs(float(selected_price) - (-110.0)) > 1e-9
    ):
        raise ValueError("selected quote differs from original eligible best quote")
    edge = (
        abs(prediction + selected_point) if spread else abs(prediction - selected_point)
    )
    actual_edge = float(row["edge_spread" if spread else "edge_total"])
    if abs(edge - actual_edge) > 1e-8:
        raise ValueError("selected quote edge differs")
    threshold = 1.0
    expected_bet = direction if edge >= threshold else "No Bet"
    if bet != expected_bet:
        raise ValueError("selected quote bet differs from unchanged threshold")


def verify(
    *,
    source_lock: Path,
    serving_dir: Path | None,
    market_cache: Path | None,
    release_tag: str,
    verification_output: Path | None = None,
) -> dict[int, dict]:
    lock_raw = source_lock.read_bytes()
    lock = json.loads(lock_raw)
    game_columns = lock["games"]["columns"]
    games = pd.DataFrame(lock["games"]["rows"], columns=game_columns).set_index(
        "game_id"
    )
    storage = (
        get_storage(environment="preview")
        if serving_dir is None or market_cache is None
        else None
    )
    results = {}
    for key, market in sorted(
        lock["market_sources"].items(), key=lambda pair: int(pair[0])
    ):
        week = int(key)
        run_id = f"2026w{week}-v5repair-{release_tag}"
        prefix = f"{OUTPUT_ROOT}/{run_id}"
        root = serving_dir / f"week={week}" if serving_dir is not None else None
        manifest_raw = (
            (root / "serving-manifest.json").read_bytes()
            if root is not None
            else storage.read_bytes(f"{prefix}/serving-manifest.json")
        )
        manifest = json.loads(manifest_raw)
        verify_signed_payload(manifest, label="repaired serving manifest")
        if (
            manifest.get("schema_version")
            != "v5_intended_update_2026_serving_manifest_v1"
            or manifest.get("parents", {}).get("source_lock_sha256") != _sha(lock_raw)
            or int(manifest["identity"]["week"]) != week
        ):
            raise ValueError("serving manifest source identity differs")
        prediction_raw = (
            (root / "predictions.csv").read_bytes()
            if root is not None
            else storage.read_bytes(manifest["prediction_ref"]["uri"])
        )
        scored_raw = (
            (root / "scored.csv").read_bytes()
            if root is not None
            else storage.read_bytes(manifest["scored_ref"]["uri"])
        )
        if (
            _sha(prediction_raw) != manifest["prediction_ref"]["raw_sha256"]
            or _sha(scored_raw) != manifest["scored_ref"]["raw_sha256"]
        ):
            raise ValueError("serving child checksum differs")
        predictions = pd.read_csv(io.BytesIO(prediction_raw))
        scored = pd.read_csv(io.BytesIO(scored_raw))
        expected = set(games[games.week.eq(week)].index.astype(int))
        if (
            len(predictions) != len(expected)
            or set(predictions.game_id.astype(int)) != expected
            or len(scored) != len(expected)
            or set(scored.game_id.astype(int)) != expected
        ):
            raise ValueError("serving prediction or grade keys differ")
        quotes = _frame(
            market_cache / f"quotes_w{week}.source.parquet" if market_cache else None,
            market["market_quotes"]["content_sha"],
            uri=market["market_quotes"]["uri"],
            storage=storage,
        )
        snapshots = _frame(
            market_cache / f"markets_w{week}.source.parquet" if market_cache else None,
            market["market_snapshots"]["content_sha"],
            uri=market["market_snapshots"]["uri"],
            storage=storage,
        ).set_index("game_id")
        for _, item in scored.iterrows():
            game_id = int(item["game_id"])
            frozen = games.loc[game_id]
            snap = snapshots.loc[game_id]
            if (
                item["market_snapshot_id"] != snap["market_snapshot_id"]
                or abs(
                    float(item["canonical_spread_line"]) - float(snap["spread_line"])
                )
                > 1e-9
                or (
                    pd.notna(snap["total_line"])
                    and abs(
                        float(item["canonical_total_line"]) - float(snap["total_line"])
                    )
                    > 1e-9
                )
            ):
                raise ValueError("serving canonical snapshot differs")
            for target in ("spread", "total"):
                _verify_target(item, quotes, target=target)
                line = item[
                    "home_team_spread_line" if target == "spread" else "total_line"
                ]
                actual = item[
                    "Spread Bet Result" if target == "spread" else "Total Bet Result"
                ]
                if pd.isna(line):
                    if pd.notna(actual):
                        raise ValueError("unlined target has a grade")
                else:
                    expected_result = (
                        "No Bet"
                        if target == "total" and float(item["edge_total"]) < 1.5
                        else _result(
                            str(
                                item[
                                    "Spread Bet" if target == "spread" else "Total Bet"
                                ]
                            ),
                            target=target,
                            line=float(line),
                            home=int(frozen["home_points"]),
                            away=int(frozen["away_points"]),
                        )
                    )
                    if actual != expected_result:
                        raise ValueError("grade differs from certified final")
        receipt = signed_payload(
            {
                "schema_version": SCHEMA,
                "state": "verified",
                "season": 2026,
                "week": week,
                "run_id": manifest["identity"]["run_id"],
                "serving_manifest_raw_sha256": _sha(manifest_raw),
                "source_lock_sha256": _sha(lock_raw),
                "game_count": len(expected),
                "quote_count": manifest["quote_count"],
                "verified": True,
            }
        )
        verification_dir = (
            root / "verification"
            if root is not None
            else verification_output / f"week={week}" / "verification"
            if verification_output
            else None
        )
        if verification_dir is not None:
            verification_dir.mkdir(parents=True, exist_ok=True)
            (verification_dir / "verifier-manifest.json").write_bytes(
                canonical_json(receipt)
            )
        results[week] = receipt
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--serving-dir", type=Path)
    parser.add_argument("--market-cache", type=Path)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--verification-output", type=Path)
    parser.add_argument("--preflight-evidence", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and (args.serving_dir or args.market_cache):
        raise ValueError("serving verification apply must re-read exact R2 sources")
    result = verify(
        source_lock=args.source_lock,
        serving_dir=args.serving_dir,
        market_cache=args.market_cache,
        release_tag=args.release_tag,
        verification_output=args.verification_output,
    )
    if args.apply:
        if not args.preflight_evidence or json.loads(
            args.preflight_evidence.read_bytes()
        ) != {str(week): receipt for week, receipt in result.items()}:
            raise ValueError("serving verification differs from reviewed preflight")
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], text=True
        ).strip()
        if dirty:
            raise ValueError("verifier publication requires clean committed code")
        storage = get_storage(environment="preview")
        for receipt in result.values():
            uri = (
                f"{OUTPUT_ROOT}/{receipt['run_id']}/verification/verifier-manifest.json"
            )
            raw = canonical_json(receipt)
            if storage.exists(uri):
                if storage.read_bytes(uri) != raw:
                    raise ValueError("immutable successor serving verifier collision")
            else:
                storage.write_bytes(raw, uri)
    print(
        json.dumps(
            {
                week: {"games": receipt["game_count"], "verified": True}
                for week, receipt in result.items()
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
