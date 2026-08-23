"""Iterative opponent adjustment for team metrics."""

from __future__ import annotations

import pandas as pd


def apply_iterative_opponent_adjustment(
    team_season_df: pd.DataFrame, team_game_df: pd.DataFrame, iterations: int = 6
) -> pd.DataFrame:
    """
    Apply iterative opponent adjustment and return a long-format DataFrame with all iterations.
    """
    adjusted_df = team_season_df.copy()
    iteration_results = []

    metrics_to_adjust = [
        "epa_pp",
        "sr",
        "ypp",
        "rush_ypp",
        "pass_ypp",
        "expl_rate_overall_10",
        "expl_rate_overall_20",
        "expl_rate_overall_30",
        "expl_rate_rush",
        "expl_rate_pass",
        "power_success_rate",
        "third_down_conversion_rate",
        "avg_line_yards",
        "avg_second_level_yards",
        "avg_open_field_yards",
        "successful_drive_rate",
        "busted_drive_rate",
        "explosive_drive_rate",
        "avg_net_punt_yards",
        "fg_rate_short",
        "fg_rate_mid",
        "fg_rate_long",
        "turnover_rate",
        "sack_rate",
        "fourth_down_conversion_rate",
        "red_zone_sr",
        "non_garbage_sr",
        "non_garbage_epa",
        "fourth_quarter_sr",
        "close_game_sr",
        "td_rate",
        "40_plus_yard_rate",
    ]
    defensive_allowed_metrics = {
        "power_success_rate",
        "avg_line_yards",
        "avg_second_level_yards",
        "avg_open_field_yards",
        "successful_drive_rate",
        "busted_drive_rate",
        "explosive_drive_rate",
        "avg_net_punt_yards",
        "td_rate",
        "40_plus_yard_rate",
    }

    # Initialize adj_ columns
    for metric in metrics_to_adjust:
        off_col = f"off_{metric}"
        def_col = f"def_{metric}"
        if metric in defensive_allowed_metrics:
            def_col += "_allowed"

        if off_col in adjusted_df.columns:
            adjusted_df[f"adj_{off_col}"] = adjusted_df[off_col]
        if def_col in adjusted_df.columns:
            adjusted_df[f"adj_{def_col}"] = adjusted_df[def_col]

    # Store iteration 0
    iter0_df = adjusted_df.copy()
    iter0_df["iteration"] = 0
    iteration_results.append(iter0_df)

    # Prepare game data with opponents
    team_game_weighted = team_game_df.copy()
    if "recency_weight" not in team_game_weighted.columns:
        team_game_weighted["recency_weight"] = 1.0

    games_with_opponents = team_game_weighted.merge(
        team_game_weighted[["season", "week", "game_id", "team"]].add_suffix("_opp"),
        left_on=["season", "week", "game_id"],
        right_on=["season_opp", "week_opp", "game_id_opp"],
    )
    games_with_opponents = games_with_opponents[
        games_with_opponents["team"] != games_with_opponents["team_opp"]
    ].copy()

    for i in range(1, iterations + 1):
        league_means = adjusted_df[
            [col for col in adjusted_df.columns if col.startswith("adj_")]
        ].mean()

        adj_for_merge = adjusted_df.set_index(["season", "team"])[
            [col for col in adjusted_df.columns if col.startswith("adj_")]
        ]

        merged_games = games_with_opponents.merge(
            adj_for_merge, left_on=["season", "team_opp"], right_index=True, how="left"
        )

        for metric in metrics_to_adjust:
            adj_off_col, adj_def_col = f"adj_off_{metric}", f"adj_def_{metric}"
            if metric in defensive_allowed_metrics:
                adj_def_col = f"adj_def_{metric}_allowed"

            if adj_def_col in merged_games.columns:
                league_mean_def = league_means.get(adj_def_col, 0)
                merged_games[f"opp_def_adj_for_{metric}"] = (
                    merged_games[adj_def_col] - league_mean_def
                )

            if adj_off_col in merged_games.columns:
                league_mean_off = league_means.get(adj_off_col, 0)
                merged_games[f"opp_off_adj_for_{metric}"] = (
                    merged_games[adj_off_col] - league_mean_off
                )

        for metric in metrics_to_adjust:
            raw_off_col, raw_def_col = f"off_{metric}", f"def_{metric}"
            if metric in defensive_allowed_metrics:
                raw_def_col += "_allowed"

            if (
                f"opp_def_adj_for_{metric}" in merged_games.columns
                and raw_off_col in adjusted_df.columns
            ):
                team_level_adj = merged_games.groupby(["season", "team"])[
                    f"opp_def_adj_for_{metric}"
                ].mean()
                adjusted_df = adjusted_df.merge(
                    team_level_adj.rename(f"final_opp_def_adj_{metric}"),
                    on=["season", "team"],
                    how="left",
                )
                adjusted_df[f"adj_{raw_off_col}"] = adjusted_df[
                    raw_off_col
                ] - adjusted_df[f"final_opp_def_adj_{metric}"].fillna(0)
                adjusted_df = adjusted_df.drop(columns=[f"final_opp_def_adj_{metric}"])

            if (
                f"opp_off_adj_for_{metric}" in merged_games.columns
                and raw_def_col in adjusted_df.columns
            ):
                team_level_adj = merged_games.groupby(["season", "team"])[
                    f"opp_off_adj_for_{metric}"
                ].mean()
                adjusted_df = adjusted_df.merge(
                    team_level_adj.rename(f"final_opp_off_adj_{metric}"),
                    on=["season", "team"],
                    how="left",
                )
                adjusted_df[f"adj_{raw_def_col}"] = adjusted_df[
                    raw_def_col
                ] - adjusted_df[f"final_opp_off_adj_{metric}"].fillna(0)
                adjusted_df = adjusted_df.drop(columns=[f"final_opp_off_adj_{metric}"])

        iter_df = adjusted_df.copy()
        iter_df["iteration"] = i
        iteration_results.append(iter_df)

    return pd.concat(iteration_results, ignore_index=True)
