"""Focused V5-05B shadow score and evidence ledger tests."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.forecast.shadow import (
    ShadowError,
    plan_freeze,
    score_freeze,
    update_evidence_counter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _schedule(n: int = 45) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2025,
                "week": 10,
                "game_id": 1000 + i,
                "kickoff_utc": "2025-11-15T16:00:00+00:00",
            }
            for i in range(n)
        ]
    )


def _preds(game_ids: list, mean: float = 5.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"game_id": g, "target": t, "mean": mean}
            for g in game_ids
            for t in ("margin", "total")
        ]
    )


def _base_plan(n: int = 45) -> "tuple":
    game_ids = list(range(1000, 1000 + n))
    freeze_ts = pd.Timestamp("2025-11-15T16:00:00Z") - pd.Timedelta(hours=2)
    freeze_plan = plan_freeze(
        candidate="forecast-v1-20260917-4600ddd-04b",
        season=2025,
        week=10,
        run_id="shadow-v1-test-05b",
        freeze_time=freeze_ts.isoformat(),
        schedule=_schedule(n),
        v5_predictions=_preds(game_ids),
        v4_predictions=_preds(game_ids, mean=4.0),
        v4_ref_uri="artifacts/v4/ref.parquet",
        min_paired_games=40,
        freeze_hard_lead_seconds=3600.0,
    )
    return freeze_plan, game_ids


def _outcomes(
    game_ids: list, last_completion: str = "2025-11-15T23:00:00Z"
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": g,
                "actual_margin": 7.0,
                "actual_total": 48.0,
                "last_completion_time": last_completion,
            }
            for g in game_ids
        ]
    )


def _score_kwargs(
    freeze_plan: object,
    game_ids: list,
    scored_at: str = "2025-11-17T00:00:00Z",
    outcome_version: str = "v1",
    last_completion: str = "2025-11-15T23:00:00Z",
) -> dict:
    return {
        "candidate": freeze_plan.candidate,
        "season": freeze_plan.season,
        "week": freeze_plan.week,
        "run_id": freeze_plan.run_id,
        "freeze_record": freeze_plan.freeze_record,
        "predictions": freeze_plan.predictions,
        "outcomes": _outcomes(game_ids, last_completion=last_completion),
        "outcome_version": outcome_version,
        "scored_at": scored_at,
        "freeze_ref": "artifacts/shadow/freeze-ref",
        "evaluation_ref": "artifacts/shadow/eval-ref",
        "min_stabilization_seconds": 86400.0,
    }


# ---------------------------------------------------------------------------
# 24h stabilization gate
# ---------------------------------------------------------------------------


def test_score_accepts_after_24h():
    fp, ids = _base_plan()
    # last_completion=2025-11-15T23:00Z, scored_at=2025-11-17T00:00Z -> 90000s > 86400
    result = score_freeze(**_score_kwargs(fp, ids))
    assert result.qualifying
    assert result.paired_count == 45


def test_score_rejects_before_24h():
    fp, ids = _base_plan()
    kwargs = _score_kwargs(fp, ids, scored_at="2025-11-16T08:00:00Z")
    # last_completion=2025-11-15T23:00Z, scored_at=2025-11-16T08:00Z -> 32400s < 86400
    with pytest.raises(ShadowError, match="24h"):
        score_freeze(**kwargs)


def test_score_rejects_exactly_at_24h_boundary_minus_one():
    fp, ids = _base_plan()
    # elapsed = exactly 86399s: one second short
    last_completion = pd.Timestamp("2025-11-15T23:00:00Z")
    scored_at = (last_completion + pd.Timedelta(seconds=86399)).isoformat()
    kwargs = _score_kwargs(fp, ids, scored_at=scored_at)
    with pytest.raises(ShadowError, match="24h"):
        score_freeze(**kwargs)


def test_score_rejects_missing_last_completion_time():
    fp, ids = _base_plan()
    kwargs = _score_kwargs(fp, ids)
    # Remove last_completion_time
    kwargs["outcomes"] = _outcomes(ids).drop(columns=["last_completion_time"])
    with pytest.raises(ShadowError, match="last_completion_time"):
        score_freeze(**kwargs)


def test_score_rejects_all_null_completion_times():
    fp, ids = _base_plan()
    kwargs = _score_kwargs(fp, ids)
    outcomes = _outcomes(ids)
    outcomes["last_completion_time"] = None
    kwargs["outcomes"] = outcomes
    with pytest.raises(ShadowError, match="trustworthy completion timestamp"):
        score_freeze(**kwargs)


def test_score_rejects_naive_scored_at():
    fp, ids = _base_plan()
    kwargs = _score_kwargs(fp, ids)
    kwargs["scored_at"] = "2025-11-17T00:00:00"  # naive
    with pytest.raises(ShadowError, match="timezone-aware"):
        score_freeze(**kwargs)


# ---------------------------------------------------------------------------
# Scoring correctness
# ---------------------------------------------------------------------------


def test_score_computes_error_correctly():
    fp, ids = _base_plan()
    # V5 mean=5.0, actual_margin=7.0 -> error=5-7=-2 for margin
    result = score_freeze(**_score_kwargs(fp, ids))
    margin_rows = result.evaluation[result.evaluation["target"] == "margin"]
    assert margin_rows["error"].sub(-2.0).abs().lt(1e-6).all()


def test_score_mae_margin_and_total():
    fp, ids = _base_plan()
    result = score_freeze(**_score_kwargs(fp, ids))
    # all margin errors = -2, all total errors = 5-48 = -43
    assert result.mae_margin == pytest.approx(2.0)
    assert result.mae_total == pytest.approx(43.0)


def test_score_evaluation_has_required_columns():
    from cks_picks_cfb.data.data_first_shadow_v1 import SHADOW_EVALUATION_COLUMNS

    fp, ids = _base_plan()
    result = score_freeze(**_score_kwargs(fp, ids))
    assert set(SHADOW_EVALUATION_COLUMNS) <= set(result.evaluation.columns)


def test_score_counter_has_required_columns():
    from cks_picks_cfb.data.data_first_shadow_v1 import EVIDENCE_COUNTER_COLUMNS

    fp, ids = _base_plan()
    result = score_freeze(**_score_kwargs(fp, ids))
    assert set(EVIDENCE_COUNTER_COLUMNS) <= set(result.counter_record.columns)
    assert len(result.counter_record) == 1


def test_score_qualifying_is_true_for_45_paired_games():
    fp, ids = _base_plan(n=45)
    result = score_freeze(**_score_kwargs(fp, ids))
    assert result.qualifying is True
    assert result.reason == "normal_coverage"


def test_score_nonqualifying_for_small_slate():
    fp, ids = _base_plan(n=40)
    # Reduce outcomes to only 20 games -> paired < 40
    kwargs = _score_kwargs(fp, ids)
    partial_ids = ids[:20]
    kwargs["outcomes"] = _outcomes(partial_ids)
    result = score_freeze(**kwargs)
    assert result.qualifying is False
    assert "paired" in result.reason


# ---------------------------------------------------------------------------
# Corrections and versioning
# ---------------------------------------------------------------------------


def test_score_correction_creates_new_outcome_version():
    fp, ids = _base_plan()
    result_v1 = score_freeze(**_score_kwargs(fp, ids, outcome_version="v1"))
    result_v2 = score_freeze(**_score_kwargs(fp, ids, outcome_version="v2"))
    assert result_v1.outcome_version == "v1"
    assert result_v2.outcome_version == "v2"
    # Both reference the same freeze but different evaluation versions
    assert result_v1.evaluation["outcome_version"].eq("v1").all()
    assert result_v2.evaluation["outcome_version"].eq("v2").all()


def test_score_correction_does_not_double_count():
    """Two outcome versions for the same slate count only once."""
    fp, ids = _base_plan()
    r1 = score_freeze(**_score_kwargs(fp, ids, outcome_version="v1"))
    r2 = score_freeze(**_score_kwargs(fp, ids, outcome_version="v2"))

    # Start with empty counter
    empty = pd.DataFrame(columns=list(r1.counter_record.columns))
    counter1, count1 = update_evidence_counter(
        empty,
        r1.counter_record,
        candidate=fp.candidate,
        season=fp.season,
        week=fp.week,
    )
    assert count1 == 1

    # Adding a correction for the same slate must not increment count
    counter2, count2 = update_evidence_counter(
        counter1,
        r2.counter_record,
        candidate=fp.candidate,
        season=fp.season,
        week=fp.week,
    )
    assert count2 == 1  # still 1 — no double-count
    assert len(counter2) == 2  # but ledger has both rows


def test_score_different_weeks_count_separately():
    """Two different weeks count separately in the evidence counter."""
    fp10, ids10 = _base_plan()
    # Create a second freeze plan for week 11
    game_ids11 = list(range(2000, 2045))
    freeze_ts = pd.Timestamp("2025-11-22T16:00:00Z") - pd.Timedelta(hours=2)
    fp11 = plan_freeze(
        candidate="forecast-v1-20260917-4600ddd-04b",
        season=2025,
        week=11,
        run_id="shadow-v1-test-05b-w11",
        freeze_time=freeze_ts.isoformat(),
        schedule=pd.DataFrame(
            [
                {
                    "season": 2025,
                    "week": 11,
                    "game_id": g,
                    "kickoff_utc": "2025-11-22T16:00:00+00:00",
                }
                for g in game_ids11
            ]
        ),
        v5_predictions=_preds(game_ids11),
        v4_predictions=_preds(game_ids11, mean=4.0),
        v4_ref_uri="artifacts/v4/week11/ref.parquet",
        min_paired_games=40,
        freeze_hard_lead_seconds=3600.0,
    )

    r10 = score_freeze(**_score_kwargs(fp10, ids10, scored_at="2025-11-17T00:00:00Z"))
    r11 = score_freeze(
        candidate=fp11.candidate,
        season=fp11.season,
        week=fp11.week,
        run_id=fp11.run_id,
        freeze_record=fp11.freeze_record,
        predictions=fp11.predictions,
        outcomes=_outcomes(game_ids11, last_completion="2025-11-22T23:00:00Z"),
        outcome_version="v1",
        scored_at="2025-11-24T00:00:00Z",
        freeze_ref="",
        evaluation_ref="",
        min_stabilization_seconds=86400.0,
    )

    empty = pd.DataFrame(columns=list(r10.counter_record.columns))
    counter, count = update_evidence_counter(
        empty,
        r10.counter_record,
        candidate=fp10.candidate,
        season=fp10.season,
        week=fp10.week,
    )
    counter, count = update_evidence_counter(
        counter,
        r11.counter_record,
        candidate=fp11.candidate,
        season=fp11.season,
        week=fp11.week,
    )
    assert count == 2  # two distinct qualifying slates


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_score_rejects_empty_outcomes():
    fp, ids = _base_plan()
    kwargs = _score_kwargs(fp, ids)
    kwargs["outcomes"] = pd.DataFrame()
    with pytest.raises(ShadowError, match="no outcomes provided"):
        score_freeze(**kwargs)


def test_score_rejects_missing_outcome_columns():
    fp, ids = _base_plan()
    kwargs = _score_kwargs(fp, ids)
    kwargs["outcomes"] = pd.DataFrame([{"game_id": 1000}])
    with pytest.raises(ShadowError, match="missing required columns"):
        score_freeze(**kwargs)


def test_score_rejects_no_matching_outcomes():
    fp, ids = _base_plan()
    kwargs = _score_kwargs(fp, ids)
    # outcomes for completely different game_ids
    kwargs["outcomes"] = _outcomes([9999, 9998])
    with pytest.raises(ShadowError, match="no outcomes match"):
        score_freeze(**kwargs)


def test_score_rejects_missing_required_params():
    fp, ids = _base_plan()
    kwargs = _score_kwargs(fp, ids)
    kwargs["outcome_version"] = ""
    with pytest.raises(ShadowError, match="candidate, run_id"):
        score_freeze(**kwargs)


def test_score_rejects_empty_freeze_record():
    fp, ids = _base_plan()
    kwargs = _score_kwargs(fp, ids)
    kwargs["freeze_record"] = pd.DataFrame()
    with pytest.raises(ShadowError, match="non-empty freeze record"):
        score_freeze(**kwargs)
