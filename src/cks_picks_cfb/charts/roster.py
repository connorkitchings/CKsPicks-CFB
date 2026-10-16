"""Published FBS roster: the authoritative team and conference list for charts."""

from __future__ import annotations

import pandas as pd

ROSTER_COLUMNS = ("season", "team", "conference")


class RosterError(ValueError):
    """The pinned teams input cannot produce a chart roster."""


def build_team_season_roster(teams: pd.DataFrame | None, season: int) -> pd.DataFrame:
    """One row per FBS team (provider name) with its published conference.

    FBS membership matches ``projection_football._fbs_teams``; the conference
    comes from the pinned Silver ``teams`` input (``normalize_teams``). A missing
    conference is stored as null rather than guessed.
    """
    if teams is None or teams.empty:
        raise RosterError("the revision lacks the pinned 'teams' input")
    name = next((c for c in ("team", "school") if c in teams.columns), None)
    if name is None or not {"classification", "conference"} <= set(teams.columns):
        raise RosterError(
            "pinned teams input needs team/school, classification and conference"
        )
    fbs = teams[teams["classification"].astype(str).str.lower().eq("fbs")]
    if fbs.empty:
        raise RosterError("pinned teams input lists no FBS team")
    frame = pd.DataFrame(
        {
            "season": season,
            "team": fbs[name].astype(str).to_numpy(),
            "conference": [
                None if pd.isna(value) else str(value) for value in fbs["conference"]
            ],
        }
    )
    if frame["team"].duplicated().any():
        raise RosterError("duplicate FBS team in the pinned teams input")
    return frame.sort_values("team", kind="mergesort").reset_index(drop=True)
