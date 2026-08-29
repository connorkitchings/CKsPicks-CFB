"""Expanded successor-v2 history and preseason-context contract tests."""

from __future__ import annotations

import pytest

from cks_picks_cfb.data.lake import DatasetRef
from cks_picks_cfb.data.season_lineage import load_season_lineage_policy
from cks_picks_cfb.ratings.context_admission import (
    ContextFamilyEvidence,
    evaluate_context_family,
)
from cks_picks_cfb.ratings.successor_history import (
    R1_REQUIRED_DATASETS,
    REQUIRED_DATASETS,
    SeasonCoverageEvidence,
    SuccessorHistoryError,
    coverage_report,
    derived_history_dataset_refs,
    derived_history_ref_set,
    expanded_history_ref_set,
)

POLICY = load_season_lineage_policy("conf/ratings/successor_v2_season_lineage.yaml")


def _evidence(season: int) -> SeasonCoverageEvidence:
    return SeasonCoverageEvidence(season, 100, 95, 94, 190, 200, True)


def test_history_coverage_requires_all_seasons_and_three_legacy_passes():
    report = coverage_report(
        POLICY, [_evidence(year) for year in POLICY.historical_development_seasons]
    )

    assert report["tournaments_permitted"] is True
    assert report["eligible_2015_2019_seasons"] == [2015, 2016, 2017, 2018, 2019]

    incomplete = coverage_report(
        POLICY, [_evidence(year) for year in (2015, 2016, 2017)]
    )
    assert incomplete["at_least_three_legacy_seasons_eligible"] is True
    assert incomplete["tournaments_permitted"] is False


def test_history_coverage_rejects_2020_and_subthreshold_reconciliation():
    with pytest.raises(Exception, match="forbidden"):
        coverage_report(POLICY, [_evidence(2020)])

    report = coverage_report(
        POLICY,
        [
            SeasonCoverageEvidence(
                year, 100, 95, 93 if year == 2015 else 94, 190, 200, True
            )
            for year in POLICY.historical_development_seasons
        ],
    )
    assert report["seasons"][0]["eligible"] is False
    assert report["tournaments_permitted"] is False


def test_history_ref_set_requires_exact_successor_scope_and_is_deterministic():
    refs = {
        (season, dataset): DatasetRef(
            dataset=dataset,
            version_id=f"{dataset}-{season}",
            schema_version="v1",
            content_sha=f"sha-{dataset}-{season}",
            uri=f"lake/silver/{dataset}/{season}",
        )
        for season in POLICY.historical_development_seasons
        for dataset in REQUIRED_DATASETS
    }
    first = expanded_history_ref_set(POLICY, refs)
    second = expanded_history_ref_set(POLICY, refs)
    assert first["ref_set_sha256"] == second["ref_set_sha256"]

    refs.pop((2015, "plays"))
    with pytest.raises(SuccessorHistoryError, match="missing"):
        expanded_history_ref_set(POLICY, refs)


def test_r1_derived_ref_set_binds_every_source_and_silver_output():
    refs = {
        (season, dataset): DatasetRef(
            dataset=dataset,
            version_id=f"{dataset}-{season}",
            schema_version="v1",
            content_sha=f"sha-{dataset}-{season}",
            uri=f"lake/silver/{dataset}/{season}",
        )
        for season in POLICY.historical_development_seasons
        for dataset in R1_REQUIRED_DATASETS
    }
    first = derived_history_ref_set(
        POLICY,
        refs,
        source_set_uri="artifacts/research/rating-successor-v2/r1/run/source-set.json",
        source_set_sha256="source-sha",
        identity={"pipeline_id": "run"},
    )
    second = derived_history_ref_set(
        POLICY,
        refs,
        source_set_uri="artifacts/research/rating-successor-v2/r1/run/source-set.json",
        source_set_sha256="source-sha",
        identity={"pipeline_id": "run"},
    )
    assert first["ref_set_sha256"] == second["ref_set_sha256"]
    assert len(first["entries"]) == len(POLICY.historical_development_seasons) * len(
        R1_REQUIRED_DATASETS
    )

    refs.pop((2015, "drives"))
    with pytest.raises(SuccessorHistoryError, match="missing"):
        derived_history_ref_set(
            POLICY,
            refs,
            source_set_uri="artifacts/research/rating-successor-v2/r1/run/source-set.json",
            source_set_sha256="source-sha",
            identity={"pipeline_id": "run"},
        )


def test_derived_ref_set_entries_round_trip_through_the_scope_aware_parser():
    refs = {
        (season, dataset): DatasetRef(
            dataset=dataset,
            version_id=f"{dataset}-{season}",
            schema_version="v1",
            content_sha=f"sha-{dataset}-{season}",
            uri=f"lake/silver/{dataset}/{season}",
        )
        for season in POLICY.historical_development_seasons
        for dataset in R1_REQUIRED_DATASETS
    }
    payload = derived_history_ref_set(
        POLICY,
        refs,
        source_set_uri="artifacts/research/rating-successor-v2/r1/run/source-set.json",
        source_set_sha256="source-sha",
        identity={"pipeline_id": "run"},
    )
    assert derived_history_dataset_refs(payload) == refs

    payload["entries"] = "not-a-list"
    with pytest.raises(SuccessorHistoryError, match="entries are invalid"):
        derived_history_dataset_refs(payload)

    payload["entries"] = [{"season": 2015, "dataset": "plays"}]
    with pytest.raises(SuccessorHistoryError, match="immutable dataset fields"):
        derived_history_dataset_refs(payload)


def test_context_admission_fails_closed_for_market_or_missing_authentic_capture():
    coverage = {
        season: 0.95 for season in (*POLICY.prior_selection_target_seasons, 2025)
    }
    admitted = evaluate_context_family(
        POLICY,
        ContextFamilyEvidence(
            "returning_production", True, True, True, coverage, ("returning_yards",)
        ),
    )
    assert admitted["admitted"] is True

    rejected = evaluate_context_family(
        POLICY,
        ContextFamilyEvidence(
            "market_proxy", True, True, False, coverage, ("opening_spread",)
        ),
    )
    assert rejected["admitted"] is False
    assert rejected["checks"]["football_only"] is False
