from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.data_first_repair_v2 import (
    RepairV2Error,
    assemble_auxiliary,
    build_team_universe,
    coverage_and_admission,
    normalize_coaching_v2,
    normalize_recruiting_v2,
    normalize_returning_production_v2,
    normalize_roster_continuity_v2,
    reconcile_population,
    verify_parent,
)
from scripts.research.verify_data_first_repair_v2 import _frame_digest


def _schedule() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": [2019, 2019, 2021],
            "week": [1, 2, 1],
            "game_id": [1, 2, 3],
            "kickoff_utc": [
                "2019-08-31T12:00:00Z",
                "2019-09-07T12:00:00Z",
                "2021-09-04T12:00:00Z",
            ],
            "home_team": ["Alabama", "Auburn", "Alabama"],
            "away_team": ["Auburn", "Alabama", "Auburn"],
            "home_classification": ["fbs", "fbs", "fbs"],
            "away_classification": ["fbs", "fbs", "fbs"],
            "completed": [True, True, False],
        }
    )


def test_population_keeps_completed_game_without_measurements() -> None:
    population, issues = reconcile_population(
        schedule=_schedule(),
        outcomes=pd.DataFrame(
            {
                "season": [2019, 2019, 2021],
                "game_id": [1, 2, 3],
                "completed": [True, True, False],
                "home_points": [21, 24, np.nan],
                "away_points": [17, 20, np.nan],
            }
        ),
        observed_games=pd.DataFrame({"season": [2019], "game_id": [1]}),
        reconciliation=pd.DataFrame(
            {
                "season": [2019, 2019, 2021],
                "game_id": [1, 2, 3],
                "classification": [
                    "exact_match",
                    "incomplete_source",
                    "incomplete_source",
                ],
            }
        ),
        omissions={"plays": [{"season": 2019, "game_id": 2}]},
    )
    second = population.set_index("game_id").loc[2]
    assert bool(second.forecast_eligible)
    assert not bool(second.measurement_usable)
    assert int(second.measurement_exposure) == 0
    assert second.disposition == "eligible_without_measurements"
    third = population.set_index("game_id").loc[3]
    assert not bool(third.forecast_eligible)
    assert len(issues) == 2


def test_verifier_digest_normalizes_nullable_game_key_representation() -> None:
    expected = pd.DataFrame({"game_id": [400944873, None], "details": ["x", None]})
    stored = pd.DataFrame(
        {"game_id": [400944873.0, float("nan")], "details": ["x", None]}
    )
    assert _frame_digest(expected) == _frame_digest(stored)


def test_population_rejects_duplicate_schedule_key() -> None:
    schedule = pd.concat([_schedule(), _schedule().iloc[[0]]], ignore_index=True)
    with pytest.raises(RepairV2Error, match="repeats a game key"):
        reconcile_population(
            schedule=schedule,
            outcomes=pd.DataFrame(
                {
                    "season": [],
                    "game_id": [],
                    "completed": [],
                    "home_points": [],
                    "away_points": [],
                }
            ),
            observed_games=pd.DataFrame({"season": [], "game_id": []}),
            reconciliation=pd.DataFrame(
                {"season": [], "game_id": [], "classification": []}
            ),
            omissions={},
        )


def test_universe_excludes_non_fbs_and_2020() -> None:
    universe = build_team_universe(_schedule())
    assert set(universe.team) == {"Alabama", "Auburn"}
    bad = _schedule().copy()
    bad.loc[0, "season"] = 2020
    with pytest.raises(RepairV2Error, match="impermissible"):
        build_team_universe(bad)


def test_recruiting_keeps_partial_and_2020_windows_explicit() -> None:
    universe = pd.DataFrame({"season": [2019, 2021], "team": ["Alabama", "Alabama"]})
    raw = pd.DataFrame(
        {
            "year": [2016, 2017, 2018, 2019, 2021],
            "team": ["Alabama"] * 5,
            "points": [1, 2, 3, 4, 5],
        }
    )
    result, issues = normalize_recruiting_v2(raw, universe)
    by_season = result.set_index("season")
    assert by_season.loc[2019, "recruiting_strict_four_class_average_points"] == 2.5
    assert by_season.loc[2021, "recruiting_available_class_count"] == 3
    assert pd.isna(by_season.loc[2021, "recruiting_strict_four_class_average_points"])
    assert by_season.loc[2021, "missing_reason"] == "forbidden_2020_four_class_window"
    assert issues.empty


def test_returning_production_rejects_domain_and_duplicate_conflict() -> None:
    universe = pd.DataFrame({"season": [2019], "team": ["Alabama"]})
    raw = pd.DataFrame(
        {
            "season": [2019, 2019],
            "team": ["Alabama", "Alabama"],
            "totalPPA": [1.0, 1.1],
            "totalPassingPPA": [1.0, 1.0],
            "totalRushingPPA": [1.0, 1.0],
            "totalReceivingPPA": [1.0, 1.0],
            "percentPPA": [0.5, 0.5],
            "passingUsage": [0.5, 0.5],
            "rushingUsage": [0.5, 0.5],
        }
    )
    result, issues = normalize_returning_production_v2(raw, universe)
    assert result.loc[0, "missing_reason"] == "missing_or_invalid_returning_production"
    assert len(issues) == 1


def test_coaching_filters_future_and_preserves_censoring() -> None:
    universe = pd.DataFrame({"season": [2015, 2021], "team": ["Alabama", "Alabama"]})
    kickoff = pd.DataFrame(
        {
            "season": [2015, 2021],
            "team": ["Alabama", "Alabama"],
            "first_kickoff_utc": ["2015-09-01T00:00:00Z", "2021-09-01T00:00:00Z"],
        }
    )
    raw = pd.DataFrame(
        {
            "firstName": ["Nick"],
            "lastName": ["Saban"],
            "hireDate": ["2007-01-03T00:00:00Z"],
            "seasons": [
                [
                    {"year": 2014, "school": "Alabama"},
                    {"year": 2015, "school": "Alabama"},
                    {"year": 2021, "school": "Alabama"},
                    {"year": 2022, "school": "Alabama"},
                ]
            ],
        }
    )
    result, _ = normalize_coaching_v2(raw, universe, kickoff)
    values = result.set_index("season")
    assert bool(values.loc[2015, "coach_new"]) is False
    assert bool(values.loc[2015, "coach_tenure_censored"])
    assert bool(values.loc[2021, "coach_tenure_censored"])
    assert pd.isna(values.loc[2021, "coach_tenure"])


def test_roster_distinguishes_returns_transfers_and_2021_gap() -> None:
    universe = pd.DataFrame(
        {
            "season": [2016, 2016, 2021],
            "team": ["Alabama", "North Texas", "North Texas"],
        }
    )
    raw = pd.DataFrame(
        {
            "season": [2015, 2015, 2016, 2016, 2019, 2021],
            "id": ["retained", "transfer", "retained", "transfer", "old", "new"],
            "team": [
                "Alabama",
                "Alabama",
                "Alabama",
                "North Texas",
                "North Texas",
                "North Texas",
            ],
            "position": ["DB", "QB", "DB", "QB", "QB", "QB"],
        }
    )
    result, _ = normalize_roster_continuity_v2(raw, universe)
    values = result.set_index(["season", "team"])
    bama = values.loc[(2016, "Alabama")]
    north_texas = values.loc[(2016, "North Texas")]
    assert bama.roster_same_team_return_count == 1
    assert north_texas.roster_incoming_experienced_count == 1
    assert north_texas.roster_incoming_experienced_qb_count == 1
    assert (
        values.loc[(2021, "North Texas")].missing_reason
        == "prior_roster_outside_lineage"
    )


def test_coverage_rejects_constant_family_and_assembly_has_unique_keys() -> None:
    universe = pd.DataFrame({"season": [2019, 2019], "team": ["Alabama", "Auburn"]})
    recruiting = pd.DataFrame(
        {
            "season": [2019, 2019],
            "team": ["Alabama", "Auburn"],
            "recruiting_current_points": [1.0, 2.0],
        }
    )
    returning = pd.DataFrame(
        {
            "season": [2019, 2019],
            "team": ["Alabama", "Auburn"],
            "return_total_ppa": [1.0, 1.0],
        }
    )
    coaching = pd.DataFrame(
        {
            "season": [2019, 2019],
            "team": ["Alabama", "Auburn"],
            "coach_tenure": [1.0, 1.0],
        }
    )
    roster = pd.DataFrame(
        {
            "season": [2019, 2019],
            "team": ["Alabama", "Auburn"],
            "roster_same_team_return_share": [0.4, 0.5],
        }
    )
    auxiliary = assemble_auxiliary(
        universe=universe,
        recruiting=recruiting,
        returning_production=returning,
        coaching=coaching,
        roster_continuity=roster,
        source_capture_ids={},
    )
    coverage, admission = coverage_and_admission(auxiliary)
    assert len(auxiliary) == 8
    assert not admission["returning_production"]["historical_eligible"]
    assert coverage[coverage.slice.eq("return_total_ppa")].constant_warning.all()


def test_parent_verification_rejects_wrong_raw_or_chronology() -> None:
    payload = signed_payload(
        {
            "schema_version": "schema",
            "state": "ready",
            "development_seasons": [
                2015,
                2016,
                2017,
                2018,
                2019,
                2021,
                2022,
                2023,
                2024,
                2025,
            ],
            "forbidden_seasons": [2020],
        }
    )
    raw_sha = hashlib.sha256(b"raw").hexdigest()
    verify_parent(
        payload,
        raw_sha256=raw_sha,
        expected_raw_sha256=raw_sha,
        expected_manifest_sha256=payload["manifest_sha256"],
        schema_version="schema",
        state="ready",
        label="test",
    )
    with pytest.raises(RepairV2Error, match="raw checksum"):
        verify_parent(
            payload,
            raw_sha256="0" * 64,
            expected_raw_sha256=raw_sha,
            expected_manifest_sha256=payload["manifest_sha256"],
            schema_version="schema",
            state="ready",
            label="test",
        )
