"""Immutable V4 feature-reference and source-family eligibility tests."""

from __future__ import annotations

from pathlib import Path
from runpy import run_path

import pandas as pd

from cks_picks_cfb.models.v4_feature_variants import additive_feature_variants


def _reference_module():
    return run_path(
        str(
            Path(__file__).resolve().parents[1]
            / "scripts/pipeline/build_v4_preseason_feature_reference.py"
        )
    )


def _evaluator_module():
    return run_path(
        str(
            Path(__file__).resolve().parents[1]
            / "scripts/pipeline/evaluate_game_ordinal_predictions.py"
        )
    )


def test_feature_variants_are_additive_and_exclude_an_incomplete_family():
    frame = pd.DataFrame(
        {
            "prior_season_gap": [1.0, 1.0],
            "home_neutral_site": [0.0, 1.0],
            "home_conference_game": [1.0, 0.0],
            "home_return_total_ppa": [0.4, 0.5],
            "away_return_total_ppa": [0.3, 0.2],
            "home_talent": [900.0, None],
            "away_talent": [800.0, 700.0],
        }
    )
    variants = additive_feature_variants(
        frame,
        family_order=("prior_core", "returning_production", "talent"),
        context_features=(
            "prior_season_gap",
            "home_neutral_site",
            "home_conference_game",
        ),
    )
    assert list(variants) == ["prior_core", "returning_production"]
    assert variants["returning_production"][-2:] == [
        "home_return_total_ppa",
        "away_return_total_ppa",
    ]


def test_strict_source_requires_pre_kickoff_effective_time_and_full_coverage():
    module = _reference_module()
    family_frame = module["_family_frame"]
    features = module["FAMILY_FEATURES"]["returning_production"]
    universe = pd.DataFrame(
        {
            "season": [2021, 2021],
            "team": ["Alpha", "Beta"],
            "season_first_kickoff_utc": pd.to_datetime(
                ["2021-08-28T00:00:00Z", "2021-08-28T00:00:00Z"]
            ),
        }
    )
    rows = []
    for team in ("Alpha", "Beta"):
        rows.append(
            {
                "season": 2021,
                "team": team,
                "effective_at": "2021-08-01T00:00:00Z",
                "retrieved_at": "2026-08-17T00:00:00Z",
                **{feature: 1.0 for feature in features},
            }
        )
    strict, metadata = family_frame(
        pd.DataFrame(rows),
        universe=universe,
        family="returning_production",
        strict=True,
    )
    assert metadata["eligible"] is True
    assert strict is not None and len(strict) == 2

    late = pd.DataFrame(rows)
    late.loc[0, "effective_at"] = "2021-09-01T00:00:00Z"
    strict, metadata = family_frame(
        late, universe=universe, family="returning_production", strict=True
    )
    assert strict is None
    assert metadata["reason"] == "effective_at is not before season first kickoff"

    reconstructed, metadata = family_frame(
        late, universe=universe, family="returning_production", strict=False
    )
    assert metadata["eligible"] is True
    assert reconstructed is not None


def test_family_frame_joins_project_team_aliases():
    module = _reference_module()
    family_frame = module["_family_frame"]
    features = module["FAMILY_FEATURES"]["returning_production"]
    universe = pd.DataFrame(
        {
            "season": [2021],
            "team": ["Appalachian State"],
            "season_first_kickoff_utc": pd.to_datetime(["2021-09-01T00:00:00Z"]),
        }
    )
    source = pd.DataFrame(
        {
            "season": [2021],
            "team": ["App State"],
            "effective_at": ["2021-08-01T00:00:00Z"],
            "retrieved_at": ["2021-08-02T00:00:00Z"],
            **{feature: [1.0] for feature in features},
        }
    )

    result, metadata = family_frame(
        source, universe=universe, family="returning_production", strict=False
    )

    assert metadata["eligible"] is True
    assert result is not None
    assert result["team"].tolist() == ["Appalachian State"]


def test_reconstructed_returning_production_allows_only_declared_absences():
    module = _reference_module()
    family_frame = module["_family_frame"]
    exceptions = sorted(
        module["DECLARED_RECONSTRUCTED_CONTEXT_ABSENCES"]["returning_production"]
    )
    features = module["FAMILY_FEATURES"]["returning_production"]
    universe = pd.DataFrame(
        {
            "season": [season for season, _ in exceptions],
            "team": [team for _, team in exceptions],
            "season_first_kickoff_utc": pd.to_datetime(
                ["2021-09-01T00:00:00Z"] * len(exceptions)
            ),
        }
    )
    source = pd.DataFrame(
        columns=["season", "team", "effective_at", "retrieved_at", *features]
    )

    result, metadata = family_frame(
        source, universe=universe, family="returning_production", strict=False
    )

    assert metadata["eligible"] is True
    assert metadata["complete_coverage"] is False
    assert len(metadata["structural_absences"]) == len(exceptions)
    assert result is not None
    assert result["returning_production_available"].eq(0).all()


def test_reconstructed_recruiting_allows_declared_provider_gap():
    module = _reference_module()
    family_frame = module["_family_frame"]
    features = module["FAMILY_FEATURES"]["recruiting"]
    universe = pd.DataFrame(
        {
            "season": [2022],
            "team": ["Florida International"],
            "season_first_kickoff_utc": pd.to_datetime(["2022-09-01T00:00:00Z"]),
        }
    )
    source = pd.DataFrame(
        columns=["season", "team", "effective_at", "retrieved_at", *features]
    )

    result, metadata = family_frame(
        source, universe=universe, family="recruiting", strict=False
    )

    assert metadata["eligible"] is True
    assert metadata["structural_absences"] == [
        {
            "season": 2022,
            "team": "Florida International",
            "reason": "source_unavailable",
        }
    ]
    assert result is not None
    assert result["recruiting_available"].eq(0).all()


def test_reconstructed_returning_production_rejects_an_undeclared_gap():
    module = _reference_module()
    family_frame = module["_family_frame"]
    features = module["FAMILY_FEATURES"]["returning_production"]
    universe = pd.DataFrame(
        {
            "season": [2021],
            "team": ["Unexpected Gap"],
            "season_first_kickoff_utc": pd.to_datetime(["2021-09-01T00:00:00Z"]),
        }
    )
    source = pd.DataFrame(
        columns=["season", "team", "effective_at", "retrieved_at", *features]
    )

    result, metadata = family_frame(
        source, universe=universe, family="returning_production", strict=False
    )

    assert result is None
    assert metadata["eligible"] is False
    assert metadata["reason"] == "incomplete team-season feature coverage"


def test_model_ready_attachment_uses_canonical_join_keys():
    module = run_path(
        str(
            Path(__file__).resolve().parents[1]
            / "scripts/pipeline/assemble_model_ready_features.py"
        )
    )
    core = pd.DataFrame(
        {
            "season": [2021],
            "game_id": [1],
            "home_team": ["App State"],
            "away_team": ["UConn"],
        }
    )
    preseason = pd.DataFrame(
        {
            "season": [2021, 2021],
            "team": ["Appalachian State", "Connecticut"],
            "coach_tenure": [3.0, 4.0],
        }
    )

    result = module["_attach_preseason_features"](core, preseason, ["coach_tenure"])

    assert result["home_team"].tolist() == ["App State"]
    assert result["away_team"].tolist() == ["UConn"]
    assert result["home_coach_tenure"].tolist() == [3.0]
    assert result["away_coach_tenure"].tolist() == [4.0]


def test_route_report_freezes_the_selected_feature_variant():
    module = _evaluator_module()
    rows = []
    for index in range(180):
        actual = float(index % 13)
        for variant, error in (("prior_core", 2.0), ("returning_production", 0.0)):
            rows.append(
                {
                    "season": 2022 + index % 3,
                    "target": "spread",
                    "regime": "game_1",
                    "actual": actual,
                    "baseline_prediction": actual + 3.0,
                    "direct_ridge_prediction": actual + error,
                    "feature_variant": variant,
                    "prior_strengths_json": '{"drives":20,"games":4,"plays":100}',
                }
            )
    reports = module["_candidate_reports"](
        pd.DataFrame(rows), target="spread", regime="game_1", bootstrap=20
    )
    assert reports["direct_ridge"]["selected_feature_variant"] == "returning_production"
