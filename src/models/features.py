"""Shared helpers for building features and merged datasets for modeling."""

from __future__ import annotations

import pandas as pd

from src.config import get_data_root
from src.utils.local_storage import LocalStorage

STYLE_METRICS: dict[str, str] = {
    "plays_per_game": "tempo",
    "drives_per_game": "drives",
    "avg_scoring_opps_per_game": "scoring_opps",
}

FEATURE_PACK_CHOICES = [
    "offense",
    "defense",
    "drive",
    "pace",
    "special_teams",
    "special_teams_high_risk",
    "context",
    "matchup",
    "other",
]


def prepare_team_features(team_season_adj_df: pd.DataFrame) -> pd.DataFrame:
    """Build one-row-per-team features combining adjusted offense/defense and extras.

    Args:
        team_season_adj_df: Season aggregates with off_/def_ and adj_* columns when available.

    Returns:
        DataFrame with season, team, games_played and consolidated metrics to be joined
        to games for home/away features.
    """
    base_cols = ["season", "team", "games_played"]

    off_metric_cols = [
        c
        for c in team_season_adj_df.columns
        if c.startswith("adj_off_") or c.startswith("off_")
    ]
    def_metric_cols = [
        c
        for c in team_season_adj_df.columns
        if c.startswith("adj_def_") or c.startswith("def_")
    ]

    off_df = team_season_adj_df[base_cols + off_metric_cols].copy()
    if off_metric_cols:
        off_df = off_df.dropna(subset=off_metric_cols, how="all")

    def_df = team_season_adj_df[base_cols + def_metric_cols].copy()
    if def_metric_cols:
        def_df = def_df.dropna(subset=def_metric_cols, how="all")

    combined = off_df.merge(
        def_df, on=["season", "team"], how="outer", suffixes=("", "_defside")
    )

    if "games_played_x" in combined.columns or "games_played_y" in combined.columns:
        combined["games_played"] = combined[
            [c for c in ["games_played_x", "games_played_y"] if c in combined.columns]
        ].max(axis=1, skipna=True)
        combined = combined.drop(
            columns=[
                c for c in ["games_played_x", "games_played_y"] if c in combined.columns
            ]
        )

    # Calculate Percentile Ranks for Key Metrics
    # We group by season to rank teams relative to their peers in that year.
    rank_metrics = [
        "adj_off_epa_pp",
        "adj_def_epa_pp",
        "adj_off_sr",
        "adj_def_sr",
        "adj_off_expl_rate_overall_20",
        "adj_def_expl_rate_overall_20",
        "off_epa_pp",
        "def_epa_pp",
    ]

    for metric in rank_metrics:
        if metric in combined.columns:
            # Rank 0.0 to 1.0 (1.0 is best).
            # For Offense: Higher is better.
            # For Defense: Lower is better (usually negative EPA).
            # Wait, EPA/SR are "higher is better" for offense.
            # For Defense, "lower allowed" is better.
            # But usually we want "Rank 1.0" to mean "Best Team".
            # So for Offense: pct=True (higher value -> higher rank)
            # For Defense: pct=True, ascending=False?
            # Let's standardize: 1.0 = Best, 0.0 = Worst.

            rank_col = f"{metric}_rank"

            if "def_" in metric:
                # Defense: Lower value (more negative) is better.
                # So we rank ascending=False (Lower value gets higher rank?)
                # No, rank(ascending=True) gives low values low ranks.
                # We want low value (good defense) to have HIGH rank (1.0).
                # So we rank ascending=False.
                combined[rank_col] = combined.groupby("season")[metric].rank(
                    pct=True, ascending=False
                )
            else:
                # Offense: Higher value is better.
                # We want high value to have HIGH rank (1.0).
                combined[rank_col] = combined.groupby("season")[metric].rank(
                    pct=True, ascending=True
                )

    # Include pace and opportunity metrics if present (excluding timing metrics like sec_per_play)
    pace_cols = [
        "plays_per_game",
        "drives_per_game",
        "avg_scoring_opps_per_game",
    ]
    present_pace = [c for c in pace_cols if c in team_season_adj_df.columns]
    if present_pace:
        pace_df = (
            team_season_adj_df[["season", "team"] + present_pace].drop_duplicates(
                subset=["season", "team"]
            )  # safety
        )
        combined = combined.merge(pace_df, on=["season", "team"], how="left")

    return combined


def build_feature_list(df: pd.DataFrame) -> list[str]:
    """Construct the list of modeling features present for both home and away.

    Args:
        df: Merged games+features DataFrame with home_/away_ prefixes.

    Returns:
        List of column names to use as model inputs.
    """
    adjusted_metrics = [
        "epa_pp",
        "sr",
        "ypp",
        "expl_rate_overall_10",
        "expl_rate_overall_20",
        "expl_rate_overall_30",
        "expl_rate_rush",
        "expl_rate_pass",
    ]
    features: list[str] = []
    for side in ["home", "away"]:
        for prefix in ["adj_off_", "adj_def_", "off_", "def_"]:
            for metric in adjusted_metrics:
                col = f"{side}_{prefix}{metric}"
                if col in df.columns:
                    features.append(col)

        # Add Ranks
        for metric in [
            "adj_off_epa_pp",
            "adj_def_epa_pp",
            "adj_off_sr",
            "adj_def_sr",
            "adj_off_expl_rate_overall_20",
            "adj_def_expl_rate_overall_20",
            "off_epa_pp",
            "def_epa_pp",
        ]:
            col = f"{side}_{metric}_rank"
            if col in df.columns:
                features.append(col)

        for extra in [
            "off_eckel_rate",
            "off_finish_pts_per_opp",
            "stuff_rate",
            "havoc_rate",
            "off_points_per_drive",
            "off_avg_start_field_position",
            "net_field_position_delta",
        ]:
            col = f"{side}_{extra}"
            if col in df.columns:
                features.append(col)
        # Pace/opportunity features (exclude sec_per_play as requested)
        for pace in [
            "plays_per_game",
            "drives_per_game",
            "avg_scoring_opps_per_game",
        ]:
            col = f"{side}_{pace}"
            if col in df.columns:
                features.append(col)
        # Defensive per-drive/state metrics scoped to the opponent
        for defensive_extra in [
            "def_points_per_drive_allowed",
            "def_avg_start_field_position_allowed",
        ]:
            col = f"{side}_{defensive_extra}"
            if col in df.columns:
                features.append(col)

    # Global game context features
    global_context = [
        "neutral_site",
        "same_conference",
    ]
    style_context = []
    for metric_label in STYLE_METRICS.values():
        style_context.extend(
            [
                f"{metric_label}_contrast",
                f"{metric_label}_total",
                f"{metric_label}_ratio",
            ]
        )

    for global_feat in [*global_context, *style_context]:
        if global_feat in df.columns:
            features.append(global_feat)

    return features


def build_differential_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    From a merged dataframe with home_ and away_ prefixes, create new
    differential/matchup features.
    """
    # Define which stats are zero-centered (use subtraction) vs. positive (use ratio)
    zero_centered_metrics = ["epa_pp"]
    positive_metrics = [
        "sr",
        "ypp",
        "expl_rate_overall_10",
        "expl_rate_overall_20",
        "expl_rate_overall_30",
        "expl_rate_rush",
        "expl_rate_pass",
        "eckel_rate",
        "finish_pts_per_opp",
        "stuff_rate",
        "havoc_rate",
        "plays_per_game",
        "drives_per_game",
        "avg_scoring_opps_per_game",
    ]

    base_metrics = zero_centered_metrics + positive_metrics

    new_df = df.copy()

    for metric in base_metrics:
        # Define the four columns for the matchup
        home_off_col = f"home_adj_off_{metric}"
        away_def_col = f"away_adj_def_{metric}"
        away_off_col = f"away_adj_off_{metric}"
        home_def_col = f"home_adj_def_{metric}"

        # Check if all necessary columns exist
        required_cols = [home_off_col, away_def_col, away_off_col, home_def_col]
        if not all(col in new_df.columns for col in required_cols):
            continue

        # Define new differential column names
        matchup_home_off_col = f"matchup_home_off_vs_away_def_{metric}"
        matchup_away_off_col = f"matchup_away_off_vs_home_def_{metric}"

        if metric in zero_centered_metrics:
            # Use subtraction for zero-centered stats
            new_df[matchup_home_off_col] = new_df[home_off_col] - new_df[away_def_col]
            new_df[matchup_away_off_col] = new_df[away_off_col] - new_df[home_def_col]
        elif metric in positive_metrics:
            # Use safe ratio for positive-only stats
            # Adding a small epsilon to avoid division by zero
            epsilon = 1e-6
            new_df[matchup_home_off_col] = new_df[home_off_col] / (
                new_df[away_def_col] + epsilon
            )
            new_df[matchup_away_off_col] = new_df[away_off_col] / (
                new_df[home_def_col] + epsilon
            )

    # --- Mismatch / Rank Diff Features ---
    # Calculate rank differences (Offense Rank - Defense Rank)
    # Since 1.0 is Best and 0.0 = Worst for both Off/Def (as calculated above):
    # Diff > 0 means Offense is better ranked than Defense.
    # Diff < 0 means Defense is better ranked than Offense.

    # Map Offense metric to corresponding Defense metric for matchup
    # e.g. adj_off_epa_pp vs adj_def_epa_pp
    metric_pairs = {
        "adj_off_epa_pp": "adj_def_epa_pp",
        "adj_off_sr": "adj_def_sr",
        "adj_off_expl_rate_overall_20": "adj_def_expl_rate_overall_20",
    }

    for off_metric, def_metric in metric_pairs.items():
        # Home Off vs Away Def
        home_off_rank_col = f"home_{off_metric}_rank"
        away_def_rank_col = f"away_{def_metric}_rank"

        if home_off_rank_col in new_df.columns and away_def_rank_col in new_df.columns:
            diff_col = (
                f"matchup_home_off_rank_diff_{off_metric.replace('adj_off_', '')}"
            )
            new_df[diff_col] = new_df[home_off_rank_col] - new_df[away_def_rank_col]

            # Mismatch Flag: Offense Top 25% vs Defense Bottom 25%
            # Offense Rank > 0.75 AND Defense Rank < 0.25
            mismatch_col = (
                f"mismatch_home_advantage_{off_metric.replace('adj_off_', '')}"
            )
            new_df[mismatch_col] = (
                (new_df[home_off_rank_col] > 0.75) & (new_df[away_def_rank_col] < 0.25)
            ).astype(int)

        # Away Off vs Home Def
        away_off_rank_col = f"away_{off_metric}_rank"
        home_def_rank_col = f"home_{def_metric}_rank"

        if away_off_rank_col in new_df.columns and home_def_rank_col in new_df.columns:
            diff_col = (
                f"matchup_away_off_rank_diff_{off_metric.replace('adj_off_', '')}"
            )
            new_df[diff_col] = new_df[away_off_rank_col] - new_df[home_def_rank_col]

            mismatch_col = (
                f"mismatch_away_advantage_{off_metric.replace('adj_off_', '')}"
            )
            new_df[mismatch_col] = (
                (new_df[away_off_rank_col] > 0.75) & (new_df[home_def_rank_col] < 0.25)
            ).astype(int)

    return new_df


def build_differential_feature_list(df: pd.DataFrame) -> list[str]:
    """
    Construct the list of modeling features after differential transformation.
    """
    features = [col for col in df.columns if col.startswith("matchup_")]

    # Add global game context features
    for global_feat in ["neutral_site", "same_conference"]:
        if global_feat in df.columns:
            features.append(global_feat)

    return features


def _categorize_feature_name(feature_name: str) -> str:
    if feature_name.startswith("matchup_") or feature_name.startswith("mismatch_"):
        return "matchup"
    if "_rank" in feature_name:
        return "matchup"  # Treat ranks as matchup/context info
    if feature_name.startswith(("adj_off_", "off_")):
        return "offense"
    if feature_name.startswith(("adj_def_", "def_")):
        return "defense"
    if feature_name in {"neutral_site", "same_conference"} or feature_name.startswith(
        ("tempo_", "drives_", "scoring_opps_")
    ):
        return "context"
    if (
        feature_name.endswith("plays_per_game")
        or feature_name.endswith("drives_per_game")
        or feature_name.endswith("avg_scoring_opps_per_game")
    ):
        return "pace"
    lowered = feature_name.lower()
    if any(token in lowered for token in ["punt", "fg_", "kick"]):
        return "special_teams"
    if any(token in lowered for token in ["net_punt"]):
        return "special_teams_high_risk"
    if any(
        token in lowered
        for token in [
            "eckel",
            "drive",
            "points_per_drive",
            "finish_pts",
            "field_position",
        ]
    ):
        return "drive"
    if "_def_" in feature_name and not feature_name.startswith("matchup_"):
        return "defense"
    if "_off_" in feature_name:
        return "offense"
    return "other"


def filter_features_by_pack(
    feature_names: list[str], allowed_packs: list[str] | None
) -> list[str]:
    """Filter a feature list down to the specified conceptual packs."""

    if not feature_names:
        return []
    if not allowed_packs or "all" in allowed_packs:
        # By default, drop high-risk ST metrics (net punt/kick) unless explicitly requested
        return [
            f
            for f in feature_names
            if _categorize_feature_name(f) != "special_teams_high_risk"
        ]
    allowed = {pack.lower() for pack in allowed_packs}
    filtered: list[str] = []
    for name in feature_names:
        if _categorize_feature_name(name) in allowed:
            filtered.append(name)
    return filtered


def _add_style_features(df: pd.DataFrame) -> pd.DataFrame:
    """Augment merged datasets with tempo/drive/opp contrast features."""
    augmented = df.copy()
    epsilon = 1e-6
    for metric, label in STYLE_METRICS.items():
        home_col = f"home_{metric}"
        away_col = f"away_{metric}"
        if home_col not in augmented.columns or away_col not in augmented.columns:
            continue
        contrast_col = f"{label}_contrast"
        total_col = f"{label}_total"
        ratio_col = f"{label}_ratio"
        augmented[contrast_col] = augmented[home_col].astype(float) - augmented[
            away_col
        ].astype(float)
        augmented[total_col] = augmented[home_col].astype(float) + augmented[
            away_col
        ].astype(float)
        augmented[ratio_col] = augmented[home_col].astype(float) / (
            augmented[away_col].astype(float) + epsilon
        )
    return augmented


def _read_team_week_adj_partition(
    storage: LocalStorage,
    year: int,
    week: int,
    iteration: int | None,
) -> pd.DataFrame | None:
    """Read weekly adjusted features for a specific iteration (or legacy layout)."""
    filters: dict[str, int] = {"year": year, "week": week}
    if iteration is not None:
        filters = {"iteration": iteration, "year": year, "week": week}

    records = storage.read_index("team_week_adj", filters)
    if not records and iteration is not None:
        # Fall back to legacy layout when iteration-specific partitions are absent.
        records = storage.read_index("team_week_adj", {"year": year, "week": week})
    if not records:
        return None
    return pd.DataFrame.from_records(records)


def _merge_mixed_iteration_features(
    offense_df: pd.DataFrame,
    defense_df: pd.DataFrame,
) -> pd.DataFrame:
    """Combine offense metrics from one iteration with defense metrics from another."""
    key_columns = ["season", "team"]
    for candidate in ("week", "before_week"):
        if candidate in offense_df.columns and candidate in defense_df.columns:
            key_columns = ["season", candidate, "team"]
            break

    offense_idx = offense_df.set_index(key_columns)
    defense_idx = defense_df.set_index(key_columns)

    def _is_defense_column(column: str) -> bool:
        return column.startswith("def_") or column.startswith("adj_def_")

    # Ensure all defense columns exist on the combined frame before assignment.
    missing_def_cols = [col for col in defense_idx.columns if _is_defense_column(col)]
    for col in missing_def_cols:
        if col not in offense_idx.columns:
            offense_idx[col] = pd.NA

    offense_idx.loc[:, missing_def_cols] = defense_idx[missing_def_cols]
    combined = offense_idx.reset_index()
    return combined


def load_weekly_team_features(
    year: int,
    week: int,
    data_root: str,
    *,
    adjustment_iteration: int | None = 4,
    adjustment_iteration_offense: int | None = None,
    adjustment_iteration_defense: int | None = None,
) -> pd.DataFrame | None:
    """Load weekly team features with optional mixed offense/defense iterations."""
    processed = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )

    offense_iteration = (
        adjustment_iteration_offense
        if adjustment_iteration_offense is not None
        else adjustment_iteration
    )
    defense_iteration = (
        adjustment_iteration_defense
        if adjustment_iteration_defense is not None
        else adjustment_iteration
    )

    offense_df = _read_team_week_adj_partition(processed, year, week, offense_iteration)
    if offense_df is None:
        return None

    team_features_df = offense_df
    if defense_iteration != offense_iteration:
        defense_df = _read_team_week_adj_partition(
            processed, year, week, defense_iteration
        )
        if defense_df is not None:
            team_features_df = _merge_mixed_iteration_features(offense_df, defense_df)

    team_features_df = team_features_df.copy()
    team_features_df["off_adjustment_iteration"] = (
        offense_iteration if offense_iteration is not None else pd.NA
    )
    team_features_df["def_adjustment_iteration"] = (
        defense_iteration if defense_iteration is not None else pd.NA
    )
    return team_features_df


def _load_betting_lines(
    storage: LocalStorage, year: int, week: int
) -> pd.DataFrame | None:
    """Load betting lines for a specific year and week."""
    records = storage.read_index("betting_lines", {"year": year, "week": week})
    if not records:
        return None

    df = pd.DataFrame.from_records(records)

    # Filter/Prioritize providers
    # Priority: Consensus > Bovada > DraftKings > FanDuel > ...
    # We want one line per game.
    if "provider" in df.columns:
        provider_priority = {
            "Consensus": 0,
            "consensus": 0,
            "Bovada": 1,
            "DraftKings": 2,
            "FanDuel": 3,
            "BetMGM": 4,
            "Caesars": 5,
        }
        df["provider_rank"] = df["provider"].map(provider_priority).fillna(99)
        df = df.sort_values(["game_id", "provider_rank"])
        df = df.drop_duplicates(subset=["game_id"], keep="first")
        df = df.drop(columns=["provider_rank"])

    return df


def load_point_in_time_data(
    year: int,
    week: int,
    data_root: str,
    *,
    adjustment_iteration: int | None = 4,
    adjustment_iteration_offense: int | None = None,
    adjustment_iteration_defense: int | None = None,
    include_betting_lines: bool = False,
) -> pd.DataFrame | None:
    """Loads pre-cached, point-in-time features for a specific week.

    Args:
        year: Season to load.
        week: Week (1-indexed) within the season.
        data_root: Root directory for the data lake.
        adjustment_iteration: Number of opponent-adjustment iterations the cache
            represents. Defaults to 4. Pass ``None`` to fall back to the legacy
            layout without the iteration directory.
        adjustment_iteration_offense: Override offense iteration depth (defaults to
            ``adjustment_iteration``).
        adjustment_iteration_defense: Override defense iteration depth (defaults to
            ``adjustment_iteration``).
        include_betting_lines: If True, load and merge betting lines to calculate
            residual targets.
    """
    raw = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")

    team_features_df = load_weekly_team_features(
        year,
        week,
        data_root,
        adjustment_iteration=adjustment_iteration,
        adjustment_iteration_offense=adjustment_iteration_offense,
        adjustment_iteration_defense=adjustment_iteration_defense,
    )
    if team_features_df is None:
        return None

    all_game_records = raw.read_index("games", {"year": year})
    if not all_game_records:
        return None
    all_games_df = pd.DataFrame.from_records(all_game_records)
    week_games_df = all_games_df[all_games_df["week"] == week].copy()
    if week_games_df.empty:
        return None

    home_features = team_features_df.add_prefix("home_")
    away_features = team_features_df.add_prefix("away_")

    merged_df = week_games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )
    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
    )

    if "home_points" in merged_df.columns and "away_points" in merged_df.columns:
        merged_df["spread_target"] = merged_df["home_points"].astype(float) - merged_df[
            "away_points"
        ].astype(float)
        merged_df["total_target"] = merged_df["home_points"].astype(float) + merged_df[
            "away_points"
        ].astype(float)
        merged_df["home_points_for"] = merged_df["home_points"].astype(float)
        merged_df["away_points_for"] = merged_df["away_points"].astype(float)

    if include_betting_lines:
        lines_df = _load_betting_lines(raw, year, week)
        if lines_df is not None and not lines_df.empty:
            # Merge lines
            # lines_df has 'game_id', merged_df has 'id'
            # We use left join to keep all games, but targets will be NaN if no line
            merged_df = merged_df.merge(
                lines_df[["game_id", "spread", "over_under"]],
                left_on="id",
                right_on="game_id",
                how="left",
                suffixes=("", "_line"),
            )

            # Calculate Residuals
            # spread_target is (Home - Away). spread_line is Home Spread (e.g. -7 for Home Fav).
            # If Home wins by 7 (Target=7) and Line is -7. Residual should be 0.
            # Residual = Target + Line.
            if "spread" in merged_df.columns and "spread_target" in merged_df.columns:
                merged_df["spread_line"] = merged_df["spread"]
                merged_df["spread_residual_target"] = (
                    merged_df["spread_target"] + merged_df["spread_line"]
                )

            if (
                "over_under" in merged_df.columns
                and "total_target" in merged_df.columns
            ):
                merged_df["total_line"] = merged_df["over_under"]
                merged_df["total_residual_target"] = (
                    merged_df["total_target"] - merged_df["total_line"]
                )

    if (
        "home_conference" in merged_df.columns
        and "away_conference" in merged_df.columns
    ):
        merged_df["same_conference"] = (
            merged_df["home_conference"].astype(str)
            == merged_df["away_conference"].astype(str)
        ).astype(int)
    elif "conference_game" in merged_df.columns:
        merged_df["same_conference"] = merged_df["conference_game"].astype(int)
    else:
        merged_df["same_conference"] = 0

    merged_df = merged_df.drop(columns=["home_season", "away_season"], errors="ignore")
    merged_df = _add_style_features(merged_df)
    return merged_df


def load_merged_dataset(year: int, data_root: str | None) -> pd.DataFrame:
    """Load adjusted team-season features and merge into games for a season.

    Args:
        year: Season to load.
        data_root: Optional data root override; falls back to config.

    Returns:
        DataFrame with per-game home/away features and spread/total targets.

    Raises:
        ValueError: If adjusted team season data or raw games are missing, or if
            required score columns are absent.
    """
    resolved_root = data_root or get_data_root()
    processed_storage = LocalStorage(
        data_root=resolved_root, file_format="csv", data_type="processed"
    )
    raw_storage = LocalStorage(
        data_root=resolved_root, file_format="csv", data_type="raw"
    )

    team_season_adj_records = processed_storage.read_index(
        "team_season_adj", {"year": year}
    )
    if not team_season_adj_records:
        raise ValueError(f"No adjusted team season data found for year {year}")
    team_season_adj_df = pd.DataFrame.from_records(team_season_adj_records)
    team_features = prepare_team_features(team_season_adj_df)

    game_records = raw_storage.read_index("games", {"year": year})
    if not game_records:
        raise ValueError(f"No raw game data found for year {year}")
    games_df = pd.DataFrame.from_records(game_records)

    home_features = team_features.add_prefix("home_")
    away_features = team_features.add_prefix("away_")

    merged_df = games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )
    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
    )

    required_scores = {"home_points", "away_points"}
    if not required_scores.issubset(merged_df.columns):
        raise ValueError(
            "Games data missing required score columns: home_points, away_points"
        )

    merged_df["spread_target"] = merged_df["home_points"].astype(float) - merged_df[
        "away_points"
    ].astype(float)
    merged_df["total_target"] = merged_df["home_points"].astype(float) + merged_df[
        "away_points"
    ].astype(float)
    merged_df = merged_df.drop(columns=["home_season", "away_season"], errors="ignore")
    merged_df = _add_style_features(merged_df)
    return merged_df
