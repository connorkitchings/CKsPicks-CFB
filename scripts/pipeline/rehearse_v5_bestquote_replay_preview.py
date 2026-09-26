#!/usr/bin/env python3
"""Rehearse and verify V5 best-quote replay replacement runs on Preview.

Generates fresh, immutable V5 replay serving runs for 2026 Weeks 0-4 whose
market lines come from the permanent ``model_side_best_quote_v1`` policy,
publishes them to the Preview database, scores completed weeks (0-3), and
verifies every run against the Task 6 gates of
``docs/plans/2026-09-25/03-permanent-best-quote-line-selection.md``:

- dataset refs bind to the same frozen quote corpora the public V4/replay
  grades used (verified against the frozen V4 production run manifests);
- forecast values are identical to the source replay runs (only the market
  selection layer differs);
- every selection row matches its frozen quote, snapshot, side, and point;
- grades settle against the exact selected quote at ``-110`` default pricing;
- publishing and scoring are idempotent, and system_stats is untouched
  (all Preview weeks already carry site_week_selections rows).

Usage:
    zsh scripts/ops/with_preview_env.sh uv run python \\
        scripts/pipeline/rehearse_v5_bestquote_replay_preview.py
    zsh scripts/ops/with_preview_env.sh uv run python \\
        scripts/pipeline/rehearse_v5_bestquote_replay_preview.py --week 0
    zsh scripts/ops/with_preview_env.sh uv run python \\
        scripts/pipeline/rehearse_v5_bestquote_replay_preview.py \\
        --verify-only --week 0 --run-id <run_id>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from dotenv import load_dotenv
from omegaconf import OmegaConf

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "pipeline"))

from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.models.market_grading import (  # noqa: E402
    SELECTION_POLICY_VERSION,
    american_profit_per_unit,
)
from scripts.pipeline.generate_v5_replay_weekly_bets import (  # noqa: E402
    run_v5_replay_weekly_bets,
)

# Frozen market sources per week. Weeks 2-4 are the exact dataset refs of the
# frozen V4 production runs. Weeks 0-1 use the snapshot corpora the public
# replay runs graded against (the V4-run snapshot versions, paired with the
# quote captures registered at the same as_of instant).
WEEK_DATASETS = {
    0: {
        "as_of": "2026-08-23T18:00:00Z",
        "config": "conf/weekly_bets/v5_replay_2026.yaml",
        "betting_lines": {
            "version_id": "e3f984c4ab545d6e6ea7fc7f",
            "content_sha": "89af1e2fa2a1097a1d3e3b16d43cce5aae2993302631136fa225d3287b4866c8",
            "schema_version": "market_snapshots_v1",
            "uri": "lake/silver/dataset=market_snapshots/version=e3f984c4ab545d6e6ea7fc7f/data.parquet",
        },
        "betting_lines_quotes": {
            "version_id": "a3d08d112fdcb37e71973f0b",
            "content_sha": "bb8010a00be757dea7a6fd4958139d3b17977f05d9993f8472fe03803e67dab7",
            "schema_version": "market_quotes_v1",
            "uri": "lake/silver/dataset=market_quotes/version=a3d08d112fdcb37e71973f0b/data.parquet",
        },
    },
    1: {
        "as_of": "2026-09-03T05:00:00Z",
        "config": "conf/weekly_bets/v5_replay_2026.yaml",
        "betting_lines": {
            "version_id": "b273e83d02759628f31ad29e",
            "content_sha": "b98570f6d6ae753556d197a093e56d5b478fc6f7c39b96d0092180c5bf4dc241",
            "schema_version": "market_snapshots_v1",
            "uri": "lake/silver/dataset=market_snapshots/version=b273e83d02759628f31ad29e/data.parquet",
        },
        "betting_lines_quotes": {
            "version_id": "b2df0fd55a5a705d01f59295",
            "content_sha": "d9c0f11bfa100679a369e2bc1bec0759620cd5b17b749038ce3ae9b9c16f9ae4",
            "schema_version": "market_quotes_v1",
            "uri": "lake/silver/dataset=market_quotes/version=b2df0fd55a5a705d01f59295/data.parquet",
        },
    },
    2: {
        "as_of": "2026-09-08T19:00:00Z",
        "config": "conf/weekly_bets/v5_replay_2026.yaml",
        "betting_lines": {
            "version_id": "459c80d0f17a8ca852d0dc86",
            "content_sha": "5ab767716c19eb3dd2c5e20623cc04633fec814b8175f2d704731b219eec0071",
            "schema_version": "market_snapshots_v1",
            "uri": "lake/silver/dataset=market_snapshots/version=459c80d0f17a8ca852d0dc86/data.parquet",
        },
        "betting_lines_quotes": {
            "version_id": "ede4a9a77bceb43c2f767074",
            "content_sha": "1fdf36f65840dd7010d5f300298ec23fbe54f23c0062619d79f9e6f3c869d666",
            "schema_version": "market_quotes_v1",
            "uri": "lake/silver/dataset=market_quotes/version=ede4a9a77bceb43c2f767074/data.parquet",
        },
    },
    3: {
        "as_of": "2026-09-13T21:00:00Z",
        "config": "conf/weekly_bets/v5_replay_2026.yaml",
        "betting_lines": {
            "version_id": "692f4fcdb4771afbf3c6fafd",
            "content_sha": "8a11a28f7452db9b5637fe28c6a75edab22132029e811ceba92ba978e243fab5",
            "schema_version": "market_snapshots_v1",
            "uri": "lake/silver/dataset=market_snapshots/version=692f4fcdb4771afbf3c6fafd/data.parquet",
        },
        "betting_lines_quotes": {
            "version_id": "b018d14211fce9bf2533f1e0",
            "content_sha": "c729cedb59b0bf299ad65f60ccffa8aed6a3ea595d1a73016bbc6753f6f4e46f",
            "schema_version": "market_quotes_v1",
            "uri": "lake/silver/dataset=market_quotes/version=b018d14211fce9bf2533f1e0/data.parquet",
        },
    },
    4: {
        "as_of": "2026-09-20T19:00:00Z",
        "config": "conf/weekly_bets/v5_replay_w4_2026.yaml",
        "betting_lines": {
            "version_id": "d84b80460092f79812883104",
            "content_sha": "c38089bab27d5af1032cb2e08dea84b2eb11eceb88190760a3287bbb06d9ca43",
            "schema_version": "market_snapshots_v1",
            "uri": "lake/silver/dataset=market_snapshots/version=d84b80460092f79812883104/data.parquet",
        },
        "betting_lines_quotes": {
            "version_id": "48466f45fafe196e515cff93",
            "content_sha": "7c3bed6f2c207bca64630eff75cbafe28544f742dcc7a6134dd1f5195bcf25b3",
            "schema_version": "market_quotes_v1",
            "uri": "lake/silver/dataset=market_quotes/version=48466f45fafe196e515cff93/data.parquet",
        },
    },
}

# The currently selected replay runs whose forecasts must be reproduced
# exactly; only the market-selection layer may differ.
SOURCE_RUNS = {
    0: "2026w0-cb2252a0w0v5",
    1: "2026w1-v5replay-w0w3",
    2: "2026w2-v5replay-w0w3",
    3: "2026w3-v5replay-w0w3",
    4: "2026w4-v5replay-w4",
}

# Frozen V4 production runs: the authoritative record of which market datasets
# each week froze against (their manifests live in the shared R2 bucket).
V4_FROZEN_RUNS = {
    0: "2026w0-55de0317120d",
    1: "2026w1-b2c739321e5d",
    2: "2026w2-43b25511a100",
    3: "2026w3-68fe6a815bd6",
    4: "2026w4-da5d98761831",
}

EXPECTED_GAMES = {0: 8, 1: 43, 2: 49, 3: 57, 4: 58}
SCORED_WEEKS = (0, 1, 2, 3)


def _read_parquet(storage: Any, uri: str) -> pd.DataFrame:
    import io

    return pd.read_parquet(io.BytesIO(storage.read_bytes(uri)))


def verify_refs(week: int, storage: Any) -> None:
    """Bind WEEK_DATASETS to the frozen V4 corpora the public grades used."""
    meta = WEEK_DATASETS[week]
    v4_uri = (
        f"artifacts/production/predictions/year=2026/week={week}/"
        f"run_id={V4_FROZEN_RUNS[week]}/manifest.json"
    )
    v4_manifest = json.loads(storage.read_bytes(v4_uri))
    v4_refs = {
        str(item["entity"]): str(item["version_id"])
        for item in v4_manifest.get("input_dataset_refs", [])
    }

    snap_vid = meta["betting_lines"]["version_id"]
    assert v4_refs.get("betting_lines") == snap_vid, (
        f"Week {week}: snapshot ref {snap_vid} is not the frozen V4 corpus "
        f"({v4_refs.get('betting_lines')}); the replacement must bind to the "
        "same public grading corpus"
    )

    quote_vid = meta["betting_lines_quotes"]["version_id"]
    if "betting_lines_quotes" in v4_refs:
        assert v4_refs["betting_lines_quotes"] == quote_vid, (
            f"Week {week}: quote ref {quote_vid} differs from the frozen V4 "
            f"quote ref {v4_refs['betting_lines_quotes']}"
        )
    else:
        # Weeks 0-1: the V4 run pinned no quote dataset. The paired capture is
        # identified by full source_quote_ids coverage of the quotes parquet.
        snaps = _read_parquet(storage, meta["betting_lines"]["uri"])
        quotes = _read_parquet(storage, meta["betting_lines_quotes"]["uri"])
        cited: set[str] = set()
        for value in snaps["source_quote_ids"]:
            cited.update(json.loads(value))
        have = set(quotes["quote_id"].astype(str))
        missing = cited - have
        assert not missing, (
            f"Week {week}: quote dataset {quote_vid} does not cover the "
            f"snapshot's cited quotes ({len(missing)} missing)"
        )
        assert len(have) == len(cited), (
            f"Week {week}: quotes {len(have)} != cited {len(cited)}; the "
            "paired capture should cover exactly the cited corpus"
        )

    snaps = _read_parquet(storage, meta["betting_lines"]["uri"])
    captured_max = pd.to_datetime(snaps["market_captured_at"]).max()
    as_of = pd.Timestamp(meta["as_of"])
    assert captured_max <= as_of, (
        f"Week {week}: snapshot captures ({captured_max}) exceed the run's "
        f"as_of ({as_of}); the run must see only frozen pre-kickoff captures"
    )
    print(
        f"  refs: snapshot {snap_vid[:12]}… == V4 corpus, quotes "
        f"{quote_vid[:12]}… covered, captures ≤ as_of ✓"
    )


def _fetch_predictions(cur, run_id: str) -> dict[int, dict[str, Any]]:
    cur.execute(
        """
        SELECT game_id, predicted_spread, predicted_total,
               spread_model_version, total_model_version
        FROM predictions WHERE run_id = %s
        """,
        (run_id,),
    )
    return {
        int(r[0]): {
            "predicted_spread": r[1],
            "predicted_total": r[2],
            "spread_model_version": r[3],
            "total_model_version": r[4],
        }
        for r in cur.fetchall()
    }


def verify_forecast_equality(db_url: str, week: int, run_id: str) -> None:
    """The replacement run must reproduce the source run's forecasts exactly."""
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            new = _fetch_predictions(cur, run_id)
            source = _fetch_predictions(cur, SOURCE_RUNS[week])
    assert len(new) == EXPECTED_GAMES[week], (
        f"Week {week}: {len(new)} predictions != expected {EXPECTED_GAMES[week]}"
    )
    assert set(new) == set(source), (
        f"Week {week}: game sets differ from source run {SOURCE_RUNS[week]}"
    )
    for game_id, src in source.items():
        got = new[game_id]
        for field in ("predicted_spread", "predicted_total"):
            a, b = got[field], src[field]
            assert (a is None and b is None) or (
                a is not None and b is not None and abs(float(a) - float(b)) < 1e-9
            ), f"Week {week} game {game_id}: {field} changed ({b} -> {a})"
        assert got["spread_model_version"] == src["spread_model_version"], (
            f"Week {week} game {game_id}: spread model version changed"
        )
        assert got["total_model_version"] == src["total_model_version"], (
            f"Week {week} game {game_id}: total model version changed"
        )
    print(f"  forecasts: {len(new)} games identical to {SOURCE_RUNS[week]} ✓")


def verify_selections(db_url: str, week: int, run_id: str) -> dict[str, int]:
    """Every selection must bind to its frozen quote, snapshot, side, point."""
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass('public.prediction_market_selections') IS NOT NULL"
            )
            assert cur.fetchone()[0], (
                "prediction_market_selections is missing; apply migration "
                "0016 to Preview before rehearsing"
            )
            cur.execute(
                """
                SELECT s.target, s.side, s.point, s.price, s.edge,
                       s.snapshot_id, s.quote_id, s.policy_version,
                       q.game_id AS quote_game,
                       q.spread AS quote_spread, q.total AS quote_total,
                       p.game_id AS pred_game,
                       p.home_team_spread_line, p.total_line,
                       p.spread_lean, p.total_lean, p.market_snapshot_id
                FROM prediction_market_selections s
                LEFT JOIN market_quotes q ON q.quote_id = s.quote_id
                JOIN predictions p
                  ON p.run_id = s.run_id AND p.game_id = s.game_id
                WHERE s.run_id = %s
                """,
                (run_id,),
            )
            rows = cur.fetchall()
            cur.execute(
                """
                SELECT
                  COUNT(*) FILTER (WHERE spread_lean IS NOT NULL) AS lined_spread,
                  COUNT(*) FILTER (WHERE total_lean IS NOT NULL) AS lined_total
                FROM predictions WHERE run_id = %s
                """,
                (run_id,),
            )
            lined_spread, lined_total = cur.fetchone()

    counts = {"spread": 0, "total": 0}
    for (
        target,
        side,
        point,
        price,
        _edge,
        snapshot_id,
        quote_id,
        policy_version,
        quote_game,
        quote_spread,
        quote_total,
        pred_game,
        pred_spread_line,
        pred_total_line,
        spread_lean,
        total_lean,
        pred_snapshot_id,
    ) in rows:
        assert quote_game is not None, (
            f"{run_id} {target} selection cites quote {quote_id} absent "
            "from market_quotes"
        )
        assert quote_game == pred_game, (
            f"{run_id} selection for game {pred_game} cites quote "
            f"{quote_id} from game {quote_game}"
        )
        assert policy_version == SELECTION_POLICY_VERSION, (
            f"{run_id} selection policy {policy_version} != {SELECTION_POLICY_VERSION}"
        )
        assert snapshot_id == pred_snapshot_id, (
            f"{run_id} selection snapshot {snapshot_id} != prediction "
            f"snapshot {pred_snapshot_id}"
        )
        if target == "spread":
            assert side in ("home", "away"), f"bad spread side {side}"
            assert abs(float(point) - float(quote_spread)) < 1e-9, (
                f"spread point {point} != quote spread {quote_spread}"
            )
            assert abs(float(point) - float(pred_spread_line)) < 1e-9, (
                f"spread point {point} != prediction line {pred_spread_line}"
            )
            assert side == spread_lean, f"side {side} != lean {spread_lean}"
        else:
            assert side in ("over", "under"), f"bad total side {side}"
            assert abs(float(point) - float(quote_total)) < 1e-9, (
                f"total point {point} != quote total {quote_total}"
            )
            assert abs(float(point) - float(pred_total_line)) < 1e-9, (
                f"total point {point} != prediction line {pred_total_line}"
            )
            assert side == total_lean, f"side {side} != lean {total_lean}"
        assert price is not None, "selection price must not be null"
        counts[target] += 1

    assert counts["spread"] == lined_spread, (
        f"spread selections {counts['spread']} != lined spread predictions "
        f"{lined_spread}"
    )
    assert counts["total"] == lined_total, (
        f"total selections {counts['total']} != lined total predictions {lined_total}"
    )
    print(
        f"  selections: {counts['spread']} spread + {counts['total']} total "
        f"all bind to frozen quotes ✓"
    )
    return counts


def verify_grades(
    db_url: str,
    week: int,
    run_id: str,
    *,
    spread_threshold: float,
    total_threshold: float,
) -> dict[str, int]:
    """Grades must settle against the exact selected quote and price.

    Above-threshold lean targets must all be graded; sub-threshold targets
    (No-Bet totals) must have no grade, mirroring the public record.
    """
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pg.target, pg.side, pg.result, pg.profit_units,
                       pg.market_quote_id, pg.grading_version,
                       p.home_team_spread_line, p.total_line,
                       gr.home_points, gr.away_points,
                       s.price
                FROM prediction_grades pg
                JOIN predictions p
                  ON p.run_id = pg.run_id AND p.game_id = pg.game_id
                JOIN games g ON g.game_id = pg.game_id
                JOIN game_results gr ON gr.game_id = pg.game_id
                LEFT JOIN prediction_market_selections s
                  ON s.run_id = pg.run_id AND s.game_id = pg.game_id
                 AND s.target = pg.target
                WHERE pg.run_id = %s
                """,
                (run_id,),
            )
            rows = cur.fetchall()
            cur.execute(
                """
                SELECT
                  COUNT(*) FILTER (WHERE spread_lean IS NOT NULL
                                    AND edge_spread >= %s),
                  COUNT(*) FILTER (WHERE total_lean IS NOT NULL
                                    AND edge_total >= %s)
                FROM predictions WHERE run_id = %s
                """,
                (spread_threshold, total_threshold, run_id),
            )
            gradable_spread, gradable_total = cur.fetchone()

    tally = {"win": 0, "loss": 0, "push": 0}
    for (
        target,
        side,
        result,
        profit_units,
        market_quote_id,
        grading_version,
        spread_line,
        total_line,
        home_points,
        away_points,
        price,
    ) in rows:
        assert grading_version == SELECTION_POLICY_VERSION, (
            f"{run_id} grade version {grading_version} != best-quote policy"
        )
        assert market_quote_id is not None, (
            f"{run_id} best-quote grade lacks market_quote_id"
        )
        assert price is not None, "grade has no selection price"
        if target == "spread":
            cov = (home_points - away_points) + float(spread_line)
            expected = (
                ("push" if cov == 0 else ("win" if cov > 0 else "loss"))
                if side == "home"
                else ("push" if cov == 0 else ("loss" if cov > 0 else "win"))
            )
            line, pts = spread_line, home_points - away_points
        else:
            tot = home_points + away_points
            expected = (
                (
                    "push"
                    if tot == float(total_line)
                    else ("win" if tot > float(total_line) else "loss")
                )
                if side == "over"
                else (
                    "push"
                    if tot == float(total_line)
                    else ("loss" if tot > float(total_line) else "win")
                )
            )
            line, pts = total_line, home_points + away_points
        assert result == expected, (
            f"{run_id} {target} result {result} != recomputed {expected} "
            f"(line={line}, pts={pts}, side={side})"
        )
        expected_profit = (
            0.0
            if result == "push"
            else -1.0
            if result == "loss"
            else american_profit_per_unit(price)
        )
        # profit_units persists at NUMERIC(10,4); compare at storage precision.
        assert abs(float(profit_units) - expected_profit) < 5e-5, (
            f"{run_id} {target} profit {profit_units} != {expected_profit} "
            f"at price {price}"
        )
        tally[result] += 1
    assert tally["win"] + tally["loss"] + tally["push"] == len(rows)
    graded = {"spread": 0, "total": 0}
    for target in ("spread", "total"):
        graded[target] = sum(1 for r in rows if r[0] == target)
    assert graded["spread"] == gradable_spread, (
        f"{run_id} spread grades {graded['spread']} != gradable spreads "
        f"{gradable_spread} (lean + edge >= {spread_threshold})"
    )
    assert graded["total"] == gradable_total, (
        f"{run_id} total grades {graded['total']} != gradable totals "
        f"{gradable_total} (lean + edge >= {total_threshold})"
    )
    print(
        f"  grades: {len(rows)} rows settle at selected quotes "
        f"(W{tally['win']}-L{tally['loss']}-P{tally['push']}; sub-threshold "
        "totals ungraded by design) ✓"
    )
    return tally


def _stats_snapshot(db_url: str) -> tuple | None:
    """W-L-P counts only; updated_at always advances on recompute."""
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT spread_wins, spread_losses, spread_pushes, "
                "total_wins, total_losses, total_pushes "
                "FROM system_stats WHERE season = 2026"
            )
            return cur.fetchone()


def _row_counts(db_url: str, run_id: str) -> dict[str, int] | None:
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM predictions WHERE run_id = %s),
                  (SELECT COUNT(*) FROM prediction_market_selections
                   WHERE run_id = %s),
                  (SELECT COUNT(*) FROM prediction_grades WHERE run_id = %s),
                  (SELECT state FROM prediction_runs WHERE run_id = %s)
                """,
                (run_id, run_id, run_id, run_id),
            )
            row = cur.fetchone()
    if row is None or row[3] is None:
        return None
    p, s, g, state = row
    return {
        "predictions": int(p),
        "selections": int(s),
        "grades": int(g),
        "state": str(state),
    }


def _publish(run_id: str, week: int, config: str, db_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["CFB_RUNTIME_TARGET_RESOLVED"] = "preview"
    env["CFB_ARTIFACT_ENV"] = "preview"
    env["PYTHONPATH"] = f"{REPO_ROOT}:{REPO_ROOT / 'src'}"
    subprocess.run(
        [
            sys.executable,
            "scripts/pipeline/publish_to_db.py",
            "--year",
            "2026",
            "--week",
            str(week),
            "--from-artifact",
            "--run-id",
            run_id,
            "--config",
            config,
            "--no-update-current",
            "--state",
            "published",
        ],
        env=env,
        check=True,
    )


def _score_week(
    db_url: str,
    week: int,
    run_id: str,
    *,
    spread_threshold: float,
    total_threshold: float,
) -> None:
    """Score above-threshold targets only, mirroring the public grading basis.

    Every lined spread is graded (threshold 0.0); totals are graded only at
    edge >= the config's total threshold (1.5), matching the artifact's bet
    labels and the released replay record. Sub-threshold totals keep their
    lean and selection lineage but receive no grade.
    """
    from scripts.pipeline.score_to_db import prepare_scored, publish_scored_run

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.game_id, p.home_team_spread_line, p.total_line,
                       p.spread_lean, p.total_lean, p.edge_spread, p.edge_total,
                       p.market_snapshot_id,
                       gr.home_points, gr.away_points
                FROM predictions p
                JOIN games g ON p.game_id = g.game_id
                JOIN game_results gr ON g.game_id = gr.game_id
                WHERE p.run_id = %s
                """,
                (run_id,),
            )
            scored_rows = cur.fetchall()
            cols = [d.name for d in cur.description]
    if not scored_rows:
        raise AssertionError(f"Week {week}: no completed games to score")

    def _spread_result(r):
        if r["home_points"] is None or r["home_team_spread_line"] is None:
            return None
        if r["spread_lean"] is None:
            return None
        if float(r["edge_spread"] or 0.0) < spread_threshold:
            return None
        cov = (r["home_points"] - r["away_points"]) + r["home_team_spread_line"]
        if cov > 0:
            return "Win" if r["spread_lean"] == "home" else "Loss"
        if cov < 0:
            return "Loss" if r["spread_lean"] == "home" else "Win"
        return "Push"

    def _total_result(r):
        if r["home_points"] is None or r["total_line"] is None:
            return None
        if r["total_lean"] is None:
            return None
        if float(r["edge_total"] or 0.0) < total_threshold:
            return None
        tot = r["home_points"] + r["away_points"]
        if tot > r["total_line"]:
            return "Win" if r["total_lean"] == "over" else "Loss"
        if tot < r["total_line"]:
            return "Loss" if r["total_lean"] == "over" else "Win"
        return "Push"

    df = pd.DataFrame(scored_rows, columns=cols)
    df["Spread Bet Result"] = df.apply(_spread_result, axis=1)
    df["Total Bet Result"] = df.apply(_total_result, axis=1)
    prepared = prepare_scored(df)
    grades_count, _ = publish_scored_run(prepared, db_url, run_id=run_id, season=2026)
    print(f"  scored: {grades_count} games")


def rehearse_week(
    week: int,
    storage: Any,
    db_url: str,
    *,
    run_id: str | None = None,
    suffix: str = "",
    dry_run: bool = False,
    verify_only: bool = False,
) -> dict[str, Any]:
    meta = WEEK_DATASETS[week]
    cfg = OmegaConf.load(meta["config"])
    spread_threshold = float(cfg.spread_edge_threshold)
    total_threshold = float(cfg.total_edge_threshold)
    if run_id is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        run_id = f"2026w{week}-v5replay-bestquote-{stamp}{suffix}"

    print("\n==========================================")
    print(f"Week {week} best-quote replay run {run_id}")
    print("==========================================")

    verify_refs(week, storage)
    if verify_only:
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
        return {"week": week, "run_id": run_id, "mode": "verify-only"}

    stats_before = _stats_snapshot(db_url)
    existing = _row_counts(db_url, run_id)

    if existing is None:
        refs = [
            {
                "entity": "betting_lines",
                "year": 2026,
                "dataset": "market_snapshots",
                **meta["betting_lines"],
            },
            {
                "entity": "betting_lines_quotes",
                "year": 2026,
                "dataset": "market_quotes",
                **meta["betting_lines_quotes"],
            },
        ]
        refs_uri = f"artifacts/preview/pipeline-runs/{run_id}/dataset_refs.json"
        storage.write_bytes(json.dumps(refs).encode(), refs_uri)

        args = argparse.Namespace(
            year=2026,
            week=week,
            as_of=meta["as_of"],
            run_id=run_id,
            run_state="preview",
            dataset_refs_uri=refs_uri,
            output_csv=None,
            upload_artifact=not dry_run,
            config=meta["config"],
        )
        result = run_v5_replay_weekly_bets(args, cfg)
        print(
            f"  artifact: {result.get('state', 'uploaded')}, "
            f"games={result.get('row_count')}"
        )
        if dry_run:
            return {"week": week, "run_id": run_id, "mode": "dry-run"}

        _publish(run_id, week, meta["config"], db_url)
        print("  published to Preview Neon (current_week untouched)")
    else:
        if existing["state"] in {"preview", "published", "frozen", "scored"}:
            print(
                f"  run already exists (state={existing['state']}); resuming "
                "verification without regeneration"
            )
        else:
            raise AssertionError(
                f"Existing run {run_id} is in unexpected state {existing['state']}"
            )

    if week in SCORED_WEEKS:
        _score_week(
            db_url,
            week,
            run_id,
            spread_threshold=spread_threshold,
            total_threshold=total_threshold,
        )

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

    stats_after = _stats_snapshot(db_url)
    assert stats_before == stats_after, (
        f"Week {week}: system_stats drifted during an unselected rehearsal "
        f"({stats_before} -> {stats_after})"
    )
    print("  system_stats unchanged ✓")

    # Idempotency within legal bounds: frozen/scored runs are immutable to
    # re-publish by design, so a scored week repeats only the score call
    # (already_scored path must not drift rows); a still-published week
    # additionally repeats the publish call.
    before_counts = _row_counts(db_url, run_id)
    if week not in SCORED_WEEKS and before_counts["state"] == "published":
        _publish(run_id, week, meta["config"], db_url)
    if week in SCORED_WEEKS:
        _score_week(
            db_url,
            week,
            run_id,
            spread_threshold=spread_threshold,
            total_threshold=total_threshold,
        )
    after_counts = _row_counts(db_url, run_id)
    assert before_counts == after_counts, (
        f"Week {week}: repeat publish/score drifted rows "
        f"({before_counts} -> {after_counts})"
    )
    print(f"  idempotent repeat: {after_counts} ✓")

    return {"week": week, "run_id": run_id, "mode": "full", **after_counts}


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--week", type=int, choices=range(5), help="Single week to rehearse"
    )
    parser.add_argument("--dry-run", action="store_true", help="Generate only")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify an existing run (requires --run-id)",
    )
    parser.add_argument("--run-id", help="Explicit run ID (verify-only)")
    parser.add_argument(
        "--suffix",
        default="",
        help="Run-ID suffix for a fresh rehearsal batch (e.g. -r2)",
    )
    args = parser.parse_args()

    if args.verify_only and not args.run_id:
        raise SystemExit("--verify-only requires --run-id")

    pipeline_db_url = os.getenv("PREVIEW_DATABASE_URL")
    if not pipeline_db_url:
        raise SystemExit("PREVIEW_DATABASE_URL is not set")

    storage = get_storage(environment="preview")
    weeks = [args.week] if args.week is not None else list(range(5))

    summary = []
    for w in weeks:
        summary.append(
            rehearse_week(
                w,
                storage,
                pipeline_db_url,
                run_id=args.run_id if args.verify_only else None,
                suffix=args.suffix,
                dry_run=args.dry_run,
                verify_only=args.verify_only,
            )
        )
    print("\n=========== REHEARSAL SUMMARY ===========")
    for item in summary:
        print(item)


if __name__ == "__main__":
    main()
