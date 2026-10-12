"""What a lock extension adds to the published comparison, and what it must not hide."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pandas as pd
import pytest

from cks_picks_cfb.rebuild import published_comparison as pc
from cks_picks_cfb.rebuild import published_diff as pd_
from cks_picks_cfb.rebuild.errors import GateError

EXTENDED = {
    "extends": {
        "added_post_week": 5,
        "newly_final_game_ids": [10, 11],
        "kickoff_revisions": [
            {
                "game_id": 11,
                "old_start_date": "2026-10-03T19:30:00Z",
                "new_start_date": "2026-10-03T15:00:00Z",
            }
        ],
    }
}


def test_an_unextended_lock_adds_nothing():
    scope = pc.lock_scope({})
    assert pc.game_scope(scope) is None and pc.week_scope(scope) is None
    assert (
        pc.kickoff_revision(scope)(pd.Series({"game_id_built": 11}), "cutoff_utc")
        is None
    )


def test_an_extension_scopes_games_and_the_next_as_of_week():
    scope = pc.lock_scope(EXTENDED)
    games = pc.game_scope(scope)(pd.DataFrame({"game_id": [9, 10, 11]}))
    assert games.tolist() == [False, True, True]
    weeks = pc.week_scope(scope)(pd.DataFrame({"as_of_week": [5, 6]}))
    assert weeks.tolist() == [False, True]


def _row(game, built, published):
    return pd.Series(
        {"game_id_built": game, "cutoff_utc_built": built, "cutoff_utc_pub": published}
    )


def test_only_the_recorded_revision_is_named():
    override = pc.kickoff_revision(pc.lock_scope(EXTENDED))
    new, old = (
        pd.Timestamp("2026-10-03T15:00:00Z"),
        pd.Timestamp("2026-10-03T19:30:00Z"),
    )
    assert override(_row(11, new, old), "cutoff_utc") == "kickoff_revision"
    assert override(_row(11, new, old), "rating_mean") is None
    assert override(_row(12, new, old), "cutoff_utc") is None
    # A different new value, or the direction reversed, is not the recorded revision.
    other = pd.Timestamp("2026-10-03T16:00:00Z")
    assert override(_row(11, other, old), "cutoff_utc") is None
    assert override(_row(11, old, new), "cutoff_utc") is None


def test_the_revision_makes_a_cutoff_difference_explained_but_not_a_rating_change():
    override = pc.kickoff_revision(pc.lock_scope(EXTENDED))
    old, new = "2026-10-03T19:30:00+00:00", "2026-10-03T15:00:00+00:00"

    def frame(cutoff, rating):
        return pd.DataFrame(
            {
                "component_id": ["a"],
                "game_id": [11],
                "cutoff_utc": pd.to_datetime([cutoff], utc=True),
                "rating_mean": [rating],
            }
        )

    def run(built):
        return pd_.diff_frames(
            built,
            frame(old, 1.0),
            keys=["component_id"],
            columns=["game_id", "cutoff_utc", "rating_mean"],
            metric_of=lambda row: None,
            expected={"kickoff_revision"},
            bucket_override=override,
        )

    assert not run(frame(new, 1.0))["unexplained"]
    changed = run(frame(new, 1.5))
    assert changed["unexplained"] and "ratings" in changed["unexplained_buckets"]


RATINGS_V1 = "v5-intended-update-2026-ratings-v1"
W6LIVE = "v5-intended-update-2026-corrected-w6live-r1"
POLICY = {"published_rating_runs": {RATINGS_V1: [0, 1, 2, 3, 4, 5], W6LIVE: [6]}}


def test_the_week6_plan_maps_weeks_0_to_5_and_week_6_to_their_runs():
    from pathlib import Path

    import yaml

    plan = yaml.safe_load(Path("conf/rebuild/6a_task4_w6_v1.yaml").read_text())
    week_runs = pc.published_rating_runs(plan["policies"])
    assert week_runs == {**dict.fromkeys(range(6), RATINGS_V1), 6: W6LIVE}


def test_a_missing_or_overlapping_policy_is_refused():
    with pytest.raises(GateError, match="missing"):
        pc.published_rating_runs({})
    with pytest.raises(GateError, match="two runs"):
        pc.published_rating_runs({"published_rating_runs": {"a": [5], "b": [5, 6]}})


def test_exactly_the_planned_runs_are_accepted():
    week_runs = pc.published_rating_runs(POLICY)
    pc.check_published_runs([W6LIVE, RATINGS_V1], week_runs)
    for found, word in [
        ([RATINGS_V1], "missing"),
        ([RATINGS_V1, W6LIVE, "other-run"], "unexpected"),
        ([RATINGS_V1, "other-run"], "unexpected"),
        ([], "missing"),
    ]:
        with pytest.raises(GateError, match=word):
            pc.check_published_runs(found, week_runs)


def test_a_single_run_is_accepted_only_when_the_plan_names_one():
    single = pc.published_rating_runs({"published_rating_runs": {RATINGS_V1: [0, 1]}})
    pc.check_published_runs([RATINGS_V1], single)
    with pytest.raises(GateError):
        pc.check_published_runs([RATINGS_V1], pc.published_rating_runs(POLICY))


def test_each_week_carries_its_runs_ids():
    @dataclasses.dataclass
    class Artifacts:
        run_id: str

    def build(artifacts):
        weeks = [0, 5, 6, 7]
        frames = {
            "team_rating_components": pd.DataFrame(
                {
                    "component_id": [f"{artifacts.run_id}:{w}" for w in weeks],
                    "as_of_week": weeks,
                }
            ),
            "team_game_measurements": pd.DataFrame({"run": [artifacts.run_id]}),
        }
        return SimpleNamespace(payload=SimpleNamespace(frames=frames))

    frames = pc.build_frames(Artifacts("x"), pc.published_rating_runs(POLICY), build)
    components = frames["team_rating_components"].sort_values("as_of_week")
    assert components["component_id"].tolist() == [
        f"{RATINGS_V1}:0",
        f"{RATINGS_V1}:5",
        f"{W6LIVE}:6",
        f"{W6LIVE}:7",  # past the plan: the newest run's ids (lock-extension scope)
    ]
    assert frames["team_game_measurements"]["run"].tolist() == [W6LIVE]
