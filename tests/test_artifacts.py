"""Tests for operational artifact path conventions."""

from cks_picks_cfb.artifacts import (
    local_prediction_path,
    local_scored_path,
    prediction_artifact_path,
    scored_artifact_path,
    scored_artifact_prefix,
)


def test_prediction_paths_are_explicit():
    assert str(local_prediction_path(2026, 1)) == (
        "data/production/predictions/2026/CFB_week1_bets.csv"
    )
    assert prediction_artifact_path(2026, 1) == (
        "artifacts/production/predictions/year=2026/CFB_week1_bets.csv"
    )


def test_scored_paths_are_explicit():
    assert str(local_scored_path(2026, 1)) == (
        "data/production/scored/2026/CFB_week1_bets_scored.csv"
    )
    assert scored_artifact_path(2026, 1) == (
        "artifacts/production/scored/year=2026/CFB_week1_bets_scored.csv"
    )
    assert scored_artifact_prefix(2026) == "artifacts/production/scored/year=2026/"
