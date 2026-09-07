from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2e import (
    Phase2eError,
    auxiliary_eligibility_manifest,
    capture_set_manifest,
    normalize_coaching,
    normalize_lagged_rankings,
    normalize_recruiting,
    normalize_roster_continuity,
    validate_capture_inventory,
)


def _inventory():
    rows = []
    for entity, years in {
        "betting_lines": (*range(2015, 2020), *range(2021, 2026)),
        "coaches": (*range(2015, 2020), *range(2021, 2026)),
        "rankings": (*range(2015, 2020), *range(2021, 2026)),
        "rosters": (*range(2015, 2020), *range(2021, 2026)),
        "returning_production": (*range(2015, 2020), *range(2021, 2026)),
        "recruiting": (*range(2012, 2020), *range(2021, 2026)),
    }.items():
        for year in years:
            rows.append(
                {
                    "capture_id": f"{entity}-{year}",
                    "provider": "cfbd",
                    "entity": entity,
                    "season": year,
                    "state": "registered",
                    "effective_at": None,
                    "timing_class": "historically_reconstructed",
                    "row_count": 1,
                    "content_sha": "a" * 64,
                    "object_sha": "b" * 64,
                }
            )
    return rows


def test_capture_inventory_requires_exact_63_matrix():
    manifest = capture_set_manifest(_inventory())
    assert len(manifest["captures"]) == 63
    with pytest.raises(Phase2eError, match="duplicate"):
        validate_capture_inventory([*_inventory(), _inventory()[0]])


def test_recruiting_requires_four_complete_class_rows():
    universe = pd.DataFrame({"season": [2015], "team": ["A"]})
    raw = pd.DataFrame(
        {"year": [2012, 2013, 2014, 2015], "team": ["A"] * 4, "points": [1, 2, 3, 4]}
    )
    result = normalize_recruiting(raw, universe)
    assert result.loc[0, "recruiting_4yr"] == 2.5
    assert result.loc[0, "recruiting_trend"] == 1.5


def test_recruiting_records_the_forbidden_2020_structural_fallback():
    universe = pd.DataFrame({"season": [2021], "team": ["A"]})
    raw = pd.DataFrame(
        {"year": [2018, 2019, 2021], "team": ["A"] * 3, "points": [1, 2, 4]}
    )
    result = normalize_recruiting(raw, universe)
    assert result.loc[0, "missing_reason"] == "forbidden_2020_four_class_window"


def test_coaching_excludes_ambiguous_assignment_without_outcome_selection():
    universe = pd.DataFrame({"season": [2021], "team": ["A"]})
    raw = pd.DataFrame(
        {
            "season": [2021, 2021],
            "seasons": [
                [{"year": 2021, "school": "A"}],
                [{"year": 2021, "school": "A"}],
            ],
        }
    )
    result = normalize_coaching(raw, universe)
    assert result.loc[0, "missing_reason"] == "ambiguous_coach_assignment"


def test_roster_continuity_uses_prior_ids_and_preserves_2021_fallback():
    universe = pd.DataFrame({"season": [2019, 2021, 2022], "team": ["A", "A", "A"]})
    raw = pd.DataFrame(
        {
            "season": [2018, 2018, 2019, 2019, 2021, 2022, 2022],
            "team": ["A"] * 7,
            "id": ["p1", "p2", "p1", "p3", "p3", "p3", "p4"],
            "position": ["QB", "WR", "QB", "WR", "WR", "WR", "QB"],
        }
    )
    result = normalize_roster_continuity(raw, universe).set_index("season")
    assert result.loc[2019, "roster_returning_share"] == 0.5
    assert result.loc[2019, "roster_returning_qb_count"] == 1
    assert result.loc[2021, "missing_reason"] == "prior_roster_outside_lineage"
    assert result.loc[2022, "roster_returning_share"] == 0.5


def test_rankings_require_strictly_earlier_poll_week_and_unranked_is_26():
    raw = pd.DataFrame(
        {
            "season": [2025, 2025],
            "week": [1, 2],
            "polls": [
                [
                    {"poll": "AP Top 25", "ranks": [{"school": "A", "rank": 4}]},
                    {"poll": "Coaches Poll", "ranks": [{"school": "A", "rank": 5}]},
                ],
                [
                    {"poll": "AP Top 25", "ranks": [{"school": "A", "rank": 3}]},
                    {"poll": "Coaches Poll", "ranks": [{"school": "A", "rank": 4}]},
                ],
            ],
        }
    )
    sides = pd.DataFrame(
        {"season": [2025, 2025], "week": [1, 2], "game_id": [1, 2], "team": ["A", "B"]}
    )
    result = normalize_lagged_rankings(raw, sides).set_index("game_id")
    assert result.loc[1, "missing_reason"] == "no_prior_poll"
    assert result.loc[2, "lagged_ap_rank"] == 26
    assert result.loc[2, "lagged_coaches_rank"] == 26


def test_auxiliary_manifest_rejects_incomplete_context_coverage():
    refs = {
        name: {"dataset": name}
        for name in (
            *(
                "recruiting",
                "returning_production",
                "coaching",
                "roster_continuity",
                "lagged_rankings",
            ),
            "market_references",
        )
    }
    coverage = {
        name: {"minimum_coverage": 1.0} for name in refs if name != "market_references"
    }
    coverage["coaching"] = {"minimum_coverage": 0.89}
    with pytest.raises(Phase2eError, match="coverage"):
        auxiliary_eligibility_manifest(
            capture_set=capture_set_manifest(_inventory()),
            refs=refs,
            coverage=coverage,
            exclusions={},
            code_sha="a",
            as_of="2026-09-06T00:00:00Z",
        )
