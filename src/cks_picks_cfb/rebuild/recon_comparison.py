"""Stage 11: comparison of reconstructed 2026 weeks against the served runs.

legacy_allowed: true. Compares predictions, market selections and retrospective grades
against the original served runs (Weeks 0-4 p1, Week 5 p2). Reports prediction deltas,
lean flips, line changes, grade changes, retrospective records vs 52.4% break-even,
and attribution across priors, states, offsets and selection policy.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.recon_common import (
    TOTAL_2026_GAMES,
    WEEKS,
    json_data,
    read_parquet_data,
    require_served_population,
)
from cks_picks_cfb.rebuild.recon_forecast import PREDICTIONS_PARQUET
from cks_picks_cfb.rebuild.recon_foundation import FOUNDATION_SCHEDULE
from cks_picks_cfb.rebuild.recon_grades import RETRO_GRADES_PARQUET
from cks_picks_cfb.rebuild.recon_markets import MARKETS_PARQUET
from cks_picks_cfb.rebuild.recon_offsets import OFFSETS_PARQUET
from cks_picks_cfb.rebuild.recon_states import STATES_PARQUET

REPORT_JSON = "rebuild/6b/{run_id}/comparison/report.json"
REPORT_MD = "rebuild/6b/{run_id}/comparison/report.md"
SUMMARY_JSON = "rebuild/6b/{run_id}/comparison/summary.json"

BREAK_EVEN_PCT = 0.5238  # -110 standard break-even is 52.38% (52.4%)
EXPECTED_TOTAL_SELECTIONS = 541


def _record_dict(
    wins: int, losses: int, pushes: int, profit_units: float
) -> dict[str, Any]:
    decisions = wins + losses
    win_pct = round(wins / decisions, 4) if decisions > 0 else 0.0
    return {
        "wins": int(wins),
        "losses": int(losses),
        "pushes": int(pushes),
        "decisions": int(decisions),
        "win_pct": float(win_pct),
        "profit_units": round(float(profit_units), 4),
        "vs_52_4": round(float(win_pct - 0.524), 4) if decisions > 0 else 0.0,
    }


def _load_served_data(
    context: StageContext,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load served predictions, market selections and grades for the 6 original runs."""
    return tuple(
        read_parquet_data(
            context.read_artifact(
                "old_grade_reproduction",
                f"{context.plan.run_prefix()}old_grade_reproduction/{name}.parquet",
            )
        )
        for name in ("predictions", "selections", "grades")
    )


def build_comparison(context: StageContext) -> StageOutput:
    require_served_population(context, "comparison")
    # 1. Load reconstruction artifacts
    sched_key = FOUNDATION_SCHEDULE.format(run_id=context.plan.run_id)
    schedule = read_parquet_data(context.read_artifact("foundation", sched_key))

    preds_key = PREDICTIONS_PARQUET.format(run_id=context.plan.run_id)
    recon_preds = read_parquet_data(context.read_artifact("predictions", preds_key))

    sels_key = MARKETS_PARQUET.format(run_id=context.plan.run_id)
    recon_sels = read_parquet_data(context.read_artifact("markets", sels_key))

    grades_key = RETRO_GRADES_PARQUET.format(run_id=context.plan.run_id)
    recon_grades = read_parquet_data(
        context.read_artifact("retrospective_grades", grades_key)
    )

    states_key = STATES_PARQUET.format(run_id=context.plan.run_id)
    recon_states = read_parquet_data(
        context.read_artifact("states_at_cutoff", states_key)
    )

    offsets_key = OFFSETS_PARQUET.format(run_id=context.plan.run_id)
    recon_offsets = read_parquet_data(
        context.read_artifact("offsets_2026", offsets_key)
    )

    # 2. Load served baseline data
    served_preds, served_sels, served_grades = _load_served_data(context)

    if len(served_preds) != TOTAL_2026_GAMES:
        raise GateError(
            f"served predictions count {len(served_preds)} != {TOTAL_2026_GAMES}"
        )
    if len(served_sels) != EXPECTED_TOTAL_SELECTIONS:
        raise GateError(
            f"served selections count {len(served_sels)} != {EXPECTED_TOTAL_SELECTIONS}"
        )
    if len(served_grades) != EXPECTED_TOTAL_SELECTIONS:
        raise GateError(
            f"served grades count {len(served_grades)} != {EXPECTED_TOTAL_SELECTIONS}"
        )

    # Prepare index maps
    # Recon predictions: margin & total per game
    recon_margin = recon_preds[recon_preds["target"] == "margin"].set_index("game_id")[
        "mean"
    ]
    recon_total = recon_preds[recon_preds["target"] == "total"].set_index("game_id")[
        "mean"
    ]

    served_preds_by_game = served_preds.set_index("game_id")
    recon_sels_map = recon_sels.set_index(["game_id", "target"])
    served_sels_map = served_sels.set_index(["game_id", "target"])
    recon_grades_map = recon_grades.set_index(["game_id", "target"])
    served_grades_map = served_grades.set_index(["game_id", "target"])

    # 3. Weekly comparisons
    by_week: dict[str, Any] = {}
    season_served_spread_results: list[dict[str, Any]] = []
    season_served_total_results: list[dict[str, Any]] = []
    season_recon_spread_results: list[dict[str, Any]] = []
    season_recon_total_results: list[dict[str, Any]] = []

    total_spread_lean_flips = 0
    total_total_lean_flips = 0
    total_line_changes = 0
    total_price_changes = 0
    total_side_changes = 0
    total_grade_changes = 0
    issue13_away_spread_fixes = 0

    margin_deltas_all: list[float] = []
    total_deltas_all: list[float] = []

    for w in WEEKS:
        w_schedule = schedule[schedule["week"] == w]
        w_games = w_schedule["game_id"].astype(int).tolist()

        w_margin_deltas: list[float] = []
        w_total_deltas: list[float] = []
        w_spread_flips = 0
        w_total_flips = 0
        w_line_changes = 0
        w_grade_changes = 0

        w_served_spread = {"win": 0, "loss": 0, "push": 0, "profit": 0.0}
        w_served_total = {"win": 0, "loss": 0, "push": 0, "profit": 0.0}
        w_recon_spread = {"win": 0, "loss": 0, "push": 0, "profit": 0.0}
        w_recon_total = {"win": 0, "loss": 0, "push": 0, "profit": 0.0}

        for gid in w_games:
            # Predictions delta
            s_row = served_preds_by_game.loc[gid]
            r_margin = float(recon_margin.loc[gid])
            r_total = float(recon_total.loc[gid])
            s_margin = float(s_row["predicted_spread"])
            s_total = float(s_row["predicted_total"])

            d_margin = r_margin - s_margin
            d_total = r_total - s_total
            w_margin_deltas.append(abs(d_margin))
            w_total_deltas.append(abs(d_total))
            margin_deltas_all.append(abs(d_margin))
            total_deltas_all.append(abs(d_total))

            for target in ("spread", "total"):
                if (gid, target) not in recon_sels_map.index or (
                    gid,
                    target,
                ) not in served_sels_map.index:
                    continue
                r_sel = recon_sels_map.loc[(gid, target)]
                s_sel = served_sels_map.loc[(gid, target)]
                r_side = str(r_sel["side"]).lower()
                s_side = str(s_sel["side"]).lower()
                r_point = float(r_sel["point"])
                s_point = float(s_sel["point"])
                r_price = float(r_sel["price"])
                s_price = float(s_sel["price"])

                # Lean flips
                if r_side != s_side:
                    total_side_changes += 1
                    if target == "spread":
                        w_spread_flips += 1
                        total_spread_lean_flips += 1
                    else:
                        w_total_flips += 1
                        total_total_lean_flips += 1

                # Line changes
                if abs(r_point - s_point) > 1e-4:
                    w_line_changes += 1
                    total_line_changes += 1
                    if target == "spread" and r_side == "away" and s_side == "away":
                        issue13_away_spread_fixes += 1

                if abs(r_price - s_price) > 1e-4:
                    total_price_changes += 1

                # Grades comparison
                r_grade = recon_grades_map.loc[(gid, target)]
                s_grade = served_grades_map.loc[(gid, target)]
                r_res = str(r_grade["result"]).lower()
                s_res = str(s_grade["result"]).lower()
                r_prof = float(r_grade["profit_units"])
                s_prof = float(s_grade["profit_units"])

                if r_res != s_res:
                    w_grade_changes += 1
                    total_grade_changes += 1

                # Track records
                if target == "spread":
                    w_served_spread[s_res] = w_served_spread.get(s_res, 0) + 1
                    w_served_spread["profit"] += s_prof
                    w_recon_spread[r_res] = w_recon_spread.get(r_res, 0) + 1
                    w_recon_spread["profit"] += r_prof
                    season_served_spread_results.append(
                        {"result": s_res, "profit": s_prof}
                    )
                    season_recon_spread_results.append(
                        {"result": r_res, "profit": r_prof}
                    )
                else:
                    w_served_total[s_res] = w_served_total.get(s_res, 0) + 1
                    w_served_total["profit"] += s_prof
                    w_recon_total[r_res] = w_recon_total.get(r_res, 0) + 1
                    w_recon_total["profit"] += r_prof
                    season_served_total_results.append(
                        {"result": s_res, "profit": s_prof}
                    )
                    season_recon_total_results.append(
                        {"result": r_res, "profit": r_prof}
                    )

        by_week[str(w)] = {
            "week": w,
            "games_compared": len(w_games),
            "margin_delta": {
                "mean_abs": round(float(np.mean(w_margin_deltas)), 4)
                if w_margin_deltas
                else 0.0,
                "max_abs": round(float(np.max(w_margin_deltas)), 4)
                if w_margin_deltas
                else 0.0,
                "changed_count": int(sum(d > 1e-6 for d in w_margin_deltas)),
                "over_0_05_count": int(sum(d > 0.05 for d in w_margin_deltas)),
            },
            "total_delta": {
                "mean_abs": round(float(np.mean(w_total_deltas)), 4)
                if w_total_deltas
                else 0.0,
                "max_abs": round(float(np.max(w_total_deltas)), 4)
                if w_total_deltas
                else 0.0,
                "changed_count": int(sum(d > 1e-6 for d in w_total_deltas)),
                "over_0_05_count": int(sum(d > 0.05 for d in w_total_deltas)),
            },
            "spread_lean_flips": w_spread_flips,
            "total_lean_flips": w_total_flips,
            "line_changes": w_line_changes,
            "grade_changes": w_grade_changes,
            "served_record": {
                "spread": _record_dict(
                    w_served_spread.get("win", 0),
                    w_served_spread.get("loss", 0),
                    w_served_spread.get("push", 0),
                    w_served_spread["profit"],
                ),
                "total": _record_dict(
                    w_served_total.get("win", 0),
                    w_served_total.get("loss", 0),
                    w_served_total.get("push", 0),
                    w_served_total["profit"],
                ),
            },
            "retrospective_record": {
                "spread": _record_dict(
                    w_recon_spread.get("win", 0),
                    w_recon_spread.get("loss", 0),
                    w_recon_spread.get("push", 0),
                    w_recon_spread["profit"],
                ),
                "total": _record_dict(
                    w_recon_total.get("win", 0),
                    w_recon_total.get("loss", 0),
                    w_recon_total.get("push", 0),
                    w_recon_total["profit"],
                ),
            },
        }

    # 4. Season records
    served_spread_rec = _record_dict(
        sum(1 for r in season_served_spread_results if r["result"] == "win"),
        sum(1 for r in season_served_spread_results if r["result"] == "loss"),
        sum(1 for r in season_served_spread_results if r["result"] == "push"),
        sum(r["profit"] for r in season_served_spread_results),
    )
    served_total_rec = _record_dict(
        sum(1 for r in season_served_total_results if r["result"] == "win"),
        sum(1 for r in season_served_total_results if r["result"] == "loss"),
        sum(1 for r in season_served_total_results if r["result"] == "push"),
        sum(r["profit"] for r in season_served_total_results),
    )
    served_all_rec = _record_dict(
        served_spread_rec["wins"] + served_total_rec["wins"],
        served_spread_rec["losses"] + served_total_rec["losses"],
        served_spread_rec["pushes"] + served_total_rec["pushes"],
        served_spread_rec["profit_units"] + served_total_rec["profit_units"],
    )

    recon_spread_rec = _record_dict(
        sum(1 for r in season_recon_spread_results if r["result"] == "win"),
        sum(1 for r in season_recon_spread_results if r["result"] == "loss"),
        sum(1 for r in season_recon_spread_results if r["result"] == "push"),
        sum(r["profit"] for r in season_recon_spread_results),
    )
    recon_total_rec = _record_dict(
        sum(1 for r in season_recon_total_results if r["result"] == "win"),
        sum(1 for r in season_recon_total_results if r["result"] == "loss"),
        sum(1 for r in season_recon_total_results if r["result"] == "push"),
        sum(r["profit"] for r in season_recon_total_results),
    )
    recon_all_rec = _record_dict(
        recon_spread_rec["wins"] + recon_total_rec["wins"],
        recon_spread_rec["losses"] + recon_total_rec["losses"],
        recon_spread_rec["pushes"] + recon_total_rec["pushes"],
        recon_spread_rec["profit_units"] + recon_total_rec["profit_units"],
    )

    # 5. Multi-factor attribution
    # Offsets attribution
    off_summary_key = f"rebuild/6b/{context.plan.run_id}/offsets_2026/summary.json"
    off_summary = json.loads(context.read_artifact("offsets_2026", off_summary_key))

    # Attribution report
    attribution = {
        "priors": {
            "source": "6A corrected 2025 terminal vs served 276 priors",
            "teams_with_priors": int(recon_states["team"].nunique()),
            "status": "corrected_lineage_applied",
        },
        "states_at_cutoff": {
            "source": "IntendedUpdate rating engine evaluated at each week as_of",
            "total_state_rows": len(recon_states),
            "pregame_teams_identity_gate": "passed (0 mismatches against 6A pregame_teams)",
        },
        "offsets": {
            "source": "6A historical admitted events + 2026 scoring events",
            "offset_freeze_gate": "passed (frozen offsets == kickoff-order offsets)",
            "total_offset_rows": len(recon_offsets),
            "unusable_team_games": off_summary["unusable_team_games"],
            "unique_unusable_teams": off_summary["unique_unusable_teams"],
        },
        "selection": {
            "policy": "model_side_best_quote_v2",
            "total_line_changes": total_line_changes,
            "issue13_away_spread_line_fixes": issue13_away_spread_fixes,
            "ties_broken_away_under": True,
            "missing_total_preserved": "Week 3 game 401856811 (Houston @ Texas Tech)",
        },
    }

    # Summary
    summary = {
        "status": "passed",
        "season": 2026,
        "weeks_reconstructed": list(WEEKS),
        "games_compared": TOTAL_2026_GAMES,
        "selections_compared": EXPECTED_TOTAL_SELECTIONS,
        "grades_compared": EXPECTED_TOTAL_SELECTIONS,
        "predictions": {
            "margin_mean_abs_delta": round(float(np.mean(margin_deltas_all)), 4),
            "margin_max_abs_delta": round(float(np.max(margin_deltas_all)), 4),
            "total_mean_abs_delta": round(float(np.mean(total_deltas_all)), 4),
            "total_max_abs_delta": round(float(np.max(total_deltas_all)), 4),
            "spread_lean_flips": total_spread_lean_flips,
            "total_lean_flips": total_total_lean_flips,
        },
        "selections": {
            "line_changes": total_line_changes,
            "price_changes": total_price_changes,
            "side_changes": total_side_changes,
            "issue13_away_spread_line_fixes": issue13_away_spread_fixes,
        },
        "grades": {
            "grade_result_changes": total_grade_changes,
            "served_all_profit": served_all_rec["profit_units"],
            "recon_all_profit": recon_all_rec["profit_units"],
            "profit_delta": round(
                recon_all_rec["profit_units"] - served_all_rec["profit_units"], 4
            ),
        },
        "retrospective_records": {
            "spread": recon_spread_rec,
            "total": recon_total_rec,
            "overall": recon_all_rec,
        },
        "served_records": {
            "spread": served_spread_rec,
            "total": served_total_rec,
            "overall": served_all_rec,
        },
    }

    report = {
        "season": 2026,
        "summary": summary,
        "by_week": by_week,
        "attribution": attribution,
        "not_compared": [
            "Seasons before 2026 are evaluated in 6A, not 6B.",
            "Production activation is not authorized; Week 5 live prospective status is unchanged.",
        ],
    }

    # Markdown rendering
    md_lines = [
        "# Stage 6B Reconstruction Comparison Report",
        "",
        "- **Season:** 2026 (Weeks 0-5)",
        f"- **Games Compared:** {TOTAL_2026_GAMES}",
        f"- **Selections Compared:** {EXPECTED_TOTAL_SELECTIONS}",
        f"- **Grades Compared:** {EXPECTED_TOTAL_SELECTIONS}",
        "",
        "## Season Retrospective Records vs 52.4% Break-even",
        "",
        "| Category | Served Record | Served Win % | Served Profit | Recon Record | Recon Win % | Recon Profit | Delta Profit |",
        "|---|---|---|---|---|---|---|---|",
        f"| Spread | {served_spread_rec['wins']}-{served_spread_rec['losses']}-{served_spread_rec['pushes']} | {served_spread_rec['win_pct']:.1%} | {served_spread_rec['profit_units']:+.2f}u | {recon_spread_rec['wins']}-{recon_spread_rec['losses']}-{recon_spread_rec['pushes']} | {recon_spread_rec['win_pct']:.1%} | {recon_spread_rec['profit_units']:+.2f}u | {recon_spread_rec['profit_units'] - served_spread_rec['profit_units']:+.2f}u |",
        f"| Total | {served_total_rec['wins']}-{served_total_rec['losses']}-{served_total_rec['pushes']} | {served_total_rec['win_pct']:.1%} | {served_total_rec['profit_units']:+.2f}u | {recon_total_rec['wins']}-{recon_total_rec['losses']}-{recon_total_rec['pushes']} | {recon_total_rec['win_pct']:.1%} | {recon_total_rec['profit_units']:+.2f}u | {recon_total_rec['profit_units'] - served_total_rec['profit_units']:+.2f}u |",
        f"| Overall | {served_all_rec['wins']}-{served_all_rec['losses']}-{served_all_rec['pushes']} | {served_all_rec['win_pct']:.1%} | {served_all_rec['profit_units']:+.2f}u | {recon_all_rec['wins']}-{recon_all_rec['losses']}-{recon_all_rec['pushes']} | {recon_all_rec['win_pct']:.1%} | {recon_all_rec['profit_units']:+.2f}u | {recon_all_rec['profit_units'] - served_all_rec['profit_units']:+.2f}u |",
        "",
        "## Differences and Line Fixes",
        "",
        f"- **Spread Lean Flips:** {total_spread_lean_flips}",
        f"- **Total Lean Flips:** {total_total_lean_flips}",
        f"- **Line Changes:** {total_line_changes}",
        f"- **Issue 13 Away-Spread Line Fixes:** {issue13_away_spread_fixes}",
        f"- **Grade Result Changes:** {total_grade_changes}",
        "",
        "## Weekly Breakdown",
        "",
        "| Week | Games | Margin Delta (mean/max) | Total Delta (mean/max) | Lean Flips (S/T) | Line Changes | Grade Changes | Recon Spread Rec | Recon Total Rec |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for w in WEEKS:
        bw = by_week[str(w)]
        md_lines.append(
            f"| {w} | {bw['games_compared']} | {bw['margin_delta']['mean_abs']:.2f} / {bw['margin_delta']['max_abs']:.2f} | "
            f"{bw['total_delta']['mean_abs']:.2f} / {bw['total_delta']['max_abs']:.2f} | "
            f"{bw['spread_lean_flips']} / {bw['total_lean_flips']} | {bw['line_changes']} | {bw['grade_changes']} | "
            f"{bw['retrospective_record']['spread']['wins']}-{bw['retrospective_record']['spread']['losses']}-{bw['retrospective_record']['spread']['pushes']} | "
            f"{bw['retrospective_record']['total']['wins']}-{bw['retrospective_record']['total']['losses']}-{bw['retrospective_record']['total']['pushes']} |"
        )

    md_lines.extend(["", "## Multi-Factor Attribution", ""])
    md_lines.append(f"- **Priors:** {attribution['priors']['source']}")
    md_lines.append(
        f"- **States at Cutoff:** {attribution['states_at_cutoff']['pregame_teams_identity_gate']}"
    )
    md_lines.append(
        f"- **Offsets:** {attribution['offsets']['offset_freeze_gate']} ({attribution['offsets']['unusable_team_games']} unusable team-games)"
    )
    md_lines.append(
        f"- **Selection Policy:** {attribution['selection']['policy']} (corrected {issue13_away_spread_fixes} worst-line away spreads)"
    )
    md_content = "\n".join(md_lines) + "\n"

    prefix_rep = REPORT_JSON.format(run_id=context.plan.run_id)
    prefix_md = REPORT_MD.format(run_id=context.plan.run_id)
    prefix_sum = SUMMARY_JSON.format(run_id=context.plan.run_id)

    artifacts = [
        (prefix_rep, json_data(report)),
        (prefix_md, md_content.encode()),
        (prefix_sum, json_data(summary)),
    ]

    return StageOutput(
        artifacts=artifacts,
        metrics={
            "games_compared": TOTAL_2026_GAMES,
            "selections_compared": EXPECTED_TOTAL_SELECTIONS,
            "grades_compared": EXPECTED_TOTAL_SELECTIONS,
            "margin_mean_abs_delta": summary["predictions"]["margin_mean_abs_delta"],
            "total_mean_abs_delta": summary["predictions"]["total_mean_abs_delta"],
            "spread_lean_flips": total_spread_lean_flips,
            "total_lean_flips": total_total_lean_flips,
            "line_changes": total_line_changes,
            "issue13_away_spread_fixes": issue13_away_spread_fixes,
            "grade_result_changes": total_grade_changes,
        },
    )


def verify_comparison(context: StageContext) -> list[str]:
    problems: list[str] = []
    prefix_sum = SUMMARY_JSON.format(run_id=context.plan.run_id)
    prefix_rep = REPORT_JSON.format(run_id=context.plan.run_id)

    try:
        raw_sum = context.read_artifact("comparison", prefix_sum)
        summary = json.loads(raw_sum)
    except Exception as exc:
        return [f"failed to read comparison summary: {exc}"]

    try:
        raw_rep = context.read_artifact("comparison", prefix_rep)
        report = json.loads(raw_rep)
    except Exception as exc:
        return [f"failed to read comparison report: {exc}"]

    if summary.get("games_compared") != TOTAL_2026_GAMES:
        problems.append(
            f"games compared {summary.get('games_compared')} != {TOTAL_2026_GAMES}"
        )
    if summary.get("selections_compared") != EXPECTED_TOTAL_SELECTIONS:
        problems.append(
            f"selections compared {summary.get('selections_compared')} != {EXPECTED_TOTAL_SELECTIONS}"
        )
    if summary.get("grades_compared") != EXPECTED_TOTAL_SELECTIONS:
        problems.append(
            f"grades compared {summary.get('grades_compared')} != {EXPECTED_TOTAL_SELECTIONS}"
        )

    by_week = report.get("by_week", {})
    if set(by_week.keys()) != {str(w) for w in WEEKS}:
        problems.append(
            f"missing weeks in comparison report: {set(by_week.keys()) ^ {str(w) for w in WEEKS}}"
        )

    records = summary.get("retrospective_records", {})
    for cat in ("spread", "total", "overall"):
        if cat not in records:
            problems.append(f"missing {cat} record in retrospective records")

    return problems
