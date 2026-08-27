"""Sealed R2–R4 successor-v2 tournament mechanics tests."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.data.season_lineage import load_season_lineage_policy
from cks_picks_cfb.ratings.successor_tournaments import (
    SuccessorTournamentError,
    candidate_v2_gate,
    load_tournament_configs,
    select_from_fold_metrics,
)

POLICY = load_season_lineage_policy("conf/ratings/successor_v2_season_lineage.yaml")
CONFIGS = load_tournament_configs("conf/ratings/successor_v2_tournaments.yaml")


def _results(stage: str) -> pd.DataFrame:
    config = CONFIGS[stage]
    return pd.DataFrame(
        [
            {
                "candidate_id": candidate.candidate_id,
                "season": season,
                "early_margin_mae": 10.0 + candidate.complexity * 0.01,
                "early_total_mae": 12.0 + candidate.complexity * 0.01,
                "full_margin_mae": 11.0 + candidate.complexity * 0.01,
                "full_total_mae": 13.0 + candidate.complexity * 0.01,
            }
            for candidate in config.candidates
            if not candidate.requires_admitted_context
            for season in (
                POLICY.prior_selection_target_seasons
                if stage == "between_season"
                else POLICY.update_selection_target_seasons
            )
        ]
    )


def test_config_seals_all_candidate_rosters_and_tie_uses_simplicity():
    assert set(CONFIGS) == {"between_season", "within_season", "structured_predictor"}
    selected = select_from_fold_metrics(
        _results("between_season"), policy=POLICY, config=CONFIGS["between_season"]
    )
    assert selected["winner"] == "neutral_population"


def test_context_candidates_are_absent_unless_admitted_and_folds_fail_closed():
    results = _results("between_season")
    with pytest.raises(SuccessorTournamentError, match="coverage"):
        select_from_fold_metrics(
            results.iloc[:-1], policy=POLICY, config=CONFIGS["between_season"]
        )

    continuity_rows = pd.DataFrame(
        [
            {
                "candidate_id": candidate.candidate_id,
                "season": season,
                "early_margin_mae": 8.0
                if candidate.candidate_id == "continuity_ridge_alpha_1"
                else 9.0,
                "early_total_mae": 10.0
                if candidate.candidate_id == "continuity_ridge_alpha_1"
                else 11.0,
                "full_margin_mae": 9.0
                if candidate.candidate_id == "continuity_ridge_alpha_1"
                else 10.0,
                "full_total_mae": 11.0
                if candidate.candidate_id == "continuity_ridge_alpha_1"
                else 12.0,
            }
            for candidate in CONFIGS["between_season"].candidates
            if candidate.requires_admitted_context
            for season in POLICY.prior_selection_target_seasons
        ]
    )
    with pytest.raises(SuccessorTournamentError, match="coverage"):
        select_from_fold_metrics(
            pd.concat([results, continuity_rows]),
            policy=POLICY,
            config=CONFIGS["between_season"],
        )
    selected = select_from_fold_metrics(
        pd.concat([results, continuity_rows]),
        policy=POLICY,
        config=CONFIGS["between_season"],
        admitted_context_families=("continuity",),
    )
    assert selected["winner"] == "continuity_ridge_alpha_1"


def test_candidate_v2_gate_requires_negative_early_upper_and_locked_2025():
    rows = []
    for game_id in range(100):
        for target in ("margin", "total"):
            rows.append(
                {
                    "season": 2024,
                    "game_id": game_id,
                    "target": target,
                    "completed_games": (game_id % 3) + 1,
                    "actual": 0.0,
                    "candidate_v1_prediction": 10.0,
                    "candidate_v2_prediction": 1.0,
                }
            )
    gated = candidate_v2_gate(
        pd.DataFrame(rows), locked_2025_passed=True, existing_quality_gates_passed=True
    )
    assert gated["all_checks_passed"] is True

    locked_failed = candidate_v2_gate(
        pd.DataFrame(rows), locked_2025_passed=False, existing_quality_gates_passed=True
    )
    assert locked_failed["all_checks_passed"] is False
