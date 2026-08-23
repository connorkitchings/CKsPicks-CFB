"""Pure completed-game and upcoming-game regime routing helpers."""

from __future__ import annotations

import pandas as pd

CANONICAL_EARLY_REGIMES = ("game_1", "game_2", "game_3", "game_4", "established")
LEGACY_TO_CANONICAL_REGIME = {
    "preseason": "game_1",
    "one_game": "game_2",
    "two_games": "game_3",
    "three_games": "game_4",
    "established": "established",
}


def completed_game_regime(games: int | float | None) -> str:
    """Return the legacy completed-game routing label."""
    count = 0 if games is None or pd.isna(games) else max(0, int(games))
    return {
        0: "preseason",
        1: "one_game",
        2: "two_games",
        3: "three_games",
    }.get(count, "established")


def upcoming_game_regime(completed_games: int | float | None) -> str:
    """Return the canonical route for a team's next scheduled game."""
    count = (
        0
        if completed_games is None or pd.isna(completed_games)
        else max(0, int(completed_games))
    )
    return {0: "game_1", 1: "game_2", 2: "game_3", 3: "game_4"}.get(
        count, "established"
    )


def canonical_prediction_regime(value: str | None) -> str:
    """Normalize a legacy or canonical route value to the new contract."""
    if value in CANONICAL_EARLY_REGIMES:
        return str(value)
    try:
        return LEGACY_TO_CANONICAL_REGIME[str(value)]
    except KeyError as exc:
        raise ValueError(f"Unsupported prediction regime: {value!r}") from exc
