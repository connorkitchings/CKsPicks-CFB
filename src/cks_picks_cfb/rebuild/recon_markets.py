"""Stage 7 (markets) and Stage 8 (finals) for Stage 6B."""

from __future__ import annotations

import io
import json
import os
from typing import Any

import pandas as pd

from cks_picks_cfb.models.market_grading import (
    select_best_quote,
)
from cks_picks_cfb.rebuild import common
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.recon_common import (
    TOTAL_2026_GAMES,
    WEEKS,
    checked_read,
    frame_digest,
    json_data,
    load_partitioned_gold,
    parquet_data,
    read_parquet_data,
    recon_run_id,
    source_refs,
    weekly_as_of,
    write_partitioned_gold,
)
from cks_picks_cfb.rebuild.recon_forecast import PREDICTIONS_PARQUET
from cks_picks_cfb.rebuild.recon_foundation import FOUNDATION_SCHEDULE

MARKETS_SUMMARY = "rebuild/6b/{run_id}/markets/summary.json"
MARKETS_PARQUET = "rebuild/6b/{run_id}/markets/selections.parquet"
MARKETS_DATASET = "reconstruction_market_selections"
MARKETS_SCHEMA_VERSION = "reconstruction_market_selections_v1"

FINALS_SUMMARY = "rebuild/6b/{run_id}/finals/summary.json"
FINALS_PARQUET = "rebuild/6b/{run_id}/finals/finals.parquet"

EXPECTED_SELECTIONS_COUNT = (
    541  # 271 games * 2 targets - 1 missing total (Houston @ Texas Tech)
)
MISSING_TOTAL_GAME_ID = 401856811


# ---------------------------------------------------------------------------
# Stage 7: Market Selections
# ---------------------------------------------------------------------------


def _load_market_data(
    context: StageContext, week: int, storage: Any
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Load market snapshots and quotes for week w."""
    sources = source_refs(context)["weeks"][str(week)]["market_sources"]
    snaps_data = checked_read(storage, sources["market_snapshots"])
    quotes_data = checked_read(storage, sources["market_quotes"])

    snaps = pd.read_parquet(io.BytesIO(snaps_data))
    quotes_df = pd.read_parquet(io.BytesIO(quotes_data))
    quotes_list = quotes_df.to_dict("records")
    return snaps, quotes_list


def build_markets(context: StageContext) -> StageOutput:
    import yaml

    if context.stage.name == "markets":
        config = yaml.safe_load(context.read_input("bets_config"))
        if any(
            float(config[name]) != 0.0
            for name in (
                "spread_edge_threshold",
                "total_lean_threshold",
                "total_edge_threshold",
            )
        ):
            raise GateError("reconstruction threshold config is not all zero")
    storage = common.preview_storage(context)
    sched_key = FOUNDATION_SCHEDULE.format(run_id=context.plan.run_id)
    schedule = read_parquet_data(context.read_artifact("foundation", sched_key))

    preds_key = PREDICTIONS_PARQUET.format(run_id=context.plan.run_id)
    predictions = read_parquet_data(context.read_artifact("predictions", preds_key))

    weekly_selections: dict[int, pd.DataFrame] = {}
    total_selections: list[dict[str, Any]] = []
    observed_quote_gaps: list[dict[str, Any]] = []

    for w in WEEKS:
        snaps, quotes = _load_market_data(context, w, storage)
        if snaps.duplicated("game_id").any():
            raise GateError("original quote set has duplicate canonical snapshots")
        captured = pd.to_datetime(snaps["market_captured_at"], utc=True, errors="raise")
        if (
            captured.isna().any()
            or captured.gt(pd.Timestamp(weekly_as_of(context)[w])).any()
        ):
            raise GateError("market snapshot was captured after as_of")
        snaps_by_game = snaps.set_index("game_id")
        w_schedule = schedule[schedule["week"].eq(w)].set_index("game_id")
        w_preds = predictions[predictions["week"].eq(w)].set_index(
            ["game_id", "target"]
        )
        as_of_dt = pd.Timestamp(weekly_as_of(context)[w]).to_pydatetime()
        run_id_w = recon_run_id(w)

        week_rows: list[dict[str, Any]] = []
        for game_id, game in w_schedule.iterrows():
            game_id = int(game_id)
            if game_id not in snaps_by_game.index:
                raise GateError(f"game {game_id} missing from market snapshots")
            snap = snaps_by_game.loc[game_id]
            snap_id = str(snap["market_snapshot_id"])
            kickoff_utc = pd.to_datetime(game["kickoff_utc"], utc=True).to_pydatetime()

            for target in ("spread", "total"):
                # Prediction target name is margin for spread, total for total
                pred_target = "margin" if target == "spread" else "total"
                pred_row = w_preds.loc[(game_id, pred_target)]
                pred_val = float(pred_row["mean"])

                canon_line = snap.get(target)
                if pd.isna(canon_line):
                    canon_line = None
                else:
                    canon_line = float(canon_line)

                linked = snap.get("source_quote_ids", "[]")
                if isinstance(linked, str):
                    linked = json.loads(linked)
                linked = set(linked or [])
                candidates = [
                    {
                        **quote,
                        "snapshot_id": snap_id,
                        "target": target,
                        "point": quote.get(target),
                    }
                    for quote in quotes
                    if int(quote["game_id"]) == game_id
                    and (not linked or quote["quote_id"] in linked)
                ]
                selected = select_best_quote(
                    target=target,
                    prediction=pred_val,
                    canonical_snapshot_id=snap_id,
                    canonical_line=canon_line,
                    game_id=game_id,
                    kickoff_utc=kickoff_utc,
                    quote_candidates=candidates,
                    forecast_cutoff=as_of_dt,
                )

                if selected is None:
                    observed_quote_gaps.append(
                        {"week": w, "game_id": game_id, "target": target}
                    )
                else:
                    rec = {
                        "run_id": run_id_w,
                        "season": 2026,
                        "week": w,
                        "game_id": game_id,
                        "target": target,
                        "snapshot_id": selected.snapshot_id,
                        "quote_id": selected.quote_id,
                        "side": selected.side,
                        "point": float(selected.point),
                        "price": float(selected.price),
                        "edge": float(selected.edge),
                        "policy_version": selected.policy_version,
                    }
                    week_rows.append(rec)
                    total_selections.append(rec)

        weekly_selections[w] = pd.DataFrame.from_records(week_rows)

    all_selections = pd.DataFrame.from_records(total_selections)
    if len(all_selections) != EXPECTED_SELECTIONS_COUNT:
        raise GateError(
            f"selections count {len(all_selections)} != expected {EXPECTED_SELECTIONS_COUNT}"
        )

    # Check observed quote gaps matches exactly the locked missing total
    if observed_quote_gaps != [
        {"week": 3, "game_id": MISSING_TOTAL_GAME_ID, "target": "total"}
    ]:
        raise GateError(
            f"unexpected quote gaps: expected only game {MISSING_TOTAL_GAME_ID}, got {observed_quote_gaps}"
        )

    lake_summary, lake_files = write_partitioned_gold(
        context,
        dataset=MARKETS_DATASET,
        schema_version=MARKETS_SCHEMA_VERSION,
        frames_by_week=weekly_selections,
        parent_refs=[
            {"dataset": "predictions", "version_id": context.plan.run_id},
        ],
    )

    summary = {
        "status": "passed",
        "total_selections": len(all_selections),
        "weekly_counts": {str(w): len(weekly_selections[w]) for w in WEEKS},
        "quote_gaps": observed_quote_gaps,
        "selections_digest": frame_digest(all_selections),
        "lake_gold": lake_summary,
    }

    prefix_sel = MARKETS_PARQUET.format(run_id=context.plan.run_id)
    prefix_sum = MARKETS_SUMMARY.format(run_id=context.plan.run_id)

    artifacts = [
        (prefix_sel, parquet_data(all_selections)),
        (prefix_sum, json_data(summary)),
        *lake_files,
    ]
    return StageOutput(artifacts=artifacts, metrics={"selections": len(all_selections)})


def verify_markets(context: StageContext) -> list[str]:
    problems: list[str] = []
    prefix_sum = MARKETS_SUMMARY.format(run_id=context.plan.run_id)
    prefix_sel = MARKETS_PARQUET.format(run_id=context.plan.run_id)
    try:
        summary = json.loads(context.read_artifact("markets", prefix_sum))
        sels = read_parquet_data(context.read_artifact("markets", prefix_sel))
    except Exception as exc:
        return [f"failed to read markets artifacts: {exc}"]

    if len(sels) != EXPECTED_SELECTIONS_COUNT:
        problems.append(f"selections count {len(sels)} != {EXPECTED_SELECTIONS_COUNT}")
    if frame_digest(sels) != summary["selections_digest"]:
        problems.append("selections digest mismatch")

    try:
        lake_sels = load_partitioned_gold(context, "markets", summary["lake_gold"])
        if len(lake_sels) != EXPECTED_SELECTIONS_COUNT:
            problems.append(
                f"lake selections count {len(lake_sels)} != {EXPECTED_SELECTIONS_COUNT}"
            )
    except Exception as exc:
        problems.append(f"failed to load partitioned lake selections: {exc}")

    return problems


# ---------------------------------------------------------------------------
# Stage 8: Finals
# ---------------------------------------------------------------------------


def build_finals(context: StageContext) -> StageOutput:
    storage = common.preview_storage(context)
    sched_key = FOUNDATION_SCHEDULE.format(run_id=context.plan.run_id)
    schedule = read_parquet_data(context.read_artifact("foundation", sched_key))

    # Read Week 5 outcomes
    outcomes_ref = source_refs(context)["week5_outcomes"]
    w5_outcomes_data = checked_read(storage, outcomes_ref)
    w5_outcomes = pd.read_parquet(io.BytesIO(w5_outcomes_data))
    if w5_outcomes.duplicated(["season", "game_id"]).any():
        raise GateError("Week 5 outcomes duplicate a key")
    w5_by_id = w5_outcomes[w5_outcomes["season"].eq(2026)].set_index("game_id")

    finals_rows = []
    for game in schedule.itertuples(index=False):
        game_id = int(game.game_id)
        w = int(game.week)
        if w < 5:
            home_pts = int(game.home_points)
            away_pts = int(game.away_points)
            finals_ref = "source_lock_2026"
        else:
            w5_row = w5_by_id.loc[game_id]
            if not bool(w5_row["completed"]):
                raise GateError(f"game {game_id} has no certified final")
            home_pts = int(w5_row["home_points"])
            away_pts = int(w5_row["away_points"])
            finals_ref = outcomes_ref["uri"]

        finals_rows.append(
            {
                "season": 2026,
                "week": w,
                "game_id": game_id,
                "home_team": str(game.home_team),
                "away_team": str(game.away_team),
                "home_points": home_pts,
                "away_points": away_pts,
                "completed": True,
                "finals_ref": finals_ref,
            }
        )

    finals_df = pd.DataFrame.from_records(finals_rows)
    if len(finals_df) != TOTAL_2026_GAMES:
        raise GateError(f"finals count {len(finals_df)} != {TOTAL_2026_GAMES}")
    if finals_df["home_points"].isna().any() or finals_df["away_points"].isna().any():
        raise GateError("finals dataframe has null scores")

    # Read-only cross-check against Preview DB if PREVIEW_DATABASE_URL is set
    db_matches = 0
    preview_url = os.getenv("PREVIEW_DATABASE_URL")
    if not preview_url:
        raise GateError("finals cross-check requires PREVIEW_DATABASE_URL")
    if preview_url:
        import psycopg

        from cks_picks_cfb.rebuild.targets import assert_preview_database

        with psycopg.connect(preview_url) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                assert_preview_database(cur)
                game_ids = finals_df["game_id"].tolist()
                cur.execute(
                    "SELECT game_id, home_points, away_points FROM game_results WHERE game_id = ANY(%s)",
                    (game_ids,),
                )
                raw_rows = cur.fetchall()
                if (
                    len(raw_rows) != len(game_ids)
                    or len({r[0] for r in raw_rows}) != len(game_ids)
                    or any(r[1] is None or r[2] is None for r in raw_rows)
                ):
                    raise GateError(
                        "Preview finals coverage is incomplete or duplicated"
                    )
                db_rows = {int(r[0]): (int(r[1]), int(r[2])) for r in raw_rows}
                if set(db_rows) != set(game_ids):
                    raise GateError("Preview finals keys differ from locked schedule")
                for row in finals_df.itertuples(index=False):
                    gid = int(row.game_id)
                    if gid in db_rows:
                        if (row.home_points, row.away_points) != db_rows[gid]:
                            raise GateError(
                                f"game {gid} scores ({row.home_points}, {row.away_points}) "
                                f"differ from Preview DB {db_rows[gid]}"
                            )
                        db_matches += 1

    if db_matches != TOTAL_2026_GAMES:
        raise GateError("Preview finals cross-check did not cover every game")
    summary = {
        "status": "passed",
        "total_finals": len(finals_df),
        "weekly_counts": {str(w): int((finals_df["week"] == w).sum()) for w in WEEKS},
        "db_matches": db_matches,
        "finals_digest": frame_digest(finals_df),
    }

    prefix_fin = FINALS_PARQUET.format(run_id=context.plan.run_id)
    prefix_sum = FINALS_SUMMARY.format(run_id=context.plan.run_id)

    artifacts = [
        (prefix_fin, parquet_data(finals_df)),
        (prefix_sum, json_data(summary)),
    ]
    return StageOutput(artifacts=artifacts, metrics={"finals": len(finals_df)})


def verify_finals(context: StageContext) -> list[str]:
    problems: list[str] = []
    prefix_sum = FINALS_SUMMARY.format(run_id=context.plan.run_id)
    prefix_fin = FINALS_PARQUET.format(run_id=context.plan.run_id)
    try:
        summary = json.loads(context.read_artifact("finals", prefix_sum))
        finals = read_parquet_data(context.read_artifact("finals", prefix_fin))
    except Exception as exc:
        return [f"failed to read finals artifacts: {exc}"]

    if len(finals) != TOTAL_2026_GAMES:
        problems.append(f"finals count {len(finals)} != {TOTAL_2026_GAMES}")
    if frame_digest(finals) != summary["finals_digest"]:
        problems.append("finals digest mismatch")
    return problems
