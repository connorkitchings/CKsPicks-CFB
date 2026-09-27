"""The weekly readiness gate accepts only a complete current rating generation."""

from datetime import datetime, timezone

import pandas as pd
import psycopg
import pytest

from scripts.pipeline import check_prepared_week

SHA = "a" * 64
KICKOFF = datetime(2026, 9, 26, 18, tzinfo=timezone.utc)
AS_OF = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
CUTOFF = datetime(2026, 9, 27, 0, tzinfo=timezone.utc)


def _row(team, kind="current", cutoff=CUTOFF, *, run="rating-1", sha=SHA):
    return (run, sha, team, kind, cutoff, AS_OF)


def _completed():
    return pd.DataFrame([{"kickoff_utc": KICKOFF, "home_team": "A", "away_team": "B"}])


def _currency(rows, *, teams=None, completed=None, as_of=AS_OF):
    return check_prepared_week._rating_currency(
        rows,
        target_teams=teams or {"A", "B"},
        completed_games=_completed() if completed is None else completed,
        as_of=as_of,
    )


def test_current_generation_covers_completed_game_at_six_hour_boundary():
    result = _currency([_row("A"), _row("B")])
    assert result == {
        "rating_cutoff_utc": CUTOFF.isoformat(),
        "rating_manifest_sha256": SHA,
    }


def test_stale_generation_fails_before_ready_state():
    stale = CUTOFF - pd.Timedelta(seconds=1)
    with pytest.raises(ValueError, match="Ratings are stale"):
        _currency([_row("A", cutoff=stale), _row("B", cutoff=stale)])


def test_missing_or_ambiguous_current_generation_fails():
    with pytest.raises(ValueError, match="Ratings are missing"):
        _currency([])
    with pytest.raises(ValueError, match="Ratings are ambiguous"):
        _currency([_row("A"), _row("B", run="rating-2", sha="b" * 64)])


def test_target_teams_need_same_generation_current_or_preseason_rows():
    rows = [_row("A"), _row("B"), _row("C", kind="pregame", cutoff=KICKOFF)]
    assert _currency(rows, teams={"A", "B", "C"})["rating_manifest_sha256"] == SHA
    with pytest.raises(ValueError, match=r"preseason=\['C'\]"):
        _currency(rows[:2], teams={"A", "B", "C"})
    with pytest.raises(ValueError, match=r"current=\['B'\]"):
        _currency(rows[:1])


def test_schedule_aliases_match_canonical_rating_teams():
    completed = pd.DataFrame(
        [
            {
                "kickoff_utc": KICKOFF,
                "home_team": "Hawai'i",
                "away_team": "Massachusetts",
            }
        ]
    )
    assert (
        _currency(
            [_row("Hawai_i"), _row("UMass")],
            teams={"Hawai'i", "Massachusetts"},
            completed=completed,
        )["rating_manifest_sha256"]
        == SHA
    )


def test_preseason_baseline_when_no_games_are_completed():
    empty = _completed().iloc[0:0]
    result = _currency(
        [
            _row("A", kind="pregame", cutoff=KICKOFF),
            _row("B", kind="pregame", cutoff=KICKOFF),
        ],
        completed=empty,
    )
    assert result["rating_cutoff_utc"] == KICKOFF.isoformat()


def test_future_rating_cutoff_is_rejected():
    future = AS_OF + pd.Timedelta(seconds=1)
    with pytest.raises(ValueError, match="later than the requested as_of"):
        _currency([_row("A", cutoff=future), _row("B", cutoff=future)])


@pytest.mark.parametrize(
    "error",
    [psycopg.OperationalError("unavailable"), psycopg.errors.UndefinedTable("missing")],
)
def test_database_failure_does_not_bypass_rating_gate(monkeypatch, error):
    def unavailable(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(check_prepared_week.psycopg, "connect", unavailable)
    with pytest.raises(type(error)):
        check_prepared_week._rating_rows(
            "postgresql://unused", year=2026, week=5, as_of=AS_OF
        )
