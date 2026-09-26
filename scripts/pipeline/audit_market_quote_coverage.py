#!/usr/bin/env python3
"""
Read-only coverage audit for market quote selection across all stored prediction runs.

Inspects prediction_runs, predictions, market_snapshots, and market_quotes in Neon
to account for every prediction target:
  - Eligible selections (spread and total)
  - Missing-line reasons (missing_canonical_line, no_quotes, post_kickoff, missing_side_price, etc.)
  - Compares strict explicit price vs standard default (-110) price policy.

Does NOT mutate any data in R2 or Neon.

Usage:
    PYTHONPATH=src uv run python scripts/pipeline/audit_market_quote_coverage.py
    PYTHONPATH=src uv run python scripts/pipeline/audit_market_quote_coverage.py --season 2026
    PYTHONPATH=src uv run python scripts/pipeline/audit_market_quote_coverage.py --allow-default-price
"""

from __future__ import annotations

import argparse
import os
from typing import Any

import pandas as pd
import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.models.market_grading import (
    audit_quote_coverage,
)


def get_db_url(env_choice: str | None = None) -> str:
    load_dotenv()
    if env_choice == "preview":
        url = os.getenv("PREVIEW_DATABASE_URL")
    elif env_choice == "production":
        url = os.getenv("DATABASE_URL")
    else:
        url = os.getenv("PREVIEW_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise ValueError(
            "No database URL found in environment (DATABASE_URL / PREVIEW_DATABASE_URL)"
        )
    return url


def run_audit(
    *,
    db_url: str,
    season: int | None = None,
    week: int | None = None,
    run_id: str | None = None,
    allow_default_price: bool = False,
) -> pd.DataFrame:
    """Run read-only audit across stored runs and return a detailed report DataFrame."""
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # 1. Fetch runs
            query = """
                SELECT run_id, season, week, state, evidence_class, model_id
                FROM prediction_runs
                WHERE 1=1
            """
            params: list[Any] = []
            if season is not None:
                query += " AND season = %s"
                params.append(season)
            if week is not None:
                query += " AND week = %s"
                params.append(week)
            if run_id is not None:
                query += " AND run_id = %s"
                params.append(run_id)
            query += " ORDER BY season, week, created_at"

            cur.execute(query, params)
            runs = cur.fetchall()

            audit_rows: list[dict[str, Any]] = []

            for r in runs:
                r_id, r_season, r_week, r_state, r_ev_class, r_model_id = r

                # Fetch predictions and kickoff times
                cur.execute(
                    """
                    SELECT p.game_id, p.predicted_spread, p.predicted_total,
                           p.home_team_spread_line, p.total_line, p.market_snapshot_id,
                           g.start_date, g.home_team, g.away_team
                    FROM predictions p
                    JOIN games g ON g.game_id = p.game_id
                    WHERE p.run_id = %s
                    ORDER BY g.start_date, p.game_id
                    """,
                    (r_id,),
                )
                predictions = cur.fetchall()

                for pred in predictions:
                    (
                        game_id,
                        pred_spread,
                        pred_total,
                        home_spread,
                        total_line,
                        snap_id,
                        start_date,
                        home_team,
                        away_team,
                    ) = pred

                    # Fetch linked quotes for this snapshot if snapshot_id exists
                    quote_candidates: list[dict[str, Any]] = []
                    if snap_id:
                        cur.execute(
                            """
                            SELECT mq.quote_id, mq.game_id, mq.captured_at, mq.spread, mq.total,
                                   mq.home_spread_price, mq.away_spread_price, mq.over_price, mq.under_price,
                                   msq.snapshot_id, msq.target, mq.provider
                            FROM market_snapshot_quotes msq
                            JOIN market_quotes mq ON mq.quote_id = msq.quote_id
                            WHERE msq.snapshot_id = %s
                            """,
                            (snap_id,),
                        )
                        for q in cur.fetchall():
                            h_price = (
                                q[5]
                                if q[5] is not None or not allow_default_price
                                else -110.0
                            )
                            a_price = (
                                q[6]
                                if q[6] is not None or not allow_default_price
                                else -110.0
                            )
                            o_price = (
                                q[7]
                                if q[7] is not None or not allow_default_price
                                else -110.0
                            )
                            u_price = (
                                q[8]
                                if q[8] is not None or not allow_default_price
                                else -110.0
                            )

                            quote_candidates.append(
                                {
                                    "quote_id": q[0],
                                    "game_id": q[1],
                                    "captured_at": q[2],
                                    "point": q[3] if q[10] == "spread" else q[4],
                                    "home_spread_price": h_price,
                                    "away_spread_price": a_price,
                                    "over_price": o_price,
                                    "under_price": u_price,
                                    "snapshot_id": q[9],
                                    "target": q[10],
                                    "provider": q[11],
                                }
                            )

                    spread_candidates = [
                        q for q in quote_candidates if q.get("target") == "spread"
                    ]
                    total_candidates = [
                        q for q in quote_candidates if q.get("target") == "total"
                    ]

                    # Audit Spread
                    spread_audit = audit_quote_coverage(
                        run_id=r_id,
                        game_id=game_id,
                        target="spread",
                        prediction=pred_spread,
                        canonical_snapshot_id=snap_id or "",
                        canonical_line=home_spread,
                        kickoff_utc=start_date,
                        quote_candidates=spread_candidates,
                    )

                    # Audit Total
                    total_audit = audit_quote_coverage(
                        run_id=r_id,
                        game_id=game_id,
                        target="total",
                        prediction=pred_total,
                        canonical_snapshot_id=snap_id or "",
                        canonical_line=total_line,
                        kickoff_utc=start_date,
                        quote_candidates=total_candidates,
                    )

                    audit_rows.append(
                        {
                            "season": r_season,
                            "week": r_week,
                            "run_id": r_id,
                            "game_id": game_id,
                            "matchup": f"{away_team} @ {home_team}",
                            "target": "spread",
                            "has_canonical": home_spread is not None,
                            "canonical_line": home_spread,
                            "eligible": spread_audit["eligible"],
                            "selected_quote_id": spread_audit["selected_quote_id"],
                            "selected_point": spread_audit["selected_point"],
                            "no_line_reason": spread_audit["no_line_reason"],
                            "candidate_count": spread_audit["candidate_count"],
                            "eligible_count": spread_audit["eligible_count"],
                        }
                    )
                    audit_rows.append(
                        {
                            "season": r_season,
                            "week": r_week,
                            "run_id": r_id,
                            "game_id": game_id,
                            "matchup": f"{away_team} @ {home_team}",
                            "target": "total",
                            "has_canonical": total_line is not None,
                            "canonical_line": total_line,
                            "eligible": total_audit["eligible"],
                            "selected_quote_id": total_audit["selected_quote_id"],
                            "selected_point": total_audit["selected_point"],
                            "no_line_reason": total_audit["no_line_reason"],
                            "candidate_count": total_audit["candidate_count"],
                            "eligible_count": total_audit["eligible_count"],
                        }
                    )

            return pd.DataFrame(audit_rows)


def print_summary(df: pd.DataFrame, allow_default_price: bool):
    print("=" * 80)
    mode_str = (
        "STANDARD (-110 DEFAULT FOR UNPRICED CFBD LINES)"
        if allow_default_price
        else "STRICT (REJECT UNPRICED)"
    )
    print(f"MARKET QUOTE COVERAGE AUDIT REPORT [Mode: {mode_str}]")
    print("=" * 80)

    if df.empty:
        print("No prediction rows found matching criteria.")
        return

    total_targets = len(df)
    spread_targets = len(df[df["target"] == "spread"])
    total_total_targets = len(df[df["target"] == "total"])

    eligible = df[df["eligible"]]
    ineligible = df[~df["eligible"]]

    print(
        f"Total Prediction Targets: {total_targets} ({spread_targets} spread, {total_total_targets} total)"
    )
    print(
        f"Eligible for Best-Quote:  {len(eligible)} ({len(eligible) / total_targets * 100:.1f}%)"
    )
    print(
        f"Ineligible (No Quote):    {len(ineligible)} ({len(ineligible) / total_targets * 100:.1f}%)"
    )
    print("-" * 80)

    print("Ineligible Reasons Breakdown:")
    for reason, count in ineligible["no_line_reason"].value_counts().items():
        print(
            f"  - {reason:<25}: {count} targets ({count / len(ineligible) * 100:.1f}%)"
        )

    print("-" * 80)
    print("Per-Run Summary:")
    print(
        f"{'Run ID':<28} {'Season':<6} {'Wk':<3} {'Target':<6} {'Total':<6} {'Eligible':<8} {'Top Reason'}"
    )
    for (r_id, r_season, r_week, target), grp in df.groupby(
        ["run_id", "season", "week", "target"]
    ):
        t_count = len(grp)
        e_count = grp["eligible"].sum()
        reasons = grp[~grp["eligible"]]["no_line_reason"].value_counts()
        top_reason = reasons.index[0] if not reasons.empty else "none (100% eligible)"
        print(
            f"{r_id:<28} {r_season:<6} {r_week:<3} {target:<6} {t_count:<6} {e_count:<8} {top_reason}"
        )
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Audit market quote eligibility across prediction runs."
    )
    parser.add_argument("--season", type=int, help="Filter by season (e.g. 2025, 2026)")
    parser.add_argument("--week", type=int, help="Filter by week")
    parser.add_argument("--run-id", type=str, help="Filter by specific run_id")
    parser.add_argument(
        "--env",
        choices=["preview", "production"],
        default="preview",
        help="Target database environment",
    )
    parser.add_argument(
        "--allow-default-price",
        action="store_true",
        help="Treat unpriced quotes (CFBD standard lines) as standard -110 American vig rather than rejecting them.",
    )
    args = parser.parse_args()

    db_url = get_db_url(args.env)
    df = run_audit(
        db_url=db_url,
        season=args.season,
        week=args.week,
        run_id=args.run_id,
        allow_default_price=args.allow_default_price,
    )
    print_summary(df, allow_default_price=args.allow_default_price)


if __name__ == "__main__":
    main()
