"""Pure site-class and conference context for the error diagnostics.

Inputs are the game rows of the V5 `fbs_involved_games` dataset (neutral flag,
venue id, each team's conference in that season, conference-game flag). Nothing
here uses betting lines or results.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HOME_VENUE_MIN_GAMES = 3
VENUE_CLASSES = (
    "home venue",
    "neutral site",
    "non-home venue, not flagged neutral",
    "venue unknown",
)
POWER_CONFERENCES = ("ACC", "Big 12", "Big Ten", "Pac-12", "SEC")
GROUP_OF_5_CONFERENCES = (
    "American Athletic",
    "Conference USA",
    "Mid-American",
    "Mountain West",
    "Sun Belt",
)
CONFERENCE_GROUPS = ("Power", "Group of 5", "FBS independent", "other")
CONFERENCE_GAME_LABELS = ("conference game", "non-conference game")


def home_venues(games: pd.DataFrame) -> dict[str, set[int]]:
    """Each team's home venue ids, from its own non-neutral hosted games.

    A venue counts when the team hosted at least ``HOME_VENUE_MIN_GAMES`` games
    there; the team's most frequent venue always counts.
    """
    hosted = games[games["neutral_site"].eq(False) & games["venue_id"].notna()]
    counts = hosted.groupby(["home_team", "venue_id"]).size()
    result: dict[str, set[int]] = {}
    for team, per_venue in counts.groupby(level=0):
        per_venue = per_venue.droplevel(0)
        keep = {int(v) for v in per_venue[per_venue >= HOME_VENUE_MIN_GAMES].index}
        keep.add(int(per_venue.sort_values(ascending=False, kind="mergesort").index[0]))
        result[str(team)] = keep
    return result


def venue_class(games: pd.DataFrame) -> pd.Series:
    """Home venue, neutral site, non-home venue without the neutral flag, or unknown."""
    venues = home_venues(games)
    labels = []
    for row in games.itertuples(index=False):
        if pd.isna(row.neutral_site) or pd.isna(row.venue_id):
            labels.append("venue unknown")
        elif bool(row.neutral_site):
            labels.append("neutral site")
        elif int(row.venue_id) in venues.get(str(row.home_team), set()):
            labels.append("home venue")
        else:
            labels.append("non-home venue, not flagged neutral")
    return pd.Series(labels, index=games.index)


def conference_group(conference: pd.Series) -> pd.Series:
    """Group each team's conference label for that season (realignment is in the data)."""

    def group(name: object) -> str:
        if name in POWER_CONFERENCES:
            return "Power"
        if name in GROUP_OF_5_CONFERENCES:
            return "Group of 5"
        if name == "FBS Independents":
            return "FBS independent"
        return "other"

    return conference.map(group)


def game_context(games: pd.DataFrame) -> pd.DataFrame:
    """Per-game site class, home-team conference and group, conference-game flag."""
    out = games[["season", "game_id"]].copy()
    out["venue_class"] = venue_class(games)
    out["home_conference"] = games["home_conference"].astype(str)
    out["conference_group"] = conference_group(games["home_conference"])
    out["conference_game_label"] = np.where(
        games["conference_game"].astype(bool),
        CONFERENCE_GAME_LABELS[0],
        CONFERENCE_GAME_LABELS[1],
    )
    return out
