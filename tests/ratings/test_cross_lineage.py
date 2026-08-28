"""Cross-lineage hard-gate behavior."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.ratings.cross_lineage import compare_season


def _games_frame(*rows: dict) -> pd.DataFrame:
    base = {"season": 2019, "home_team": "Alpha", "away_team": "Beta"}
    return pd.DataFrame([{**base, **row} for row in rows])


def _outcomes_frame(*rows: dict) -> pd.DataFrame:
    base = {"season": 2019, "completed": True}
    return pd.DataFrame(
        [{**base, "home_points": 24, "away_points": 17, **row} for row in rows]
    )


def _inputs(*, canceled: bool = False, extra_outcome: bool = False) -> dict:
    outcomes_rows = [{"game_id": 1}]
    if canceled:
        outcomes_rows.append(
            {"game_id": 2, "completed": False, "home_points": None, "away_points": None}
        )
    if extra_outcome:
        outcomes_rows.append({"game_id": 3})
    return {
        "games": _games_frame({"game_id": 1}),
        "game_outcomes": _outcomes_frame(*outcomes_rows),
        "teams": pd.DataFrame(
            [{"season": 2019, "school": "Alpha"}, {"season": 2019, "school": "Beta"}]
        ),
    }


def test_cross_lineage_accepts_equal_evidence_and_rejects_hard_conflicts():
    baseline = _inputs()
    assert all(
        compare_season(season=2019, successor=baseline, legacy=_inputs()).values()
    )

    mutated_team = _inputs()
    mutated_team["games"] = _games_frame({"game_id": 1, "home_team": "Gamma"})
    assert not compare_season(season=2019, successor=baseline, legacy=mutated_team)[
        "game_identity_ok"
    ]
    mutated_score = _inputs()
    mutated_score["game_outcomes"] = _outcomes_frame({"game_id": 1, "home_points": 21})
    assert not compare_season(season=2019, successor=baseline, legacy=mutated_score)[
        "scores_ok"
    ]


def test_cross_lineage_accepts_outcomes_superset_and_shared_canceled_game():
    successor = _inputs(canceled=True, extra_outcome=True)
    legacy = _inputs(canceled=True, extra_outcome=True)
    assert all(compare_season(season=2019, successor=successor, legacy=legacy).values())


def test_cross_lineage_rejects_divergent_canceled_game_sets():
    successor = _inputs(canceled=True)
    legacy = _inputs(canceled=False)
    checks = compare_season(season=2019, successor=successor, legacy=legacy)
    assert not checks["scores_ok"]
    assert not checks["season_membership_ok"]


def test_cross_lineage_rejects_outcomes_membership_divergence():
    successor = _inputs(extra_outcome=True)
    legacy = _inputs(extra_outcome=False)
    checks = compare_season(season=2019, successor=successor, legacy=legacy)
    assert not checks["season_membership_ok"]
    assert checks["game_identity_ok"]


def test_cross_lineage_rejects_games_membership_divergence():
    successor = _inputs()
    successor["games"] = _games_frame({"game_id": 1}, {"game_id": 9})
    legacy = _inputs()
    checks = compare_season(season=2019, successor=successor, legacy=legacy)
    assert not checks["season_membership_ok"]
    assert not checks["game_identity_ok"]


def test_cross_lineage_rejects_completed_game_with_missing_scores():
    successor = _inputs()
    successor["game_outcomes"] = _outcomes_frame(
        {"game_id": 1, "completed": True, "home_points": None, "away_points": None}
    )
    with pytest.raises(ValueError, match="completed games with missing scores"):
        compare_season(season=2019, successor=successor, legacy=_inputs())


def test_cross_lineage_rejects_duplicate_outcome_identities():
    successor = _inputs()
    successor["game_outcomes"] = _outcomes_frame({"game_id": 1}, {"game_id": 1})
    with pytest.raises(ValueError, match="duplicate game identity keys"):
        compare_season(season=2019, successor=successor, legacy=_inputs())
