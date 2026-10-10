import copy
import json

import pandas as pd
import pytest

from cks_picks_cfb.rebuild import market_sources_lock as lock

AS_OF = "2026-10-08T16:20:00Z"


def _schedule(*games):
    return pd.DataFrame(games, columns=["game_id", "kickoff_utc"])


def _snapshot(
    game_id, *, spread=-3.5, total=50.5, quotes=(), captured="2026-10-08T16:19:00Z"
):
    return {
        "game_id": game_id,
        "market_snapshot_id": f"snap-{game_id}",
        "market_captured_at": captured,
        "spread_line": spread,
        "total_line": total,
        "source_quote_ids": json.dumps(list(quotes)),
    }


def _quote(game_id, quote_id, captured, *, spread=-3.5, total=50.5):
    return {
        "game_id": game_id,
        "quote_id": quote_id,
        "captured_at": captured,
        "spread": spread,
        "total": total,
    }


def _classify(snapshots, quotes, schedule, as_of=AS_OF):
    return {
        (row["game_id"], row["target"]): row["status"]
        for row in lock.classify_week_markets(
            pd.DataFrame(snapshots), pd.DataFrame(quotes), schedule, as_of=as_of
        )
    }


def test_pre_kickoff_quotes_are_eligible_and_post_kickoff_only_games_are_gaps():
    schedule = _schedule(
        (1, "2026-10-09T00:00:00Z"),  # kicks off after the capture
        (2, "2026-10-07T00:00:00Z"),  # kicked off before the capture
    )
    snapshots = [_snapshot(1, quotes=["q1"]), _snapshot(2, quotes=["q2"])]
    quotes = [
        _quote(1, "q1", "2026-10-08T16:19:00Z"),
        _quote(2, "q2", "2026-10-08T16:19:00Z"),
    ]
    status = _classify(snapshots, quotes, schedule)
    assert status[(1, "spread")] == status[(1, "total")] == lock.STATUS_ELIGIBLE
    assert (
        status[(2, "spread")] == status[(2, "total")] == lock.STATUS_POST_KICKOFF_ONLY
    )


def test_a_quote_captured_exactly_at_kickoff_is_not_eligible():
    schedule = _schedule((1, "2026-10-08T16:19:00Z"))
    status = _classify(
        [_snapshot(1, quotes=["q"])], [_quote(1, "q", "2026-10-08T16:19:00Z")], schedule
    )
    assert status[(1, "spread")] == lock.STATUS_POST_KICKOFF_ONLY


def test_each_target_is_classified_on_its_own():
    schedule = _schedule((1, "2026-10-09T00:00:00Z"))
    snapshots = [_snapshot(1, total=None, quotes=["q"])]
    quotes = [_quote(1, "q", "2026-10-08T16:19:00Z", total=None)]
    status = _classify(snapshots, quotes, schedule)
    assert status[(1, "spread")] == lock.STATUS_ELIGIBLE
    assert status[(1, "total")] == lock.STATUS_NO_CANONICAL_LINE


def test_missing_snapshot_missing_quotes_and_unlinked_quotes():
    schedule = _schedule(
        (1, "2026-10-09T00:00:00Z"),
        (2, "2026-10-09T00:00:00Z"),
        (3, "2026-10-09T00:00:00Z"),
    )
    snapshots = [_snapshot(2, quotes=["other"]), _snapshot(3, quotes=["q3"])]
    quotes = [
        _quote(
            2, "unlinked", "2026-10-08T16:00:00Z"
        ),  # not in the snapshot's quote ids
        _quote(3, "q3", "2026-10-08T16:00:00Z", spread=None),
    ]
    status = _classify(snapshots, quotes, schedule)
    assert status[(1, "spread")] == lock.STATUS_NO_SNAPSHOT
    assert status[(2, "spread")] == lock.STATUS_NO_QUOTE
    assert status[(3, "spread")] == lock.STATUS_NO_QUOTE  # no point for that target
    assert status[(3, "total")] == lock.STATUS_ELIGIBLE


def test_a_quote_after_the_forecast_cutoff_is_not_eligible():
    schedule = _schedule((1, "2026-10-10T00:00:00Z"))
    snapshots = [_snapshot(1, quotes=["q"])]
    quotes = [_quote(1, "q", "2026-10-08T16:20:30Z")]  # pre-kickoff, after as_of
    status = _classify(snapshots, quotes, schedule)
    assert status[(1, "spread")] == lock.STATUS_AFTER_AS_OF_ONLY


def test_inputs_that_would_hide_evidence_are_refused():
    schedule = _schedule((1, "2026-10-09T00:00:00Z"))
    good_quotes = pd.DataFrame([_quote(1, "q", "2026-10-08T16:00:00Z")])
    with pytest.raises(lock.MarketLockError, match="duplicate canonical"):
        lock.classify_week_markets(
            pd.DataFrame([_snapshot(1), _snapshot(1)]),
            good_quotes,
            schedule,
            as_of=AS_OF,
        )
    with pytest.raises(lock.MarketLockError, match="after as_of"):
        lock.classify_week_markets(
            pd.DataFrame([_snapshot(1, captured="2026-10-08T17:00:00Z")]),
            good_quotes,
            schedule,
            as_of=AS_OF,
        )
    with pytest.raises(lock.MarketLockError, match="duplicate game ids"):
        lock.classify_week_markets(
            pd.DataFrame([_snapshot(1)]),
            good_quotes,
            _schedule((1, "2026-10-09T00:00:00Z"), (1, "2026-10-09T00:00:00Z")),
            as_of=AS_OF,
        )
    with pytest.raises(lock.MarketLockError, match="lacks columns"):
        lock.classify_week_markets(
            pd.DataFrame([_snapshot(1)]),
            good_quotes.drop(columns=["captured_at"]),
            schedule,
            as_of=AS_OF,
        )


def _rows():
    schedule = _schedule((1, "2026-10-09T00:00:00Z"), (2, "2026-10-07T00:00:00Z"))
    snapshots = [_snapshot(1, quotes=["q1"]), _snapshot(2, quotes=["q2"])]
    quotes = [
        _quote(1, "q1", "2026-10-08T16:19:00Z"),
        _quote(2, "q2", "2026-10-08T16:19:00Z"),
    ]
    return lock.classify_week_markets(
        pd.DataFrame(snapshots), pd.DataFrame(quotes), schedule, as_of=AS_OF
    )


def test_gaps_are_listed_in_the_lock_format_and_summarized():
    rows = _rows()
    gaps = lock.verified_gaps(rows, week=6)
    assert [(g["week"], g["game_id"], g["target"]) for g in gaps] == [
        (6, 2, "spread"),
        (6, 2, "total"),
    ]
    assert all("verified gap, no selection or grade" in g["status"] for g in gaps)
    summary = lock.coverage_summary(rows)
    assert summary["games"] == 2
    assert summary["spread"] == {
        "eligible": 1,
        "gaps": 1,
        "by_status": {"eligible": 1, "post_kickoff_only": 1},
    }


def _entry(rows):
    ref = {"dataset": "x", "version_id": "v", "content_sha": "c", "uri": "u"}
    return lock.week_entry(
        as_of=AS_OF,
        cutoff_source={"uri": "serving", "sha256": "s"},
        source_manifest={"uri": "manifest", "sha256": "m"},
        games=ref,
        market_quotes=ref,
        market_snapshots=ref,
        rows=rows,
        week=6,
    )


def _base():
    return {
        "schema_version": "reconstruction_source_refs_v1",
        "week5_outcomes": {"x": 1},
        "weeks": {str(week): {"as_of": f"w{week}"} for week in range(6)},
    }


def test_extension_adds_only_the_next_week_and_leaves_the_base_untouched():
    base = _base()
    frozen = copy.deepcopy(base)
    extended = lock.extend_source_refs(base, week=6, entry=_entry(_rows()))
    assert base == frozen
    assert {k: v for k, v in extended["weeks"].items() if k != "6"} == base["weeks"]
    entry = extended["weeks"]["6"]
    assert set(entry["market_sources"]) == {
        "games",
        "market_quotes",
        "market_snapshots",
    }
    assert len(entry["market_gaps"]) == 2 and entry["market_coverage"]["games"] == 2


@pytest.mark.parametrize("week", [5, 7, 8])
def test_extension_refuses_existing_or_non_adjacent_weeks(week):
    with pytest.raises(lock.MarketLockError):
        lock.extend_source_refs(_base(), week=week, entry=_entry(_rows()))


def test_unknown_refs_schema_is_refused():
    with pytest.raises(lock.MarketLockError, match="schema"):
        lock.extend_source_refs(
            {**_base(), "schema_version": "other"}, week=6, entry=_entry(_rows())
        )
