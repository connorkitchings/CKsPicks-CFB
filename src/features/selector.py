import hashlib
from typing import Dict, List

import pandas as pd
from omegaconf import DictConfig

RECENCY_BASE_FEATURES = {
    "def_avg_line_yards_allowed",
    "def_avg_open_field_yards_allowed",
    "def_avg_second_level_yards_allowed",
    "def_avg_start_field_position_allowed",
    "def_busted_drive_rate_allowed",
    "def_epa_pp",
    "def_expl_rate_overall_10",
    "def_expl_rate_overall_20",
    "def_expl_rate_overall_30",
    "def_expl_rate_pass",
    "def_expl_rate_rush",
    "def_explosive_drive_rate_allowed",
    "def_pass_ypp",
    "def_points_per_drive_allowed",
    "def_power_success_rate_allowed",
    "def_rush_ypp",
    "def_sr",
    "def_successful_drive_rate_allowed",
    "def_third_down_conversion_rate",
    "def_ypp",
    "drives_per_game",
    "havoc_rate",
    "net_field_position_delta",
    "off_avg_line_yards",
    "off_avg_net_punt_yards",
    "off_avg_open_field_yards",
    "off_avg_second_level_yards",
    "off_avg_start_field_position",
    "off_busted_drive_rate",
    "off_eckel_rate",
    "off_epa_pp",
    "off_expl_rate_overall_10",
    "off_expl_rate_overall_20",
    "off_expl_rate_overall_30",
    "off_expl_rate_pass",
    "off_expl_rate_rush",
    "off_explosive_drive_rate",
    "off_fg_attempts_short",
    "off_fg_made_short",
    "off_fg_rate_short",
    "off_finish_pts_per_opp",
    "off_pass_ypp",
    "off_points_per_drive",
    "off_power_success_rate",
    "off_rush_ypp",
    "off_sr",
    "off_successful_drive_rate",
    "off_third_down_conversion_rate",
    "off_ypp",
    "plays_per_game",
    "precipitation",
    "stuff_rate",
    "temperature",
    "wind_speed",
}


def get_feature_groups() -> Dict[str, List[str]]:
    """Define available feature groups."""
    return {
        "off_def_stats": [
            "adj_off_epa_pp",
            "adj_def_epa_pp",
            "adj_off_sr",
            "adj_def_sr",
            "adj_off_ypp",
            "adj_def_ypp",
            "adj_off_expl_rate_overall_20",
            "adj_def_expl_rate_overall_20",
        ],
        "pace_stats": [
            "plays_per_game",
            "drives_per_game",
            "tempo_contrast",
            "tempo_total",
        ],
        "recency_stats": [
            # Will be dynamically expanded to include _last_3 versions of base stats
        ],
        "luck_stats": ["cumulative_luck_factor"],
        "weather_stats": ["temperature", "precipitation", "wind_speed"],
    }


def select_features(df: pd.DataFrame, cfg: DictConfig) -> pd.DataFrame:
    """Select features based on configuration."""
    groups = cfg.features.groups
    feature_cols = []

    defined_groups = get_feature_groups()

    # Expand recency stats dynamically if requested
    if "recency_stats" in groups:
        # Determine suffix based on recency_window config
        suffix_map = {"fast": "_last_1", "last_1": "_last_1", "standard": "_last_3"}
        recency_window = cfg.features.get("recency_window", "standard")
        suffix = suffix_map.get(recency_window, "_last_3")

        # Scan dataframe for all columns matching the recency pattern
        # AND are in the allow-list
        recency_cols = []
        for col in df.columns:
            if not col.endswith(suffix):
                continue

            # Check if base feature is in allow-list
            # col is like "home_temperature_last_3" -> base "temperature"
            base_col = col.replace(suffix, "")
            if base_col.startswith("home_"):
                base_col = base_col.replace("home_", "")
            elif base_col.startswith("away_"):
                base_col = base_col.replace("away_", "")

            if base_col in RECENCY_BASE_FEATURES:
                recency_cols.append(col)

        # Also include _last_2 if requested
        if cfg.features.get("include_last_2", False):
            recency_cols.extend([c for c in df.columns if c.endswith("_last_2")])

        # Add to feature list
        feature_cols.extend(recency_cols)

    for group in groups:
        if group == "recency_stats":
            continue  # handled above
        if group in defined_groups:
            feature_cols.extend(defined_groups[group])
        else:
            # Allow direct column names if not a group
            feature_cols.append(group)

    # Generate Interactions if configured
    interactions = cfg.features.get("interactions", [])
    if interactions:
        for f1, f2 in interactions:
            # Home Offense vs Away Defense
            h_col = f"home_{f1}_x_away_{f2}"
            if f"home_{f1}" in df.columns and f"away_{f2}" in df.columns:
                df[h_col] = df[f"home_{f1}"] * df[f"away_{f2}"]
                feature_cols.append(h_col)

            # Away Offense vs Home Defense
            a_col = f"away_{f1}_x_home_{f2}"
            if f"away_{f1}" in df.columns and f"home_{f2}" in df.columns:
                df[a_col] = df[f"away_{f1}"] * df[f"home_{f2}"]
                feature_cols.append(a_col)

    # Weather Interactions (Explicit)
    if "weather_stats" in groups:
        # Define interactions: Weather Var x Team Stat
        weather_interactions = [
            ("wind_speed", "off_pass_ypp"),
            ("wind_speed", "off_expl_rate_pass"),
            ("precipitation", "off_fumble_rate"),  # if available
        ]

        # Identify available weather columns (could be 'wind_speed' or 'home_wind_speed')
        # We prefer the game-level 'wind_speed' if available, else 'home_wind_speed'

        for w_base, stat_base in weather_interactions:
            # Find the weather column
            w_col = None
            if w_base in df.columns:
                w_col = w_base
            elif f"home_{w_base}" in df.columns:
                w_col = f"home_{w_base}"

            if w_col:
                # Home Team Interaction
                h_stat = f"home_{stat_base}"
                if h_stat in df.columns:
                    new_col = f"home_{w_base}_x_{stat_base}"
                    df[new_col] = df[w_col] * df[h_stat]
                    feature_cols.append(new_col)

                # Away Team Interaction
                a_stat = f"away_{stat_base}"
                if a_stat in df.columns:
                    new_col = f"away_{w_base}_x_{stat_base}"
                    df[new_col] = df[w_col] * df[a_stat]
                    feature_cols.append(new_col)

    # Filter to columns that actually exist in df
    # Try to expand for home/away if not present directly
    final_cols = []
    for col in feature_cols:
        if col in df.columns:
            final_cols.append(col)
        else:
            # Check for home/away variants
            home_col = f"home_{col}"
            away_col = f"away_{col}"
            if home_col in df.columns:
                final_cols.append(home_col)
            if away_col in df.columns:
                final_cols.append(away_col)
            # Also check for matchup variants if applicable
            # (matchup features usually start with matchup_, so might be handled directly if config specifies them)

    # Deduplicate
    final_cols = sorted(list(set(final_cols)))

    available_cols = [c for c in final_cols if c in df.columns]

    exclude_features = set(cfg.features.get("exclude", []))
    if exclude_features:
        available_cols = [c for c in available_cols if c not in exclude_features]

    # Check for missing base features (if neither home nor away found)
    # This is approximate
    missing_base = []
    for col in feature_cols:
        if (
            col not in df.columns
            and f"home_{col}" not in df.columns
            and f"away_{col}" not in df.columns
        ):
            missing_base.append(col)

    if missing_base:
        print(
            f"Warning: {len(missing_base)} requested base features not found in dataframe: {list(missing_base)[:5]}..."
        )

    return df[available_cols]


def get_feature_set_id(cfg: DictConfig) -> str:
    """Generate a unique ID for the configured feature set."""
    # Sort groups to ensure stability
    groups = sorted(list(cfg.features.groups))
    s = f"{cfg.features.name}_{'-'.join(groups)}_{cfg.features.recency_window}"
    return hashlib.md5(s.encode()).hexdigest()[:8]
