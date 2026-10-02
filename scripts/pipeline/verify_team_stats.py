#!/usr/bin/env python3
"""Compare published ``team_season_stats`` with CFBD advanced season stats.

Read-only diagnostic. For ``--as-of-week N`` (N >= 2) it fetches CFBD
``/stats/season/advanced`` (garbage time excluded, through provider week N-1,
which is the same cutoff as our snapshot because our week 0 shares provider
week 1 with week 1) and reports the Spearman rank correlation per comparable
metric, plus the teams that disagree most. Definitions differ (CFBD counts FCS
games and applies its own garbage-time rule), so this is a sanity gate, not an
equality test: the key metrics must correlate at ``--min-rho`` (default 0.85).

    PYTHONPATH=src:. uv run python scripts/pipeline/verify_team_stats.py \\
        --season 2026 --as-of-week 5 --environment preview
"""

from __future__ import annotations

import argparse
import os
import sys

import cfbd
import pandas as pd
import psycopg
from dotenv import load_dotenv

URL_ENV = {"preview": "PREVIEW_DATABASE_URL", "production": "DATABASE_URL"}

#: (label, our metric or "overall_epa", CFBD side attribute, gating?)
COMPARISONS = (
    ("EPA/play", "overall_epa", "ppa", True),
    ("success rate", "success_rate", "successRate", True),
    ("explosiveness", "explosive_rate", "explosiveness", False),
    ("points per scoring opp", "pts_per_scoring_opp", "pointsPerOpportunity", False),
)


def our_frame(rows: list[tuple]) -> pd.DataFrame:
    """Pivot (team, role, metric, value, n) rows to one row per team and role."""
    df = pd.DataFrame(rows, columns=["team", "role", "metric", "value", "n"])
    wide = df.pivot_table(
        index=["team", "role"], columns="metric", values="value", aggfunc="first"
    )
    counts = df.pivot_table(
        index=["team", "role"], columns="metric", values="n", aggfunc="first"
    )
    wide["plays"] = counts["success_rate"]
    if "ppa_per_play" in wide.columns:
        wide["overall_epa"] = wide["ppa_per_play"]
    else:  # snapshots published before ppa_per_play: blend pass and rush PPA
        pass_n = counts["epa_pass"].fillna(0)
        rush_n = counts["epa_rush"].fillna(0)
        total = (pass_n + rush_n).where(lambda s: s > 0)
        wide["overall_epa"] = (
            wide["epa_pass"].fillna(0) * pass_n + wide["epa_rush"].fillna(0) * rush_n
        ) / total
    return wide.reset_index()


def cfbd_frame(stats: list) -> pd.DataFrame:
    rows = []
    for stat in stats:
        data = stat.to_dict()
        for role in ("offense", "defense"):
            side = data.get(role) or {}
            rows.append({"team": data["team"], "role": role, **side})
    return pd.DataFrame(rows)


def compare(
    ours: pd.DataFrame, theirs: pd.DataFrame, *, like_for_like: bool = False
) -> list[dict]:
    """Spearman per role and metric.

    CFBD counts FCS opponents and we do not, so ``like_for_like`` keeps only
    teams whose CFBD play count is within 5% of ours (no hidden FCS game).
    """
    merged = ours.merge(theirs, on=["team", "role"], suffixes=("", "_cfbd"))
    if like_for_like and {"plays", "plays_cfbd"} <= set(merged.columns):
        close = (merged["plays"] - merged["plays_cfbd"]).abs() <= 0.05 * merged[
            "plays_cfbd"
        ]
        merged = merged[close]
    results = []
    for role in ("offense", "defense"):
        part = merged[merged["role"] == role]
        for label, mine, cfbd_key, gate in COMPARISONS:
            if mine not in part.columns or cfbd_key not in part.columns:
                continue
            pair = part[[mine, cfbd_key, "team"]].dropna()
            if len(pair) < 10:
                continue
            rho = pair[mine].corr(pair[cfbd_key], method="spearman")
            ranks = pd.DataFrame(
                {
                    "team": pair["team"],
                    "ours": pair[mine].rank(),
                    "cfbd": pair[cfbd_key].rank(),
                }
            )
            ranks["gap"] = (ranks["ours"] - ranks["cfbd"]).abs()
            results.append(
                {
                    "role": role,
                    "metric": label,
                    "teams": int(len(pair)),
                    "rho": float(rho),
                    "gating": gate,
                    "outliers": ranks.nlargest(3, "gap")[
                        ["team", "ours", "cfbd"]
                    ].to_dict("records"),
                }
            )
    return results


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--as-of-week", type=int, required=True)
    parser.add_argument("--environment", choices=sorted(URL_ENV), required=True)
    parser.add_argument("--min-rho", type=float, default=0.85)
    args = parser.parse_args()
    if args.as_of_week < 2:
        parser.error("--as-of-week must be >= 2 (week 1 shares provider week 1)")
    url = os.getenv(URL_ENV[args.environment])
    key = os.getenv("CFBD_API_KEY")
    if not url or not key:
        print(f"Set {URL_ENV[args.environment]} and CFBD_API_KEY", file=sys.stderr)
        return 2

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(
            "SELECT team, role, metric, value, n FROM team_season_stats "
            "WHERE season = %s AND as_of_week = %s",
            (args.season, args.as_of_week),
        )
        rows = cur.fetchall()
    if not rows:
        print("No published rows for that season/week.", file=sys.stderr)
        return 3

    stats = cfbd.StatsApi(
        cfbd.ApiClient(cfbd.Configuration(access_token=key))
    ).get_advanced_season_stats(
        year=args.season, exclude_garbage_time=True, end_week=args.as_of_week - 1
    )
    ours, theirs = our_frame(rows), cfbd_frame(stats)
    print("All teams (informational: CFBD includes FCS games we exclude):")
    for res in compare(ours, theirs):
        print(
            f"  {res['role']:<8} {res['metric']:<24} rho={res['rho']:.3f} n={res['teams']}"
        )
    print("Like-for-like teams (CFBD plays within 5% of ours), gated:")
    results = compare(ours, theirs, like_for_like=True)
    failed = False
    for res in results:
        gate = ""
        if res["gating"]:
            ok = res["rho"] >= args.min_rho
            failed |= not ok
            gate = f"  [{'ok' if ok else 'BELOW GATE'} >= {args.min_rho}]"
        print(
            f"{res['role']:<8} {res['metric']:<24} rho={res['rho']:.3f} "
            f"n={res['teams']}{gate}"
        )
        for o in res["outliers"]:
            print(
                f"    largest rank gap: {o['team']} ours={o['ours']:.0f} cfbd={o['cfbd']:.0f}"
            )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
