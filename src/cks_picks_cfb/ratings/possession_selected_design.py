"""Pure computation of the selected rating design from measurement frames.

``ppp__rho_0_60__exposure`` is a fixed prior rule (0.60 per year carryover of the previous
season's terminal state) followed by an analytic exposure-weighted update: nothing is
fitted, no auxiliary data and no storage are needed. This runs only that design on staged
frames, using the same pure functions as the 60-candidate tournament, so it needs none of
the tournament's parent pins, Kalman fits or history audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    PRIOR_COLUMNS,
    RATING_STATE_COLUMNS,
    TEAM_STATE_COLUMNS,
)
from cks_picks_cfb.data.data_first_possession_v1 import ADJUSTED_MEASUREMENTS, ROLES
from cks_picks_cfb.ratings.possession_rating_materializer import (
    PossessionMaterializerError,
    RatingTournamentInputs,
    _fbs_universe,
    _replay_candidate_states,
    build_boundary_table,
    build_observation_streams,
    build_prior_tables,
    build_terminal_tables,
)

SELECTED_CANDIDATE = "ppp__rho_0_60__exposure"
_SELECTED = ("ppp", "rho_0_60", "exposure")


@dataclass(frozen=True)
class SelectedDesignFrames:
    candidate_id: str
    priors: pd.DataFrame
    rating_states: pd.DataFrame
    team_states: pd.DataFrame
    terminal_tables: dict[tuple[str, str, int], dict[str, Any]]


def _records(
    partitions: dict[tuple[int, int], list[dict[str, Any]]], columns: tuple[str, ...]
) -> pd.DataFrame:
    rows = [row for key in sorted(partitions) for row in partitions[key]]
    frame = pd.DataFrame.from_records(rows, columns=list(columns))
    return frame.sort_values(
        [
            name
            for name in ("season", "week", "game_id", "team", "unit_role")
            if name in frame
        ],
        kind="mergesort",
    ).reset_index(drop=True)


def compute_selected_design(
    *,
    population: pd.DataFrame,
    observations: pd.DataFrame,
    snapshots: pd.DataFrame,
    terminal: pd.DataFrame,
    candidate_id: str = SELECTED_CANDIDATE,
) -> SelectedDesignFrames:
    """Priors, pregame rating states and team states for the selected design only."""
    if candidate_id != SELECTED_CANDIDATE:
        raise PossessionMaterializerError(
            f"only {SELECTED_CANDIDATE} is supported, got {candidate_id}"
        )
    definition, family, updater = _SELECTED
    seasons = set(population["season"].astype(int))
    if seasons & set(FORBIDDEN_SEASONS) or seasons - set(DEVELOPMENT_SEASONS):
        raise PossessionMaterializerError(
            "population contains a forbidden or non-development season"
        )
    # The stream builder does not filter the adjustment iteration; leftover iteration-0
    # rows would silently overwrite the iteration-four values, so filter and assert here.
    for label, frame in (("snapshots", snapshots), ("terminal", terminal)):
        if "adjustment_iteration" not in frame.columns:
            raise PossessionMaterializerError(f"{label} lack adjustment_iteration")
    snapshots = snapshots[
        snapshots["adjustment_iteration"].eq(4)
        & snapshots["measurement_id"].isin(ADJUSTED_MEASUREMENTS)
    ]
    if not terminal["adjustment_iteration"].eq(4).all():
        raise PossessionMaterializerError("terminal rows must all be iteration four")
    observations = observations[
        observations["measurement_id"].isin(ADJUSTED_MEASUREMENTS)
    ]
    if population.duplicated(["game_id"]).any():
        raise PossessionMaterializerError(
            "rating streams require globally unique game ids"
        )

    inputs = RatingTournamentInputs(
        population=population,
        observations=observations,
        snapshots=snapshots,
        terminal=terminal,
        outcomes=pd.DataFrame(),
        context={},
        history_audit={},
        source_refs={},
        population_sha256="",
    )
    boundaries = build_boundary_table(population)
    terminal_tables = build_terminal_tables(terminal)
    streams = build_observation_streams(
        inputs=inputs, boundaries=boundaries, terminal_tables=terminal_tables
    )
    priors = build_prior_tables(context={}, terminal_tables=terminal_tables)
    prior_rows = priors[(definition, family)]
    state_partitions, team_partitions = _replay_candidate_states(
        candidate=candidate_id,
        definition=definition,
        family=family,
        updater=updater,
        prior_rows=prior_rows,
        streams=streams,
        population=population,
        terminal_tables=terminal_tables,
        noise={},
        fbs=_fbs_universe(population),
    )
    prior_frame = prior_rows.assign(candidate_id=candidate_id)[list(PRIOR_COLUMNS)]
    result = SelectedDesignFrames(
        candidate_id=candidate_id,
        priors=prior_frame.sort_values(
            ["season", "unit_role", "team"], kind="mergesort"
        ).reset_index(drop=True),
        rating_states=_records(state_partitions, RATING_STATE_COLUMNS),
        team_states=_records(team_partitions, TEAM_STATE_COLUMNS),
        terminal_tables=dict(terminal_tables),
    )
    eligible = int(population["forecast_eligible"].sum())
    if (
        len(result.team_states) != 2 * eligible
        or len(result.rating_states) != len(ROLES) * 2 * eligible
    ):
        raise PossessionMaterializerError(
            "state row counts do not match the forecast-eligible games"
        )
    return result
