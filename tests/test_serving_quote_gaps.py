"""The replay serving builder accepts exactly the quote gaps the lock declares."""

import pandas as pd
import pytest

from scripts.pipeline.build_v5_intended_update_serving import (
    check_quote_gaps,
    original_run_replayable,
)


def _serving(spread_missing=(), total_missing=(), games=(1, 2, 3)):
    return pd.DataFrame(
        {
            "game_id": list(games),
            "spread_market_quote_id": [
                None if g in spread_missing else f"s{g}" for g in games
            ],
            "total_market_quote_id": [
                None if g in total_missing else f"t{g}" for g in games
            ],
        }
    )


def _gap(game_id, target, week=6):
    return {"week": week, "game_id": game_id, "target": target, "status": "verified"}


def test_no_declared_gaps_means_every_target_must_be_quoted():
    check_quote_gaps(_serving(), None, week=6)
    check_quote_gaps(_serving(), [], week=6)
    with pytest.raises(ValueError, match="spread quote gaps differ"):
        check_quote_gaps(_serving(spread_missing={2}), [], week=6)
    with pytest.raises(ValueError, match="total quote gaps differ"):
        check_quote_gaps(_serving(total_missing={3}), None, week=6)


def test_declared_gaps_are_accepted_for_either_target_and_only_those():
    gaps = [_gap(2, "spread"), _gap(2, "total"), _gap(3, "total")]
    check_quote_gaps(_serving({2}, {2, 3}), gaps, week=6)
    # A declared gap that is in fact quoted, or an undeclared hole, both fail.
    with pytest.raises(ValueError, match="spread quote gaps differ"):
        check_quote_gaps(_serving(set(), {2, 3}), gaps, week=6)
    with pytest.raises(ValueError, match="total quote gaps differ"):
        check_quote_gaps(_serving({2}, {2, 3, 1}), gaps, week=6)


def test_gaps_of_other_weeks_do_not_excuse_this_week_and_a_single_mapping_works():
    check_quote_gaps(_serving(total_missing={2}), _gap(2, "total"), week=6)
    with pytest.raises(ValueError, match="total quote gaps differ"):
        check_quote_gaps(
            _serving(total_missing={2}), [_gap(2, "total", week=3)], week=6
        )


def test_only_scored_or_display_only_published_runs_can_be_replayed_from():
    assert original_run_replayable({"state": "scored"})
    assert original_run_replayable({"state": "published", "display_only": True})
    assert not original_run_replayable({"state": "published"})
    assert not original_run_replayable({"state": "published", "display_only": False})
    assert not original_run_replayable({"state": "frozen", "display_only": True})
