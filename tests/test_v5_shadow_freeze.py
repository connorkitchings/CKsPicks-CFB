"""Focused V5-05B shadow freeze tests."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.forecast.shadow import (
    ShadowError,
    plan_freeze,
)


def _schedule(n: int = 45, season: int = 2025, week: int = 10) -> pd.DataFrame:
    rows = [
        {
            "season": season,
            "week": week,
            "game_id": 1000 + i,
            "kickoff_utc": "2025-11-15T16:00:00+00:00",
        }
        for i in range(n)
    ]
    return pd.DataFrame(rows)


def _predictions(game_ids: list, mean: float = 5.0) -> pd.DataFrame:
    rows = []
    for gid in game_ids:
        for target in ("margin", "total"):
            rows.append({"game_id": gid, "target": target, "mean": mean})
    return pd.DataFrame(rows)


def _freeze_kwargs(
    n_games: int = 45, lead_offset: float = 0.0, season: int = 2025, week: int = 10
) -> dict:
    schedule = _schedule(n_games, season=season, week=week)
    game_ids = list(range(1000, 1000 + n_games))
    freeze_ts = pd.Timestamp("2025-11-15T16:00:00Z") - pd.Timedelta(
        seconds=7200 + lead_offset
    )
    return {
        "candidate": "forecast-v1-20260917-4600ddd-04b",
        "season": season,
        "week": week,
        "run_id": "shadow-v1-test-05b-freeze",
        "freeze_time": freeze_ts.isoformat(),
        "schedule": schedule,
        "v5_predictions": _predictions(game_ids),
        "v4_predictions": _predictions(game_ids, mean=4.0),
        "v4_ref_uri": "artifacts/v4/week10/v4-predictions.parquet",
        "min_paired_games": 40,
        "freeze_hard_lead_seconds": 3600.0,
    }


# Timing gate tests


def test_freeze_accepts_at_exactly_t_minus_2h():
    plan = plan_freeze(**_freeze_kwargs(lead_offset=0.0))
    assert abs(plan.lead_seconds - 7200.0) < 1.0


def test_freeze_rejects_below_t_minus_1h():
    # lead_offset=-4000 -> lead = 7200-4000 = 3200 < 3600
    kwargs = _freeze_kwargs(lead_offset=-4000.0)
    with pytest.raises(ShadowError, match="hard gate"):
        plan_freeze(**kwargs)


def test_freeze_rejects_at_kickoff():
    schedule = _schedule(45)
    game_ids = list(range(1000, 1045))
    freeze_ts = pd.Timestamp("2025-11-15T16:00:00Z")
    with pytest.raises(ShadowError, match="hard gate"):
        plan_freeze(
            candidate="forecast-v1-20260917-4600ddd-04b",
            season=2025,
            week=10,
            run_id="test",
            freeze_time=freeze_ts.isoformat(),
            schedule=schedule,
            v5_predictions=_predictions(game_ids),
            v4_predictions=_predictions(game_ids, mean=4.0),
            v4_ref_uri="v4/ref.parquet",
            min_paired_games=40,
            freeze_hard_lead_seconds=3600.0,
        )


def test_freeze_rejects_naive_freeze_time():
    kwargs = _freeze_kwargs()
    kwargs["freeze_time"] = "2025-11-15T10:00:00"  # naive
    with pytest.raises(ShadowError, match="timezone-aware"):
        plan_freeze(**kwargs)


# Population / paired game boundary tests


def test_freeze_passes_at_exactly_40_games():
    plan = plan_freeze(**_freeze_kwargs(n_games=40))
    assert plan.paired_count == 40
    assert plan.broader_count == 40


def test_freeze_rejects_39_games():
    kwargs = _freeze_kwargs(n_games=39)
    with pytest.raises(ShadowError, match="only 39 paired games"):
        plan_freeze(**kwargs)


def test_freeze_population_preservation():
    n = 50
    kwargs = _freeze_kwargs(n_games=n)
    # Last 5 games missing from V4 -> excluded
    all_ids = list(range(1000, 1050))
    kwargs["v4_predictions"] = _predictions(all_ids[:45], mean=4.0)
    plan = plan_freeze(**kwargs)
    assert plan.broader_count == 50
    assert plan.paired_count == 45
    assert plan.excluded_count == 5
    assert plan.broader_count == plan.paired_count + plan.excluded_count


def test_freeze_excludes_non_finite_v4():
    n = 45
    kwargs = _freeze_kwargs(n_games=n)
    all_ids = list(range(1000, 1045))
    bad_ids = all_ids[:3]
    good_v4 = _predictions([g for g in all_ids if g not in bad_ids], mean=4.0)
    nan_v4 = pd.DataFrame(
        [
            {"game_id": g, "target": t, "mean": float("nan")}
            for g in bad_ids
            for t in ("margin", "total")
        ]
    )
    kwargs["v4_predictions"] = pd.concat([good_v4, nan_v4])
    plan = plan_freeze(**kwargs)
    assert plan.paired_count == 42
    assert plan.excluded_count == 3


def test_freeze_excludes_non_finite_v5():
    n = 45
    kwargs = _freeze_kwargs(n_games=n)
    all_ids = list(range(1000, 1045))
    bad_ids = all_ids[:2]
    good_v5 = _predictions([g for g in all_ids if g not in bad_ids], mean=5.0)
    inf_v5 = pd.DataFrame(
        [
            {"game_id": g, "target": t, "mean": float("inf")}
            for g in bad_ids
            for t in ("margin", "total")
        ]
    )
    kwargs["v5_predictions"] = pd.concat([good_v5, inf_v5])
    plan = plan_freeze(**kwargs)
    assert plan.paired_count == 43


def test_freeze_rejects_missing_v4_column():
    kwargs = _freeze_kwargs()
    kwargs["v4_predictions"] = pd.DataFrame(
        [{"game_id": i, "target": "margin"} for i in range(1000, 1045)]
    )
    with pytest.raises(ShadowError, match="V4 predictions missing columns"):
        plan_freeze(**kwargs)


def test_freeze_rejects_empty_schedule():
    kwargs = _freeze_kwargs()
    kwargs["schedule"] = _schedule(45, season=2025, week=11)  # wrong week
    with pytest.raises(ShadowError, match="no schedule rows"):
        plan_freeze(**kwargs)


def test_freeze_rejects_missing_kickoff_column():
    schedule = _schedule(45).drop(columns=["kickoff_utc"])
    kwargs = _freeze_kwargs()
    kwargs["schedule"] = schedule
    with pytest.raises(ShadowError, match="kickoff_utc"):
        plan_freeze(**kwargs)


# Slate digest stability


def test_freeze_slate_digest_is_stable():
    plan1 = plan_freeze(**_freeze_kwargs())
    plan2 = plan_freeze(**_freeze_kwargs())
    assert plan1.slate_digest == plan2.slate_digest
    assert len(plan1.slate_digest) == 64


def test_freeze_slate_digest_changes_with_different_games():
    plan45 = plan_freeze(**_freeze_kwargs(n_games=45))
    plan46 = plan_freeze(**_freeze_kwargs(n_games=46))
    assert plan45.slate_digest != plan46.slate_digest


def test_freeze_identity_sha_changes_with_freeze_time():
    kwargs1 = _freeze_kwargs()
    kwargs2 = dict(kwargs1)
    kwargs2["freeze_time"] = (
        pd.Timestamp(kwargs1["freeze_time"]) - pd.Timedelta(hours=1)
    ).isoformat()
    plan1 = plan_freeze(**kwargs1)
    plan2 = plan_freeze(**kwargs2)
    assert plan1.identity_sha256 != plan2.identity_sha256


# Output schema


def test_freeze_record_has_required_columns():
    from cks_picks_cfb.data.data_first_shadow_v1 import SHADOW_FREEZE_COLUMNS

    plan = plan_freeze(**_freeze_kwargs())
    assert set(SHADOW_FREEZE_COLUMNS) <= set(plan.freeze_record.columns)
    assert len(plan.freeze_record) == 1


def test_freeze_predictions_have_required_columns():
    from cks_picks_cfb.data.data_first_shadow_v1 import SHADOW_PREDICTION_COLUMNS

    plan = plan_freeze(**_freeze_kwargs())
    assert set(SHADOW_PREDICTION_COLUMNS) <= set(plan.predictions.columns)
    assert len(plan.predictions) == plan.paired_count * 2


def test_freeze_plan_is_immutable():
    plan = plan_freeze(**_freeze_kwargs())
    with pytest.raises((AttributeError, TypeError)):
        plan.paired_count = 999  # type: ignore[misc]


# Guard rails


def test_freeze_rejects_empty_candidate():
    kwargs = _freeze_kwargs()
    kwargs["candidate"] = ""
    with pytest.raises(ShadowError, match="candidate identity is missing"):
        plan_freeze(**kwargs)


def test_freeze_rejects_empty_v4_ref_uri():
    kwargs = _freeze_kwargs()
    kwargs["v4_ref_uri"] = ""
    with pytest.raises(ShadowError, match="v4_ref_uri are required"):
        plan_freeze(**kwargs)
