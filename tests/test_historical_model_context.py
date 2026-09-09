import pandas as pd
import pytest

from cks_picks_cfb.models.historical_model_context import (
    HistoricalModelContextError,
    aggregate_periods,
    config_from_mapping,
)


def _config():
    ref = {
        "dataset": "dataset",
        "version_id": "version",
        "schema_version": "v1",
        "content_sha": "a" * 64,
        "uri": "lake/data.parquet",
    }
    return {
        "comparison_season": 2025,
        "model_id": "v4",
        "prediction_ref": ref,
        "feature_ref": ref,
        "market_ref": ref,
        "market_policy_version": "consensus_then_median_v1",
        "timing_class": "historically_reconstructed",
        "usage": "post_phase5_diagnostic_only",
    }


def test_context_config_rejects_non_2025_comparison_season():
    value = _config()
    value["comparison_season"] = 2024
    with pytest.raises(HistoricalModelContextError, match="pinned to 2025"):
        config_from_mapping(value)


def test_aggregate_periods_keeps_pushes_out_of_wins_and_losses():
    comparisons = pd.DataFrame(
        [
            {"week": 1, "target": "spread", "result": "win"},
            {"week": 1, "target": "spread", "result": "push"},
            {"week": 1, "target": "total", "result": "loss"},
            {"week": 1, "target": "total", "result": "win"},
        ]
    ).assign(model_id="v4", comparison_season=2025, calculation_version="v1")
    rows = aggregate_periods(comparisons)
    season = rows[rows["period_scope"].eq("season")].iloc[0]
    assert (
        season["spread_wins"],
        season["spread_losses"],
        season["spread_pushes"],
    ) == (1, 0, 1)
    assert (season["total_wins"], season["total_losses"], season["total_pushes"]) == (
        1,
        1,
        0,
    )
    assert season["spread_compared_games"] == 2
