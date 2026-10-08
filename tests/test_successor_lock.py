"""The corrected successor lock: replay weeks only, honest lineage, nothing invented."""

from __future__ import annotations

import copy

import pytest

from cks_picks_cfb.rebuild.successor_lock import (
    LOCK_SCHEMA,
    SuccessorLockError,
    derive_successor_lock,
)

COLUMNS = [
    "week",
    "game_id",
    "start_date",
    "home_team",
    "away_team",
    "home_points",
    "away_points",
]
EXTENDED = {
    "schema_version": LOCK_SCHEMA,
    "games": {
        "columns": COLUMNS,
        "rows": [
            [0, 1, "2026-08-29T16:00:00Z", "A", "B", 10, 7],
            [1, 2, "2026-09-05T16:00:00Z", "C", "D", 21, 14],
        ],
    },
    "post_week_cutoffs": {"0": "2026-09-03T04:00:00Z", "1": "2026-09-13T04:00:00Z"},
    "market_sources": {
        "0": {
            "as_of": "t0",
            "config": "conf/old.yaml",
            "config_sha256": "old",
            "market_quotes": {"content_sha": "q0"},
            "market_snapshots": {"content_sha": "s0"},
        }
    },
    "selected_runs": [{"week": 0, "run_id": "old-run", "state": "scored"}],
    "active_week": {"active_run_id": "x", "season": 2026, "week": 1},
    "game_rows_sha256": "base-rows",
    "research_2026_measurement_sha256": "old-m",
    "research_2026_rating_sha256": "old-r",
    "research_parent_sha256": {"forecast": "old"},
    "certified_weekly_rating_parents": [],
    "research_source_import": {"replay_parents": {"measurement_uri": "old"}},
    "extends": {"game_rows_sha256": "new-rows", "base_game_rows_sha256": "base-rows"},
}
REFS = {
    "weeks": {
        "0": {"as_of": "t0", "source_manifest": {"uri": "u0", "sha256": "m0"}},
        "1": {
            "as_of": "t1",
            "source_manifest": {"uri": "u1", "sha256": "m1"},
            "market_sources": {
                "market_quotes": {"content_sha": "q1"},
                "market_snapshots": {"content_sha": "s1"},
            },
        },
    }
}
CONFIG = {"path": "conf/new.yaml", "sha256": "new"}


def _derive(extended=EXTENDED, **overrides):
    kwargs = {
        "refs": REFS,
        "served_runs": {0: {"run_id": "served-0"}, 1: {"run_id": "served-1"}},
        "week_configs": {0: CONFIG, 1: CONFIG},
        "lineage": {
            "kind": "corrected_rebuild",
            "measurement_parent_sha256": "root",
            "rating_parent_sha256": "receipt",
        },
        "schedule_content_sha256": "sched",
        "schedule_uri": "uri/sched",
    }
    kwargs.update(overrides)
    return derive_successor_lock(extended, **kwargs)


def test_replay_weeks_get_market_sources_served_runs_and_a_first_unreplayed_week():
    lock = _derive()
    assert sorted(lock["market_sources"]) == ["0", "1"]
    assert lock["market_sources"]["1"]["market_quotes"] == {"content_sha": "q1"}
    assert [r["run_id"] for r in lock["selected_runs"]] == ["served-0", "served-1"]
    assert all(r["state"] == "scored" for r in lock["selected_runs"])
    assert lock["active_week"] == {"active_run_id": None, "season": 2026, "week": 2}


def test_a_replaced_threshold_config_is_recorded_not_silently_changed():
    lock = _derive()
    week0 = lock["market_sources"]["0"]
    assert (week0["config"], week0["config_sha256"]) == ("conf/new.yaml", "new")
    assert week0["superseded_config"] == {"path": "conf/old.yaml", "sha256": "old"}
    assert "superseded_config" not in lock["market_sources"]["1"]


def test_legacy_parent_keys_carry_the_corrected_hashes_and_the_old_ones_are_gone():
    lock = _derive()
    assert lock["research_2026_measurement_sha256"] == "root"
    assert lock["research_2026_rating_sha256"] == "receipt"
    assert lock["game_rows_sha256"] == "new-rows"
    assert "research_parent_sha256" not in lock
    assert "certified_weekly_rating_parents" not in lock
    assert lock["research_source_import"]["replay_parents"] == {
        "schedule_content_sha256": "sched",
        "schedule_uri": "uri/sched",
    }
    assert lock["corrected_lineage"]["kind"] == "corrected_rebuild"
    assert lock["games"] == EXTENDED["games"]


def test_the_base_lock_is_not_mutated():
    before = copy.deepcopy(EXTENDED)
    _derive()
    assert EXTENDED == before


@pytest.mark.parametrize(
    "mutate",
    [
        lambda e: e.pop("extends"),
        lambda e: e.update(schema_version="other"),
        lambda e: e.update(corrected_lineage={}),
        lambda e: e["post_week_cutoffs"].pop("0"),
        lambda e: e["games"]["rows"][1].__setitem__(5, None),
    ],
)
def test_a_base_that_is_not_a_complete_rebuild_extension_is_refused(mutate):
    base = copy.deepcopy(EXTENDED)
    mutate(base)
    with pytest.raises(SuccessorLockError):
        _derive(base)


def test_missing_per_week_inputs_and_a_changed_as_of_are_refused():
    with pytest.raises(SuccessorLockError, match="served_runs"):
        _derive(served_runs={0: {"run_id": "x"}})
    with pytest.raises(SuccessorLockError, match="week_configs"):
        _derive(week_configs={0: CONFIG})
    changed = copy.deepcopy(REFS)
    changed["weeks"]["0"]["as_of"] = "other"
    with pytest.raises(SuccessorLockError, match="as_of"):
        _derive(refs=changed)


# ---------------------------------------------------------------------------
# A live week on top of a corrected replay lock
# ---------------------------------------------------------------------------

from cks_picks_cfb.rebuild.successor_lock import derive_live_lock  # noqa: E402


def _replay_lock():
    lock = _derive()
    lock["extends"] = {"game_rows_sha256": "new-rows"}
    return lock


LIVE_GAMES = [
    {
        "game_id": 20,
        "start_date": "2026-10-10T16:00:00Z",
        "home_team": "E",
        "away_team": "F",
    },
    {
        "game_id": 21,
        "start_date": "2026-10-07T00:00:00Z",
        "home_team": "G",
        "away_team": "H",
    },
]
SOURCE = {"dataset": "games", "version_id": "v", "content_sha": "c", "uri": "u"}


def test_a_live_week_is_appended_without_finals_and_the_rest_is_untouched():
    base = _replay_lock()
    live = derive_live_lock(base, week=2, games=LIVE_GAMES, games_source=SOURCE)
    assert live["games"]["rows"][: len(base["games"]["rows"])] == base["games"]["rows"]
    added = live["games"]["rows"][len(base["games"]["rows"]) :]
    assert [row[1] for row in added] == [21, 20]  # kickoff order
    assert all(row[0] == 2 and row[5] is None and row[6] is None for row in added)
    assert live["post_week_cutoffs"] == base["post_week_cutoffs"]
    assert live["market_sources"] == base["market_sources"]
    assert live["active_week"] == {"active_run_id": None, "season": 2026, "week": 2}
    assert live["game_rows_sha256"] != base["game_rows_sha256"]
    assert live["corrected_lineage"]["live_week"]["games"] == 2
    assert base["active_week"]["week"] == 2 and len(base["games"]["rows"]) == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"week": 3},  # not the week after the last replayed one
        {"games": []},
        {"games": LIVE_GAMES + LIVE_GAMES[:1]},  # duplicate
        {"games": [{**LIVE_GAMES[0], "game_id": 1}]},  # already locked
    ],
)
def test_a_live_week_that_does_not_follow_cleanly_is_refused(kwargs):
    arguments = {"week": 2, "games": LIVE_GAMES, "games_source": SOURCE, **kwargs}
    with pytest.raises(SuccessorLockError):
        derive_live_lock(_replay_lock(), **arguments)


def test_only_a_corrected_lock_can_take_a_live_week():
    with pytest.raises(SuccessorLockError):
        derive_live_lock(dict(EXTENDED), week=2, games=LIVE_GAMES, games_source=SOURCE)
