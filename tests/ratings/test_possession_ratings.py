"""Focused V5-03 chronological rating and selection contracts."""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    PossessionRatingContractError,
    candidate_id,
    candidate_registry,
    rating_identity,
    validate_config,
)
from cks_picks_cfb.ratings import possession_rating_tournament as tournament
from cks_picks_cfb.ratings.possession_ratings import (
    RatingPrior,
    analytic_update,
    carryover_prior,
    kalman_step,
    recency_observation,
    replay_states,
)

ROOT = Path(__file__).resolve().parents[2]


def test_sealed_registry_has_every_definition_prior_and_updater():
    config = yaml.safe_load(
        (
            ROOT / "conf/research/data_first_football_v1/possession_rating_v1.yaml"
        ).read_text()
    )
    validate_config(config)
    registry = candidate_registry()
    assert len(registry) == 60
    assert {row["candidate_id"] for row in registry} == set(config["candidates"])
    changed = dict(config)
    changed["candidates"] = changed["candidates"][:-1]
    with pytest.raises(PossessionRatingContractError, match="registry"):
        validate_config(changed)


def test_identity_binds_both_immutable_parents_and_preview_only_contract():
    first = rating_identity(
        run_id="r",
        as_of="2026-09-16T00:00:00Z",
        code_sha="a",
        config_sha="b",
        measurement_manifest_uri="m",
        measurement_manifest_raw_sha256="c",
        repair_manifest_uri="r",
        repair_manifest_raw_sha256="d",
    )
    second = rating_identity(
        run_id="r",
        as_of="2026-09-17T00:00:00Z",
        code_sha="a",
        config_sha="b",
        measurement_manifest_uri="m",
        measurement_manifest_raw_sha256="c",
        repair_manifest_uri="r",
        repair_manifest_raw_sha256="d",
    )
    assert first["identity_sha256"] != second["identity_sha256"]


def test_carryover_gap_and_analytic_precision_use_possessions_not_games():
    previous = RatingPrior(2.0, 0.25, "terminal", 2019)
    prior = carryover_prior(previous, gap=2)
    assert prior.mean == pytest.approx(0.72)
    assert prior.variance == pytest.approx(0.0 + 1 - 0.60**4 + 0.60**4 * 0.25)
    state = analytic_update(RatingPrior(0.0, 0.25, "x", 2024), 2.0, 8.0, k=8.0)
    assert state.mean == pytest.approx(2 / 5)
    assert state.variance == pytest.approx(0.2)
    assert state.evidence_weight == pytest.approx(0.2)


def test_recency_weights_numerator_and_denominator_and_kalman_advances_bye():
    history = pd.DataFrame({"adjusted_z": [0.0, 2.0], "usable_exposure": [8.0, 8.0]})
    value, exposure = recency_observation(history, half_life=2)
    assert value == pytest.approx(2 / (1 + 2**-0.5))
    assert exposure == pytest.approx(8 * (1 + 2**-0.5))
    state = analytic_update(RatingPrior(0.0, 1.0, "x", None), None, 0.0, k=8.0)
    advanced = kalman_step(
        state, observation=None, exposure=0.0, elapsed_days=14, q=0.1, r=1.0
    )
    assert advanced.mean == 0.0
    assert advanced.variance == pytest.approx(1.2)


def test_replay_uses_each_observation_once_and_excludes_same_game_cutoff():
    observations = pd.DataFrame(
        {
            "game_id": [1, 2],
            "kickoff_utc": ["2025-09-01T00:00:00Z", "2025-09-08T00:00:00Z"],
            "adjusted_z": [1.0, 100.0],
            "usable_exposure": [8.0, 8.0],
        }
    )
    state = replay_states(
        prior=RatingPrior(0.0, 1.0, "x", None),
        observations=observations,
        updater="exposure",
        definition="ppp",
        cutoff="2025-09-08T00:00:00Z",
    )
    assert state.mean == pytest.approx(0.5)
    assert state.completed_games == 1


def test_selection_prefers_ppp_without_admissible_epa_gain(monkeypatch):
    monkeypatch.setattr(
        tournament,
        "_bootstrap",
        lambda candidate, reference, **_: (1.0, 1.0, 1.0)
        if not candidate["candidate_id"].eq(reference["candidate_id"].iloc[0]).all()
        else (0.0, 0.0, 0.0),
    )
    rows = []
    for item in candidate_registry():
        for target in ("margin", "total"):
            for stage in range(5):
                error = 10.0
                if item["candidate_id"] == candidate_id("ppp", "rho_0_60", "exposure"):
                    error = 9.8
                if item["candidate_id"] == candidate_id(
                    "epa_per_possession", "rho_0_60", "exposure"
                ):
                    error = 9.79
                rows.append(
                    {
                        "candidate_id": item["candidate_id"],
                        "definition": item["definition"],
                        "season": 2024,
                        "week": stage + 1,
                        "game_id": stage + 1,
                        "target": target,
                        "absolute_error": error,
                        "completed_game_stage": stage,
                    }
                )
    result = tournament.select_candidates(pd.DataFrame(rows))
    assert result.loc[result["selected"], "candidate_id"].item() == candidate_id(
        "ppp", "rho_0_60", "exposure"
    )
