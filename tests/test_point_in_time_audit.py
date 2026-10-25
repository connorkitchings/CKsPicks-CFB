"""Each point-in-time rule has a passing and a failing fixture."""

import copy

import pandas as pd
import pytest

from cks_picks_cfb.audit import point_in_time as pit
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload

BUNDLE = {
    "development_seasons": [2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025]
}
SHA = "a" * 64


def _games():
    return pd.DataFrame(
        [
            (1, 5, "2026-10-02T00:00:00Z"),
            (2, 5, "2026-10-03T16:00:00Z"),
            (3, 6, "2026-10-07T00:00:00Z"),  # mid-week game: the slate's first kickoff
            (4, 6, "2026-10-10T16:00:00Z"),
        ],
        columns=["game_id", "week", "kickoff_utc"],
    )


def _forecasts(as_of5="2026-09-29T20:29:00Z", as_of6="2026-10-05T12:00:00Z"):
    rows = []
    for gid, week in ((1, 5), (2, 5), (3, 6), (4, 6)):
        rows.append(
            {
                "game_id": gid,
                "run_id": f"run-{week}",
                "forecast_as_of": as_of5 if week == 5 else as_of6,
                "market_as_of": as_of5 if week == 5 else "2026-10-08T16:20:00Z",
            }
        )
    return pd.DataFrame(rows)


def _runs(**overrides):
    base = [
        {
            "week": 5,
            "run_id": "run-5",
            "forecast_as_of": "2026-09-29T20:29:00Z",
            "market_as_of": "2026-09-29T20:29:00Z",
            "display_only": False,
        },
        {
            "week": 6,
            "run_id": "run-6",
            "forecast_as_of": "2026-10-05T12:00:00Z",
            "market_as_of": "2026-10-08T16:20:00Z",
            "display_only": False,
        },
    ]
    frame = pd.DataFrame(base)
    for key, value in overrides.items():
        frame[key] = value
    return frame


def _history():
    # Week 5 targets use Week 4 games; Week 6 targets use Week 5 games.
    return pd.DataFrame(
        [
            (1, "A", 100, 4, "2026-09-26T16:00:00Z"),
            (3, "B", 1, 5, "2026-10-02T00:00:00Z"),
            (4, "C", 2, 5, "2026-10-03T16:00:00Z"),
        ],
        columns=[
            "game_id",
            "team",
            "source_game_id",
            "source_week",
            "source_kickoff_utc",
        ],
    )


def _states():
    return pd.DataFrame(
        [
            (1, "A", "2026-09-28T04:00:00Z"),
            (3, "B", "2026-10-05T00:00:00Z"),
            (4, "C", "2026-10-05T00:00:00Z"),
        ],
        columns=["game_id", "team", "state_cutoff_utc"],
    )


def _quotes(late=False):
    rows = [
        (1, "spread", "q1", "2026-09-29T20:00:00Z", "cfbd", "betting_lines"),
        (2, "spread", "q2", "2026-09-29T20:00:00Z", "cfbd", "betting_lines"),
        (4, "spread", "q4", "2026-10-08T16:19:00Z", "cfbd", "betting_lines"),
    ]
    if late:
        rows.append(
            (3, "spread", "q3", "2026-10-08T16:19:00Z", "cfbd", "betting_lines")
        )
    return pd.DataFrame(
        rows,
        columns=["game_id", "target", "quote_id", "captured_at", "provider", "entity"],
    )


LATE = {
    "game_id": 3,
    "target": "spread",
    "quote_id": "q3",
    "provider": "cfbd",
    "entity": "betting_lines",
    "reason": pit.ACCEPTED_LATE_REASON,
}


def _audit(**overrides):
    kwargs = dict(
        games=_games(),
        forecasts=_forecasts(),
        runs=_runs(),
        history=_history(),
        states=_states(),
        quotes=_quotes(late=True),
        accepted_late=[LATE],
        bundle=BUNDLE,
        declared_bundle_sha256=SHA,
        bundle_file_sha256=SHA,
        team_stats_usage=pd.DataFrame(
            {"game_id": [1, 2, 3, 4], "stats_as_of_week": [5, 5, 6, 6]}
        ),
        environment="preview",
    )
    kwargs.update(overrides)
    return pit.run_audit(**kwargs)


def _rules(receipt):
    return {v["rule"] for v in receipt["violations"]}


def test_a_clean_slate_passes_and_the_receipt_is_signed_and_complete():
    receipt = _audit()
    assert receipt["state"] == "passed" and receipt["violations"] == []
    verify_signed_payload(receipt, label="receipt")
    assert receipt["runs"] == {"5": "run-5", "6": "run-6"}
    assert receipt["games_checked"] == 4 and all(g["passed"] for g in receipt["games"])
    assert [u["quote_id"] for u in receipt["accepted_late_used"]] == ["q3"]
    assert receipt["accepted_late_unused"] == []
    assert set(receipt["rules"]) == set(pit.RULES)
    assert receipt["assumptions"]


def test_a_rating_input_available_after_the_forecast_or_from_the_same_week_fails():
    late_source = _history()
    late_source.loc[1, "source_kickoff_utc"] = (
        "2026-10-05T18:00:00Z"  # +6h is after as_of
    )
    assert _rules(_audit(history=late_source)) == {"a_rating_inputs"}
    same_week = _history()
    same_week.loc[1, "source_week"] = 6
    receipt = _audit(history=same_week)
    assert _rules(receipt) == {"a_rating_inputs"}
    assert any("not an earlier week" in v["detail"] for v in receipt["violations"])


def test_the_six_hour_availability_boundary_is_inclusive():
    history = _history()
    history.loc[1, "source_kickoff_utc"] = (
        "2026-10-05T06:00:00Z"  # available exactly 12:00Z
    )
    assert _audit(history=history)["state"] == "passed"
    history.loc[1, "source_kickoff_utc"] = "2026-10-05T06:00:01Z"
    assert _rules(_audit(history=history)) == {"a_rating_inputs"}


def test_a_rating_state_cutoff_after_the_forecast_fails():
    states = _states()
    states.loc[1, "state_cutoff_utc"] = "2026-10-06T00:00:00Z"
    assert _rules(_audit(states=states)) == {"b_rating_state"}


def test_a_forecast_after_kickoff_fails_and_equal_is_allowed():
    receipt = _audit(forecasts=_forecasts(as_of5="2026-10-02T00:00:01Z"))
    assert "c_forecast_time" in _rules(receipt)
    assert any(g["game_id"] == 1 and not g["passed"] for g in receipt["games"])
    equal = _forecasts(as_of5="2026-10-02T00:00:00Z")
    assert "c_forecast_time" not in _rules(_audit(forecasts=equal))


def test_a_week_6_forecast_after_the_first_midweek_kickoff_fails():
    forecasts = _forecasts(as_of6="2026-10-07T12:00:00Z")  # after game 3 (Oct 7 00:00Z)
    runs = _runs()
    runs.loc[runs.week == 6, "forecast_as_of"] = "2026-10-07T12:00:00Z"
    receipt = _audit(forecasts=forecasts, runs=runs)
    assert {"c_forecast_time", "g_cutoff_coherence"} <= _rules(receipt)
    # A display-only run covers only later games, so the slate rule does not apply to it.
    runs["display_only"] = True
    receipt = _audit(forecasts=forecasts, runs=runs)
    assert "g_cutoff_coherence" not in _rules(receipt)


def test_a_post_kickoff_quote_needs_the_exact_declared_cfbd_exception():
    assert _audit(accepted_late=[])["state"] == "failed"
    assert _rules(_audit(accepted_late=[])) == {"d_quote_time"}
    for field, value in (
        ("reason", "because"),
        ("provider", "odds_api"),
        ("entity", "market_quotes"),
        ("quote_id", "other"),
        ("target", "total"),
        ("game_id", 4),
    ):
        entry = {**LATE, field: value}
        assert _rules(_audit(accepted_late=[entry])) == {"d_quote_time"}, field
    odds_quote = _quotes(late=True)
    odds_quote.loc[odds_quote.game_id == 3, "provider"] = "odds_api"
    assert _rules(_audit(quotes=odds_quote)) == {"d_quote_time"}


def test_a_quote_after_the_market_cutoff_fails_even_if_before_kickoff():
    quotes = _quotes(late=True)
    quotes.loc[quotes.game_id == 4, "captured_at"] = (
        "2026-10-08T16:21:00Z"  # market 16:20Z
    )
    assert _rules(_audit(quotes=quotes)) == {"d_quote_time"}


def test_unused_exceptions_are_reported_not_silently_kept():
    receipt = _audit(quotes=_quotes(late=False), accepted_late=[LATE])
    assert receipt["state"] == "passed"
    assert receipt["accepted_late_unused"] == [LATE]


@pytest.mark.parametrize(
    "bundle, declared",
    [
        ({"development_seasons": [2021, 2026]}, SHA),
        ({"development_seasons": [2020, 2021]}, SHA),
        ({"development_seasons": []}, SHA),
        ({}, SHA),
        (BUNDLE, "b" * 64),
    ],
)
def test_model_parameters_must_exclude_2026_and_2020_and_match_the_file(
    bundle, declared
):
    receipt = _audit(bundle=bundle, declared_bundle_sha256=declared)
    assert _rules(receipt) == {"e_model_parameters"}


def test_team_statistics_may_not_be_from_a_later_week():
    usage = pd.DataFrame({"game_id": [1, 2, 3, 4], "stats_as_of_week": [5, 6, 6, 6]})
    assert _rules(_audit(team_stats_usage=usage)) == {"f_team_stats"}


def test_both_cutoffs_must_be_recorded_and_ordered():
    runs = _runs()
    runs.loc[runs.week == 6, "market_as_of"] = None
    assert "g_cutoff_coherence" in _rules(_audit(runs=runs))
    runs = _runs()
    runs.loc[runs.week == 6, "market_as_of"] = "2026-10-04T00:00:00Z"  # before forecast
    assert "g_cutoff_coherence" in _rules(_audit(runs=runs))


def test_a_game_without_a_forecast_fails_closed():
    forecasts = _forecasts().iloc[:3]
    receipt = _audit(forecasts=forecasts)
    assert "c_forecast_time" in _rules(receipt)


def test_malformed_inputs_raise_instead_of_passing():
    with pytest.raises(pit.AuditInputError):
        _audit(quotes=_quotes().drop(columns=["provider"]))
    with pytest.raises(pit.AuditInputError):
        _audit(history=_history().drop(columns=["source_week"]))


def test_the_receipt_is_deterministic():
    assert _audit() == copy.deepcopy(_audit())
