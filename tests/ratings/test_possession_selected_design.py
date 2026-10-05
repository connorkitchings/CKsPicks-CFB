"""The selected-design orchestrator equals the tournament for that candidate."""

from __future__ import annotations

import copy

import pandas as pd
import pytest

from cks_picks_cfb.ratings import possession_rating_materializer as materializer
from cks_picks_cfb.ratings.possession_rating_materializer import compute_tournament
from cks_picks_cfb.ratings.possession_selected_design import (
    SELECTED_CANDIDATE,
    compute_selected_design,
)
from tests.ratings.test_possession_rating_materializer import _fixture, _noop


@pytest.fixture(autouse=True)
def _small_fbs(monkeypatch):
    monkeypatch.setattr(materializer, "FBS_MINIMUM_SCHEDULED_GAMES", 3)


def _design(inputs):
    return compute_selected_design(
        population=inputs.population,
        observations=inputs.observations,
        snapshots=inputs.snapshots,
        terminal=inputs.terminal,
    )


def _same(left: pd.DataFrame, right: pd.DataFrame) -> None:
    keys = [c for c in ("season", "week", "game_id", "team", "unit_role") if c in left]
    a = left.sort_values(keys, kind="mergesort").reset_index(drop=True)
    b = right.sort_values(keys, kind="mergesort").reset_index(drop=True)
    pd.testing.assert_frame_equal(a[list(b.columns)], b, check_dtype=False)


def test_selected_design_equals_the_tournament_candidate():
    inputs = _fixture()
    tournament = compute_tournament(inputs=inputs, progress=_noop, retain_frames=True)
    design = _design(copy.deepcopy(inputs))
    for name, frame in (
        ("team_states", design.team_states),
        ("rating_states", design.rating_states),
        ("priors", design.priors),
    ):
        expected = tournament.frames[name]
        expected = expected[expected["candidate_id"].eq(SELECTED_CANDIDATE)]
        assert len(expected) == len(frame) > 0
        _same(frame, expected)


def test_leftover_iteration_zero_snapshots_cannot_change_the_result():
    inputs = _fixture()
    clean = _design(inputs)
    stale = inputs.snapshots.copy()
    stale["adjustment_iteration"] = 0
    stale["adjusted_value"] = stale["adjusted_value"] + 100.0
    polluted = pd.concat([inputs.snapshots, stale], ignore_index=True)
    result = compute_selected_design(
        population=inputs.population,
        observations=inputs.observations,
        snapshots=polluted,
        terminal=inputs.terminal,
    )
    _same(result.team_states, clean.team_states)


def test_rejects_forbidden_seasons_other_candidates_and_bad_terminal():
    inputs = _fixture()
    with pytest.raises(materializer.PossessionMaterializerError):
        compute_selected_design(
            population=inputs.population.assign(season=2020),
            observations=inputs.observations,
            snapshots=inputs.snapshots,
            terminal=inputs.terminal,
        )
    with pytest.raises(materializer.PossessionMaterializerError):
        compute_selected_design(
            population=inputs.population,
            observations=inputs.observations,
            snapshots=inputs.snapshots,
            terminal=inputs.terminal,
            candidate_id="ppp__rho_0_60__kalman",
        )
    bad_terminal = inputs.terminal.assign(adjustment_iteration=0)
    with pytest.raises(materializer.PossessionMaterializerError):
        compute_selected_design(
            population=inputs.population,
            observations=inputs.observations,
            snapshots=inputs.snapshots,
            terminal=bad_terminal,
        )
