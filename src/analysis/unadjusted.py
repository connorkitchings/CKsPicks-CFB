"""Helpers for working with unadjusted team aggregates.

These utilities read the non-adjusted weekly caches already persisted by
`scripts/cache_weekly_stats.py` (the `running_team_season` entity) and provide
simple helpers for leaderboards and downstream visualisations.
"""

from __future__ import annotations

import re
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import numpy as np
import pandas as pd
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from PIL import Image, ImageOps

from src.config import LOGOS_DIR, get_data_root
from src.features.core import aggregate_team_season
from src.utils.local_storage import LocalStorage

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure


@dataclass(frozen=True)
class SnapshotMetadata:
    """Metadata describing the returned snapshot."""

    year: int
    before_week: int


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


@lru_cache(maxsize=None)
def _logo_index() -> dict[str, Path]:
    logo_dir = Path(LOGOS_DIR)
    mapping: dict[str, Path] = {}
    if not logo_dir.is_dir():
        return mapping
    for path in logo_dir.glob("*.png"):
        key = _normalize_name(path.stem)
        mapping[key] = path
    return mapping


@lru_cache(maxsize=None)
def _fbs_team_names(year: int, data_root: str) -> set[str]:
    storage = LocalStorage(
        data_root=data_root,
        file_format="csv",
        data_type="raw",
    )
    records = storage.read_index("teams", {"year": year})
    return {
        _normalize_name(record["school"])
        for record in records
        if record.get("classification", "").lower() == "fbs"
    }


def load_running_season_snapshot(
    year: int,
    *,
    data_root: str | None = None,
    before_week: Optional[int] = None,
) -> tuple[pd.DataFrame, SnapshotMetadata]:
    """Compute the unadjusted season-to-date snapshot for the requested week.

    This function rebuilds the aggregates directly from the `team_game` entity so
    that results are restricted to FBS vs FBS matchups with accurate game counts.
    """
    resolved_root = data_root or str(get_data_root())
    processed_storage = LocalStorage(
        data_root=resolved_root,
        file_format="csv",
        data_type="processed",
    )
    team_game_records = processed_storage.read_index("team_game", {"year": year})
    if not team_game_records:
        raise FileNotFoundError(
            f"No team_game records found for year={year} under {resolved_root}."
        )

    team_game_df = pd.DataFrame.from_records(team_game_records)
    if "week" not in team_game_df.columns:
        raise ValueError("team_game data is missing the 'week' column.")

    team_game_df["week"] = team_game_df["week"].astype(int)

    raw_storage = LocalStorage(
        data_root=resolved_root,
        file_format="csv",
        data_type="raw",
    )
    games_records = raw_storage.read_index("games", {"year": year})
    if not games_records:
        raise FileNotFoundError(
            f"No games records found for year={year} under {resolved_root}."
        )
    games_df = pd.DataFrame.from_records(games_records)
    required_game_cols = {"id", "season_type", "start_date", "home_team", "away_team"}
    if not required_game_cols.issubset(games_df.columns):
        missing = ", ".join(sorted(required_game_cols - set(games_df.columns)))
        raise ValueError(
            f"games dataset must include columns: {', '.join(sorted(required_game_cols))}. Missing: {missing}"
        )

    games_df["id"] = games_df["id"].astype(team_game_df["game_id"].dtype)
    games_df["season_type"] = games_df["season_type"].astype(str).str.lower()
    games_df["home_classification"] = games_df["home_classification"].astype(str).str.lower()
    games_df["away_classification"] = games_df["away_classification"].astype(str).str.lower()
    games_df["start_date"] = pd.to_datetime(
        games_df["start_date"], utc=True, errors="coerce"
    )
    games_df["start_date"] = games_df["start_date"].dt.tz_convert(None)

    cutoff = pd.Timestamp(year, 12, 7)

    def _is_army_navy(row: pd.Series) -> bool:
        home = _normalize_name(str(row["home_team"]))
        away = _normalize_name(str(row["away_team"]))
        return {"army", "navy"}.issubset({home, away})

    regular_mask = games_df["season_type"] == "regular"
    date_mask = games_df["start_date"].le(cutoff) | games_df.apply(_is_army_navy, axis=1)
    classification_mask = (games_df["home_classification"] == "fbs") & (
        games_df["away_classification"] == "fbs"
    )
    valid_games_df = games_df[regular_mask & date_mask & classification_mask].copy()

    regular_ids = set(valid_games_df["id"])
    if not regular_ids:
        raise ValueError("No regular season games before cutoff found for the supplied season.")

    valid_game_ids = regular_ids
    if not valid_game_ids:
        raise ValueError("No regular-season FBS vs FBS games found for this season.")

    team_game_df = team_game_df[team_game_df["game_id"].isin(valid_game_ids)].copy()
    if team_game_df.empty:
        raise ValueError(
            "Filtered team_game dataframe is empty after applying FBS-only criteria."
        )

    max_week = int(team_game_df["week"].max())
    selected_week = int(before_week) if before_week is not None else max_week + 1
    if selected_week <= team_game_df["week"].min():
        raise ValueError(
            f"before_week={selected_week} does not leave any prior games to aggregate."
        )

    prior_games_df = team_game_df[team_game_df["week"] < selected_week].copy()
    if prior_games_df.empty:
        raise ValueError(
            "No games available before the requested week after filtering to FBS matchups."
        )

    snapshot = aggregate_team_season(prior_games_df)
    snapshot["before_week"] = selected_week
    snapshot["season"] = year
    snapshot["games_played"] = snapshot["games_played"].round().astype(int)

    metadata = SnapshotMetadata(year=year, before_week=selected_week)
    return snapshot, metadata


def resolve_stat_column(
    dataframe: pd.DataFrame,
    stat: str,
    *,
    side: str,
) -> str:
    """Resolve a user-supplied stat name to an actual column."""
    normalized_side = side.lower()
    if normalized_side not in {"offense", "defense"}:
        raise ValueError("side must be 'offense' or 'defense'")

    if stat in dataframe.columns:
        return stat

    prefix = "off_" if normalized_side == "offense" else "def_"
    candidate = stat if stat.startswith(prefix) else f"{prefix}{stat}"
    if candidate in dataframe.columns:
        return candidate

    raise KeyError(
        f"Column for stat '{stat}' not found. "
        f"Tried '{stat}' and '{candidate}'. Available columns include: "
        f"{', '.join(sorted(dataframe.columns))}"
    )


def build_leaderboard(
    snapshot: pd.DataFrame,
    stat: str,
    *,
    side: str,
    limit: int = 10,
) -> pd.DataFrame:
    """Return a leaderboard DataFrame for the requested stat."""
    if snapshot.empty:
        raise ValueError("Snapshot is empty; nothing to rank.")

    working = snapshot.copy()
    if "games_played" not in working.columns and "games" in working.columns:
        working = working.rename(columns={"games": "games_played"})
    if "games_played" not in working.columns:
        working["games_played"] = pd.NA

    stat_column = resolve_stat_column(working, stat, side=side)

    leaderboard = working[["team", "games_played", stat_column]].copy()
    leaderboard = leaderboard.rename(columns={stat_column: stat})

    ascending = side.lower() == "defense"
    leaderboard = leaderboard.sort_values(stat, ascending=ascending).reset_index(
        drop=True
    )
    leaderboard[f"{stat}_rank"] = leaderboard.index + 1
    if limit:
        leaderboard = leaderboard.head(limit).reset_index(drop=True)
    return leaderboard


def _load_logo(team: str, *, alpha: float, grayscale: bool) -> np.ndarray | None:
    normalized_key = _normalize_name(team)
    logo_path = _logo_index().get(normalized_key)
    if logo_path is None or not logo_path.is_file():
        return None

    image = Image.open(logo_path).convert("RGBA")
    if grayscale:
        image = ImageOps.grayscale(image).convert("RGBA")

    logo_array = np.array(image)
    if alpha < 1.0:
        logo_array = logo_array.copy()
        logo_array[..., 3] = (logo_array[..., 3].astype(float) * alpha).astype(
            logo_array.dtype
        )
    return logo_array


def filter_to_fbs(snapshot: pd.DataFrame, year: int, *, data_root: str) -> pd.DataFrame:
    """Filter snapshot rows to FBS teams based on the raw teams registry."""
    if snapshot.empty:
        return snapshot
    allowed = _fbs_team_names(year, data_root)
    mask = snapshot["team"].apply(lambda name: _normalize_name(str(name)) in allowed)
    return snapshot[mask].copy().reset_index(drop=True)


def scatter_plot(
    snapshot: pd.DataFrame,
    stat_x: str,
    stat_y: str,
    *,
    side: str,
    highlight_team: str | None = None,
    show_medians: bool = True,
    figsize: tuple[float, float] = (14.0, 10.0),
    logo_zoom: float = 0.22,
) -> tuple["Figure", "Axes"]:
    """Create a scatter plot for two unadjusted stats."""
    if snapshot.empty:
        raise ValueError("Snapshot is empty; cannot create scatter plot.")

    import matplotlib.pyplot as plt  # pylint: disable=import-outside-toplevel

    working = snapshot.copy()
    stat_x_column = resolve_stat_column(working, stat_x, side=side)
    stat_y_column = resolve_stat_column(working, stat_y, side=side)

    x_values = working[stat_x_column].astype(float)
    y_values = working[stat_y_column].astype(float)

    fig, ax = plt.subplots(figsize=figsize)

    x_range = x_values.max() - x_values.min()
    y_range = y_values.max() - y_values.min()
    x_padding = x_range * 0.1 if x_range else 0.5
    y_padding = y_range * 0.1 if y_range else 0.5
    ax.set_xlim(x_values.min() - x_padding, x_values.max() + x_padding)
    ax.set_ylim(y_values.min() - y_padding, y_values.max() + y_padding)

    ax.scatter(x_values, y_values, alpha=0)  # base coordinates for scaling

    highlight_key = _normalize_name(highlight_team) if highlight_team else None
    rows = working.sort_values(stat_x_column).to_dict(orient="records")

    for row in rows:
        team = row["team"]
        value_x = float(row[stat_x_column])
        value_y = float(row[stat_y_column])

        team_key = _normalize_name(team)
        is_highlight = highlight_key is None or team_key == highlight_key

        logo_array = _load_logo(
            team,
            alpha=1.0 if is_highlight else 0.65,
            grayscale=highlight_key is not None and team_key != highlight_key,
        )
        if logo_array is not None:
            zoom = logo_zoom * (1.35 if is_highlight else 1.05)
            image_box = OffsetImage(logo_array, zoom=zoom)
            annotation = AnnotationBbox(
                image_box,
                (value_x, value_y),
                frameon=False,
                box_alignment=(0.5, 0.5),
                zorder=3 if is_highlight else 2,
            )
            ax.add_artist(annotation)
        else:
            ax.scatter(
                value_x,
                value_y,
                color="firebrick" if is_highlight else "gray",
                alpha=1.0 if is_highlight else 0.35,
                s=120 if is_highlight else 50,
                zorder=3 if is_highlight else 2,
            )
            if is_highlight:
                ax.text(
                    value_x,
                    value_y,
                    team,
                    fontsize=12,
                    ha="center",
                    va="bottom",
                    color="firebrick",
                    weight="bold",
                    bbox=dict(facecolor="white", alpha=0.7, edgecolor="none", pad=1),
                )
        if not is_highlight and highlight_key is not None:
            ax.text(
                value_x,
                value_y,
                "",
                fontsize=1,
                ha="center",
                va="center",
                zorder=1,
            )

    if show_medians:
        median_x = x_values.median()
        median_y = y_values.median()
        ax.axvline(median_x, linestyle="--", color="gray", alpha=0.6)
        ax.axhline(median_y, linestyle="--", color="gray", alpha=0.6)

    axis_side = side.capitalize()
    prefix = "off_" if side.lower() == "offense" else "def_"

    def _prettify(column: str) -> str:
        label = column[len(prefix) :] if column.startswith(prefix) else column
        return label.replace("_", " ").title()

    x_label = f"{axis_side} {_prettify(stat_x_column)}"
    y_label = f"{axis_side} {_prettify(stat_y_column)}"
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)

    if side.lower() == "defense":
        ax.invert_xaxis()
        ax.invert_yaxis()

    ax.grid(True, linestyle=":", alpha=0.6)

    return fig, ax
