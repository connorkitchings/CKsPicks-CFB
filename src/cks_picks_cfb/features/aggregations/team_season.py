"""Team-season recency-weighted aggregations."""

from __future__ import annotations

import numpy as np
import pandas as pd


def aggregate_team_season(team_game_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate team-game metrics to season-to-date with recency weighting.

    Uses weights 3, 2, 1 for the last three games (most recent highest), and 1 for
    all earlier games. Aggregates a curated list of offense/defense and drive-level
    metrics when present.

    Args:
        team_game_df: Team-game DataFrame with at least season, week, team columns and
            metric columns output by aggregate_team_game.

    Returns:
        DataFrame with one row per (season, team) containing weighted averages and
        games_played. Includes cumulative_luck_factor when present.

    Raises:
        ValueError: If required identity columns are missing.
    """
    required = ["season", "week", "team"]
    for c in required:
        if c not in team_game_df.columns:
            raise ValueError(f"aggregate_team_season requires column '{c}'")

    if team_game_df.empty:
        return pd.DataFrame()

    def _apply_weights(g: pd.DataFrame) -> pd.DataFrame:
        g = g.sort_values("week").copy()
        weights = np.ones(len(g), dtype=float)
        # Assign 4,3,2,1 to last four games (most recent highest), earlier = 1
        for i, w in enumerate([1.0, 2.0, 3.0, 4.0], start=1):
            idx = len(g) - i
            if idx >= 0:
                weights[idx] = w
        g["recency_weight"] = weights
        return g

    # Process each season/team separately to avoid groupby.apply column loss issues
    all_weighted = []
    for (season, team), group in team_game_df.groupby(["season", "team"]):
        weighted_group = _apply_weights(group)
        all_weighted.append(weighted_group)
    weighted = pd.concat(all_weighted, ignore_index=True)

    metric_cols = [
        "off_sr",
        "off_ypp",
        "off_rush_ypp",
        "off_pass_ypp",
        "off_epa_pp",
        "off_expl_rate_overall_10",
        "off_expl_rate_overall_20",
        "off_expl_rate_overall_30",
        "off_expl_rate_rush",
        "off_expl_rate_pass",
        "stuff_rate",
        "havoc_rate",
        "def_sr",
        "def_ypp",
        "def_rush_ypp",
        "def_pass_ypp",
        "def_epa_pp",
        "def_expl_rate_overall_10",
        "def_expl_rate_overall_20",
        "def_expl_rate_overall_30",
        "def_expl_rate_rush",
        "def_expl_rate_pass",
        "off_eckel_rate",
        "off_finish_pts_per_opp",
        "off_power_success_rate",
        "off_avg_line_yards",
        "off_avg_second_level_yards",
        "off_avg_open_field_yards",
        "def_power_success_rate_allowed",
        "def_avg_line_yards_allowed",
        "def_avg_second_level_yards_allowed",
        "def_avg_open_field_yards_allowed",
        "off_third_down_conversion_rate",
        "def_third_down_conversion_rate",
        # Drive-level metrics
        "off_successful_drive_rate",
        "off_busted_drive_rate",
        "off_explosive_drive_rate",
        "def_successful_drive_rate_allowed",
        "def_busted_drive_rate_allowed",
        "def_explosive_drive_rate_allowed",
        "off_points_per_drive",
        "def_points_per_drive_allowed",
        "off_avg_start_field_position",
        "def_avg_start_field_position_allowed",
        "net_field_position_delta",
        # Special teams metrics (if available)
        "off_avg_net_punt_yards",
        # Weather metrics
        "temperature",
        "precipitation",
        "wind_speed",
        # Turnover metrics
        "off_turnover_rate",
        "off_fumble_rate",
        "off_interception_rate",
        "def_turnover_rate",
        # Sack metrics
        "off_sack_rate",
        "def_sack_rate",
        # Penalty metrics
        "off_penalty_rate",
        "off_offensive_penalty_rate",
        "def_penalty_rate",
        "def_defensive_penalty_rate",
        # Fourth down metrics
        "off_fourth_down_conversion_rate",
        "off_fourth_down_attempt_rate",
        # Red zone metrics
        "off_red_zone_sr",
        "def_red_zone_sr",
        # Garbage time metrics
        "off_non_garbage_sr",
        "off_non_garbage_epa",
        "def_non_garbage_sr",
        # Fourth quarter / late game metrics
        "off_fourth_quarter_sr",
        "off_close_game_sr",
        "def_fourth_quarter_sr",
        # Big play metrics
        "off_td_rate",
        "off_40_plus_yard_rate",
        "def_td_rate_allowed",
        "def_40_plus_yard_rate_allowed",
        # Kickoff metrics
        "off_touchback_rate",
        "off_kick_return_avg_yards",
    ]
    present_metric_cols = [c for c in metric_cols if c in weighted.columns]
    special_team_prefixes = ("off_fg_", "off_avg_net_punt_yards", "off_avg_net_kick_")
    special_metric_cols = [
        c
        for c in weighted.columns
        if any(c.startswith(prefix) for prefix in special_team_prefixes)
    ]
    present_metric_cols = sorted(set(present_metric_cols + special_metric_cols))

    def _agg_group(g: pd.DataFrame) -> pd.Series:
        out: dict[str, float] = {}
        filled = g.copy()
        st_fill_cols = [
            c
            for c in present_metric_cols
            if c.startswith(("off_avg_net_punt_yards", "off_fg_", "off_avg_net_kick_"))
        ]
        if st_fill_cols:
            filled[st_fill_cols] = (
                filled[st_fill_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
            )
        # Trench warfare features (line yards, etc.)
        trench_cols = [
            c
            for c in present_metric_cols
            if "line_yards" in c or "second_level_yards" in c or "open_field_yards" in c
        ]
        if trench_cols:
            filled[trench_cols] = filled[trench_cols].fillna(0.0)

        # Clip net punt yards to a reasonable range (-10 to 65)
        if "off_avg_net_punt_yards" in filled.columns:
            filled["off_avg_net_punt_yards"] = filled["off_avg_net_punt_yards"].clip(
                -10, 65
            )

        w = filled["recency_weight"].astype(float)
        wsum = w.sum() if w.sum() > 0 else 1.0
        for col in present_metric_cols:
            vals = filled[col].astype(float)
            out[col] = float(np.nansum(vals * w) / wsum)

        # Add momentum features
        last_3 = filled.tail(3)
        for col in present_metric_cols:
            out[f"{col}_last_3"] = last_3[col].mean()

        last_2 = filled.tail(2)
        for col in present_metric_cols:
            out[f"{col}_last_2"] = last_2[col].mean()

        last_1 = filled.tail(1)
        for col in present_metric_cols:
            out[f"{col}_last_1"] = last_1[col].mean()

        out["games_played"] = float(len(g))
        if "n_off_plays" in g.columns:
            plays_vals = g["n_off_plays"].astype(float)
            out["plays_per_game"] = float((plays_vals * w).sum() / wsum)
            out["plays_per_game_last_1"] = last_1["n_off_plays"].mean()
            out["plays_per_game_last_2"] = last_2["n_off_plays"].mean()
            out["plays_per_game_last_3"] = last_3["n_off_plays"].mean()

        if "off_drives" in g.columns:
            drives_vals = g["off_drives"].astype(float)
            out["drives_per_game"] = float((drives_vals * w).sum() / wsum)
            out["drives_per_game_last_1"] = last_1["off_drives"].mean()
            out["drives_per_game_last_2"] = last_2["off_drives"].mean()
            out["drives_per_game_last_3"] = last_3["off_drives"].mean()

        if "off_drives" in g.columns:
            drives_vals = g["off_drives"].astype(float)
            scoring_rate = None
            if "off_drive_start_opponent_50_20_rate" in g.columns:
                scoring_rate = g["off_drive_start_opponent_50_20_rate"].astype(float)
            if "off_drive_start_inside_opponent_20_rate" in g.columns:
                inside_rate = g["off_drive_start_inside_opponent_20_rate"].astype(float)
                scoring_rate = (
                    scoring_rate + inside_rate
                    if scoring_rate is not None
                    else inside_rate
                )
            if scoring_rate is not None:
                scoring_opps = drives_vals * scoring_rate
                out["avg_scoring_opps_per_game"] = float(
                    (scoring_opps * w).sum() / wsum
                )
                # Momentum for scoring opps
                # We need to calculate scoring_opps per game for last_X
                # scoring_opps series
                g_scoring_opps = scoring_opps  # This is a Series aligned with g

                # We need to slice it for last_X
                # g is sorted by week.
                out["avg_scoring_opps_per_game_last_1"] = g_scoring_opps.tail(1).mean()
                out["avg_scoring_opps_per_game_last_2"] = g_scoring_opps.tail(2).mean()
                out["avg_scoring_opps_per_game_last_3"] = g_scoring_opps.tail(3).mean()
        if "luck_factor" in g.columns:
            out["cumulative_luck_factor"] = g["luck_factor"].sum()

        series = pd.Series(out)
        # Impute NaNs in momentum features with the overall mean for that feature
        for col in series.index:
            if col.endswith(("_last_1", "_last_2", "_last_3")) and pd.isna(series[col]):
                series[col] = series[
                    col.rsplit("_", 2)[0]
                ]  # Fallback to the season-long average
                if pd.isna(series[col]):
                    series[col] = 0.0
        return series

    season_agg = (
        weighted.groupby(["season", "team"], as_index=False)
        .apply(_agg_group, include_groups=False)
        .reset_index(drop=True)
    )
    return season_agg
