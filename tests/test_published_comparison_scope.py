"""What a lock extension adds to the published comparison, and what it must not hide."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.rebuild import published_comparison as pc
from cks_picks_cfb.rebuild import published_diff as pd_

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
