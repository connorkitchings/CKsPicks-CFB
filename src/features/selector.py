import hashlib
from typing import Dict, List

import pandas as pd
from omegaconf import DictConfig


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
        recency_cols = [c for c in df.columns if c.endswith(suffix)]

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
