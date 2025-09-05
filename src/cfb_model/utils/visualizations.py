"""Plotting and visualization utilities for analysis."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

# --- Configuration ---
# TODO: Make this configurable via environment or a config file.
LOGO_PATH = "data/logos/"

# --- Data Dictionaries ---
P5_SCHOOLS_AND_CONFERENCES = {
    "Alabama": "SEC",
    "Arkansas": "SEC",
    "Auburn": "SEC",
    "Florida": "SEC",
    "Georgia": "SEC",
    "Kentucky": "SEC",
    "LSU": "SEC",
    "Mississippi State": "SEC",
    "Missouri": "SEC",
    "Ole Miss": "SEC",
    "South Carolina": "SEC",
    "Tennessee": "SEC",
    "Texas A&M": "SEC",
    "Vanderbilt": "SEC",
    "Illinois": "Big Ten",
    "Indiana": "Big Ten",
    "Iowa": "Big Ten",
    "Maryland": "Big Ten",
    "Michigan": "Big Ten",
    "Michigan State": "Big Ten",
    "Minnesota": "Big Ten",
    "Nebraska": "Big Ten",
    "Northwestern": "Big Ten",
    "Ohio State": "Big Ten",
    "Penn State": "Big Ten",
    "Purdue": "Big Ten",
    "Rutgers": "Big Ten",
    "Wisconsin": "Big Ten",
    "Baylor": "Big 12",
    "Iowa State": "Big 12",
    "Kansas": "Big 12",
    "Kansas State": "Big 12",
    "Oklahoma": "Big 12",
    "Oklahoma State": "Big 12",
    "TCU": "Big 12",
    "Texas": "Big 12",
    "Texas Tech": "Big 12",
    "West Virginia": "Big 12",
    "Arizona": "Pac-12",
    "Arizona State": "Pac-12",
    "California": "Pac-12",
    "Colorado": "Pac-12",
    "Oregon": "Pac-12",
    "Oregon State": "Pac-12",
    "Stanford": "Pac-12",
    "UCLA": "Pac-12",
    "USC": "Pac-12",
    "Utah": "Pac-12",
    "Washington": "Pac-12",
    "Washington State": "Pac-12",
    "BYU": "Big 12",
    "Notre Dame": "Independent",
}

STATS_DICTIONARY = {
    "ypp": "Yards Per Play",
    "success_rate": "Success Rate",
    "explosive_rate": "Explosive Rate",
    "TFL_rate": "Tackle For Loss Rate",
    "turnover_rate": "Turnover Rate",
    "third_down_conversion_rate": "Third Down Conversion Rate",
    "fourth_down_conversion_rate": "Fourth Down Conversion Rate",
    "rushpass_split": "Rush/Pass Play Split",
    "r_ypp": "Rushing Yards Per Play",
    "r_success_rate": "Rushing Success Rate",
    "r_explosive_rate": "Rushing Explosive Rate",
    "r_successyards_per_success": "Rushing Success Yards Per Success",
    "r_explosiveyards_per_explosive": "Rushing Explosive Yards Per Explosive",
    "stuff_rate": "Stuff Rate",
    "p_ypp": "Passing Yards Per Play",
    "p_success_rate": "Passing Success Rate",
    "p_explosive_rate": "Passing Explosive Rate",
    "p_successyards_per_success": "Passing Success Yards Per Success",
    "p_explosiveyards_per_explosive": "Passing Explosive Yards Per Explosive",
    "completion_rate": "Completion Rate",
    "sack_rate": "Sack Rate",
    "havoc_rate": "Havoc Rate",
    "avg_available_yards": "Average Available Yards",
    "avg_available_yards_gained": "Average Available Yards Gained",
    "redzone_drive_rate": "Redzone Drive Rate",
    "eckel_drive_rate": "Eckel Drive Rate",
    "drive_success_rate": "Drive Success Rate",
    "scoring_drive_rate": "Scoring Drive Rate",
    "pointsscored_per_drive": "Points Scored Per Drive",
    "TD_drive_rate": "Touchdown Drive Rate",
    "FG_drive_rate": "Field Goal Drive Rate",
    "firstdown_drive_rate": "First Down Drive Rate",
    "busted_drive_rate": "Busted Drive Rate",
    "longdrive_rate": "Long Drive Rate",
    "ppa_per_drive": "Predicted Points Added Per Drive",
    "giveaway_drive_rate": "Giveaway Drive Rate",
    "o_penalties_per_drive": "Offensive Penalties Per Drive",
    "o_penaltyyards_per_drive": "Offensive Penalty Yards Per Drive",
    "d_penalties_per_drive": "Defensive Penalties Per Drive",
    "d_penaltyyards_per_drive": "Defensive Penalty Yards Per Drive",
}


# --- Helper Functions ---
def get_image(team_name: str, zoom: float = 1.0):
    """Load a team logo image."""
    try:
        img = plt.imread(f"{LOGO_PATH}{team_name}.png")
        return OffsetImage(img, zoom=zoom)
    except FileNotFoundError:
        print(f"Logo for {team_name} not found at {LOGO_PATH}{team_name}.png")
        return OffsetImage(np.zeros((1, 1, 4)))  # Transparent placeholder


# --- Main Visualization Function ---
def create_graph_comparison(
    data: pd.DataFrame,
    season: int,
    comparison: str,
    statx: str,
    staty: str,
    p5_only: bool = False,
    add_diagonal_line: bool = False,
    is_adjusted: bool = False,
):
    """Create a scatter plot comparing two statistics for a given season."""
    try:
        # --- Data Preparation ---
        suffix = "_o" if comparison == "offense" else "_d"
        suffix_to_drop = "_d" if comparison == "offense" else "_o"
        cols_to_drop = [c for c in data.columns if c.endswith(suffix_to_drop)]

        season_data = data[data["season"] == season].copy()
        season_data = season_data.drop(columns=cols_to_drop)
        season_data.columns = [
            col.removesuffix(suffix) if col.endswith(suffix) else col
            for col in season_data.columns
        ]

        if p5_only:
            p5_teams = list(P5_SCHOOLS_AND_CONFERENCES.keys())
            final_dataset = season_data[season_data["team"].isin(p5_teams)]
        else:
            final_dataset = season_data

        if statx not in final_dataset.columns or staty not in final_dataset.columns:
            raise ValueError(f"Stats {statx} or {staty} not found in the data.")

        x_axis = final_dataset[statx]
        y_axis = final_dataset[staty]

        # --- Plotting ---
        fig, ax = plt.subplots(figsize=(12, 8))

        x_range = x_axis.max() - x_axis.min()
        y_range = y_axis.max() - y_axis.min()
        padding = 0.1
        x_min, x_max = (x_axis.min() - x_range * padding, x_axis.max() + x_range * padding)
        y_min, y_max = (y_axis.min() - y_range * padding, y_axis.max() + y_range * padding)

        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)

        ax.scatter(x=x_axis, y=y_axis, alpha=0)  # Transparent markers

        median_x = x_axis.median()
        median_y = y_axis.median()
        ax.axvline(median_x, color="grey", linestyle="--", alpha=0.7)
        ax.axhline(median_y, color="grey", linestyle="--", alpha=0.7)

        # --- Titles and Labels ---
        x_title_base = STATS_DICTIONARY.get(statx, statx)
        y_title_base = STATS_DICTIONARY.get(staty, staty)
        adj_prefix = "Adjusted " if is_adjusted else ""
        comp_title = comparison.capitalize()

        x_axis_title = f"{adj_prefix}{comp_title} {x_title_base}"
        y_axis_title = f"{adj_prefix}{comp_title} {y_title_base}"

        ax.set_title(f"{x_axis_title} vs. {y_axis_title} ({season})")
        ax.set_xlabel(x_axis_title)
        ax.set_ylabel(y_axis_title)

        if comparison == "defense":
            ax.invert_xaxis()
            ax.invert_yaxis()

        if add_diagonal_line:
            ax.plot([x_min, x_max], [y_min, y_max], color="black", linestyle="-", alpha=0.5)

        # --- Add Logos ---
        for x0, y0, team in zip(x_axis, y_axis, final_dataset["team"]):
            ab = AnnotationBbox(get_image(team), (x0, y0), frameon=False)
            ax.add_artist(ab)

        ax.grid(True, linestyle=":", alpha=0.6)
        plt.tight_layout()
        plt.show()

    except Exception as e:
        print(f"An error occurred: {e}")
