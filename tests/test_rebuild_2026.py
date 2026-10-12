"""2026 stage helpers: lock check, availability rule and parent pin shape."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from cks_picks_cfb.rebuild import silver_2026, states_2026
from cks_picks_cfb.rebuild.errors import GateError


def _games():
    return pd.DataFrame(
        {
            "season": [2026] * 3,
            "week": [0, 1, 5],
            "game_id": [10, 11, 12],
            "kickoff_utc": [
                "2026-08-29T16:00:00Z",
                "2026-09-05T16:00:00Z",
                "2026-10-02T00:00:00Z",
            ],
            "home_team": ["TCU", "Hawai'i", "USC"],
            "away_team": ["North Carolina", "Stanford", "UCLA"],
            "completed": [True, True, False],
        }
    )


def _lock(rows=None):
    rows = rows or [
        [0, 10, "2026-08-29T16:00:00Z", "TCU", "North Carolina"],
        [1, 11, "2026-09-05T16:00:00Z", "Hawai'i", "Stanford"],
        [5, 12, "2026-10-02T00:00:00Z", "USC", "UCLA"],
    ]
    return {
        "games": {
            "columns": ["week", "game_id", "start_date", "home_team", "away_team"],
            "rows": rows,
        }
    }


def test_locked_schedule_matches_the_lock_and_canonicalizes_names():
    schedule = states_2026.locked_schedule(_games(), _lock())
    assert len(schedule) == 3
    assert schedule["home_team"].tolist()[1] != ""  # canonicalized, still present


def test_locked_schedule_rejects_missing_games_and_changed_kickoffs():
    with pytest.raises(GateError, match="locked game ids"):
        states_2026.locked_schedule(_games().iloc[:2], _lock())
    moved = _lock(
        [
            [0, 10, "2026-08-29T17:00:00Z", "TCU", "North Carolina"],
            [1, 11, "2026-09-05T16:00:00Z", "Hawai'i", "Stanford"],
            [5, 12, "2026-10-02T00:00:00Z", "USC", "UCLA"],
        ]
    )
    with pytest.raises(GateError, match="differs from the lock"):
        states_2026.locked_schedule(_games(), moved)


def test_availability_needs_kickoff_plus_six_hours_by_the_cutoff():
    schedule = states_2026.locked_schedule(_games(), _lock())
    assert len(states_2026.available_by(schedule, "2026-09-30T12:34:06Z")) == 2
    assert len(states_2026.available_by(schedule, "2026-09-05T21:59:59Z")) == 1
    assert len(states_2026.available_by(schedule, "2026-09-05T22:00:00Z")) == 2


def test_parent_pin_must_be_exactly_the_four_2026_parents():
    def pin(names):
        return {
            "schema_version": silver_2026.PIN_SCHEMA,
            "parents": [
                {
                    "dataset": n,
                    "version_id": "v",
                    "schema_version": "s",
                    "content_sha": "c" * 64,
                    "uri": "u",
                }
                for n in names
            ],
        }

    assert [
        r.dataset for r in silver_2026.pinned_parents(pin(silver_2026.PARENT_ORDER))
    ] == list(silver_2026.PARENT_ORDER)
    with pytest.raises(GateError):
        silver_2026.pinned_parents(pin(silver_2026.PARENT_ORDER[:-1]))
    with pytest.raises(GateError):
        silver_2026.pinned_parents(
            {**pin(silver_2026.PARENT_ORDER), "schema_version": "x"}
        )


def test_2026_config_identity_differs_from_the_historical_build():
    from cks_picks_cfb.rebuild import silver

    assert silver_2026.config_sha() != silver.config_sha()


def _verify_with_ppa(*, legacy_zero_ppa, null_ppa, ppa_differences):
    summary = {
        "config_sha": silver_2026.config_sha(),
        "config": silver_2026.PIPELINE_CONFIG,
        "reconciliation": {"blocking": 0},
        "ppa": {
            "rows_equal": True,
            "null_ppa": null_ppa,
            "legacy_zero_ppa": legacy_zero_ppa,
        },
        "value_differences": {"ppa": ppa_differences} if ppa_differences else {},
        "punt_return_fix": {"rows": 0, "fits_punt_return_fix": True},
        "datasets": {},
    }
    context = SimpleNamespace(
        stage=SimpleNamespace(name="silver_2026"),
        plan=SimpleNamespace(run_id="run"),
        read_artifact=lambda stage, key: json.dumps(summary).encode(),
    )
    return silver_2026.verify(context)


def test_verify_accepts_legacy_zero_ppa_becoming_null():
    problems = _verify_with_ppa(
        legacy_zero_ppa=9121, null_ppa=9121, ppa_differences=9121
    )
    assert problems == []


def test_verify_accepts_already_nullable_legacy_without_ppa_changes():
    problems = _verify_with_ppa(legacy_zero_ppa=0, null_ppa=11045, ppa_differences=0)
    assert problems == []


@pytest.mark.parametrize(
    ("legacy_zero_ppa", "ppa_differences"), [(9121, 9120), (0, 5), (9121, 0)]
)
def test_verify_rejects_ppa_changes_other_than_legacy_zeros(
    legacy_zero_ppa, ppa_differences
):
    problems = _verify_with_ppa(
        legacy_zero_ppa=legacy_zero_ppa,
        null_ppa=11045,
        ppa_differences=ppa_differences,
    )
    assert problems == ["ppa changes are not exactly the legacy zero values"]


def test_verify_rejects_a_build_without_null_ppa():
    problems = _verify_with_ppa(legacy_zero_ppa=0, null_ppa=0, ppa_differences=0)
    assert problems == ["no null PPA: nullable mode not in effect"]
