"""Resume projection (SOS, SOR, WAA) fixtures from the release contract.

Expected values are hand-computed from the contract, not produced by the code under
test. Most fixtures use a synthetic bridge whose win probability is
``Phi(reference_offense - opponent_offense)``; with equal offense ratings that is
exactly 0.5, so the expected numbers are simple fractions.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.season.projection_resume import (
    MarginBridge,
    TeamResume,
    _sor,
    at_least_wins_probability,
    build_team_resume,
    completed_game_ids,
    elite_reference_members,
    load_pinned_bridge,
    rank_order,
    win_probability,
)
from cks_picks_cfb.season.projection_serving import BRIDGE_SHA256
from tests.season_fixtures import BRIDGE_FIXTURE

REPO_ROOT = Path(__file__).resolve().parents[1]
PINNED_BUNDLE = BRIDGE_FIXTURE

#: Margin = offense(home) - offense(away); sigma 1, so P(ref wins) = Phi(off_ref - off_opp).
SYNTHETIC = MarginBridge(
    intercept=0.0,
    home_offense=1.0,
    home_defense=0.0,
    away_offense=-1.0,
    away_defense=0.0,
    sigma=1.0,
)
CUTOFF = "2026-09-05T00:00:00Z"
AFTER = "2026-09-12T16:00:00Z"


def _ratings(
    rows: list[tuple[str, float, float, float]],
    *,
    period_id: str = "post-week-1",
    cutoff: str = CUTOFF,
    post_week: int | None = 1,
) -> pd.DataFrame:
    """Rows are (team, offense, defense, overall)."""
    return pd.DataFrame(
        [
            {
                "period_id": period_id,
                "cutoff_utc": cutoff,
                "post_week": post_week,
                "team": team,
                "offense_rating": offense,
                "defense_rating": defense,
                "overall_rating": overall,
            }
            for team, offense, defense, overall in rows
        ]
    )


def _schedule(*games: tuple[int, str, str, str]) -> pd.DataFrame:
    """Rows are (game_id, kickoff_utc, home_team, away_team)."""
    return pd.DataFrame(
        [
            {"game_id": g, "kickoff_utc": k, "home_team": h, "away_team": a}
            for g, k, h, a in games
        ],
        columns=["game_id", "kickoff_utc", "home_team", "away_team"],
    )


def _finals(*scores: tuple[int, float, float]) -> pd.DataFrame:
    """Rows are (game_id, home_points, away_points)."""
    return pd.DataFrame(
        [{"game_id": g, "home_points": h, "away_points": a} for g, h, a in scores],
        columns=["game_id", "home_points", "away_points"],
    )


def _build(ratings, schedule, finals, fbs=None, bridge=SYNTHETIC) -> list[TeamResume]:
    teams = set(ratings["team"]) if fbs is None else fbs
    return build_team_resume(
        ratings=ratings,
        schedule=schedule,
        finals=finals,
        fbs_teams=teams,
        bridge=bridge,
    )


def _row(rows: list[TeamResume], team: str, period_id: str = "post-week-1"):
    (match,) = [r for r in rows if r.team == team and r.period_id == period_id]
    return match


def _league30() -> list[tuple[str, float, float, float]]:
    """T01..T30 by overall rating. Ranks 1-25 have offense 1.0, rank 26 has -1.0,
    ranks 27-30 have 0.0. Defense is irrelevant to these fixtures."""
    rows = []
    for rank in range(1, 31):
        offense = 1.0 if rank <= 25 else (-1.0 if rank == 26 else 0.0)
        rows.append((f"T{rank:02d}", offense, 0.0, 100.0 - rank))
    return rows


def _league30_teams() -> list[str]:
    return [f"T{rank:02d}" for rank in range(1, 31)]


def _league30_schedule() -> pd.DataFrame:
    """Every league team plays T29 once, after CUTOFF, so each team is scheduled."""
    games = [
        (rank, AFTER, f"T{rank:02d}", "T29") for rank in range(1, 31) if rank != 29
    ]
    return _schedule(*games)


def _round_robin_schedule() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Four teams, six games, all completed by CUTOFF-era finals.

    Records: A 3-0, B 2-1, C 1-2, D 0-3.
    """
    schedule = _schedule(
        (1, "2026-08-30T16:00:00Z", "A", "B"),
        (2, "2026-08-31T16:00:00Z", "C", "A"),
        (3, "2026-09-01T16:00:00Z", "A", "D"),
        (4, "2026-09-02T16:00:00Z", "B", "C"),
        (5, "2026-09-03T16:00:00Z", "D", "B"),
        (6, "2026-09-04T16:00:00Z", "C", "D"),
    )
    finals = _finals(
        (1, 28, 14),
        (2, 17, 24),
        (3, 31, 10),
        (4, 21, 7),
        (5, 3, 20),
        (6, 24, 13),
    )
    return schedule, finals


def _zero_ratings(teams: list[str], period_id: str = "post-week-1") -> pd.DataFrame:
    return _ratings(
        [(team, 0.0, 0.0, 100.0 - index) for index, team in enumerate(teams)],
        period_id=period_id,
    )


# --- Fixture 1: Poisson-binomial worked example -----------------------------------


def test_poisson_binomial_three_wins_gives_sor_73() -> None:
    p_at_least_three = at_least_wins_probability([0.9, 0.6, 0.5], 3)

    assert p_at_least_three == pytest.approx(0.27)
    assert (1 - p_at_least_three) * 100 == pytest.approx(73.0)


def test_poisson_binomial_two_wins_gives_sor_25() -> None:
    p_at_least_two = at_least_wins_probability([0.9, 0.6, 0.5], 2)

    assert p_at_least_two == pytest.approx(0.75)
    assert (1 - p_at_least_two) * 100 == pytest.approx(25.0)


def test_sor_worked_examples_map_probability_to_sor() -> None:
    assert _sor(0.27) == pytest.approx(73.0)
    assert _sor(0.75) == pytest.approx(25.0)


def test_zero_wins_over_twelve_coin_flips_gives_sor_positive_zero() -> None:
    # Each game is 0.5, so every binomial mass is an exact power of two and P is exactly 1.
    p_at_least_zero = at_least_wins_probability([0.5] * 12, 0)

    assert p_at_least_zero == 1.0
    sor = _sor(p_at_least_zero)
    assert sor == 0.0
    assert math.copysign(1.0, sor) == 1.0


def test_overshooting_probability_sum_is_clamped_and_sor_never_negative() -> None:
    # Unclamped, the convolution of these 27 games sums to 1.0000000000000002.
    probs = [round(0.1 * i, 1) for i in range(1, 10)] * 3

    p_at_least_zero = at_least_wins_probability(probs, 0)

    assert p_at_least_zero == 1.0
    sor = _sor(p_at_least_zero)
    assert sor == 0.0
    assert math.copysign(1.0, sor) == 1.0
    assert _sor(1.0000000000000002) == 0.0
    assert math.copysign(1.0, _sor(1.0000000000000002)) == 1.0


def test_at_least_wins_probability_stays_in_unit_interval_and_non_increasing() -> None:
    probs = [round(0.1 * i, 1) for i in range(1, 10)] * 3
    games = len(probs)

    values = [at_least_wins_probability(probs, wins) for wins in range(games + 1)]

    assert all(0.0 <= value <= 1.0 for value in values)
    assert all(earlier >= later for earlier, later in zip(values, values[1:]))
    assert values[0] == 1.0
    assert at_least_wins_probability(probs, games + 1) == 0.0


def test_team_sor_from_coin_flip_round_robin_matches_hand_values() -> None:
    schedule, finals = _round_robin_schedule()
    ratings = _zero_ratings(["A", "B", "C", "D"])

    rows = _build(ratings, schedule, finals)

    expected = {
        # team: (wins, sor_p, sor, sor_rank, waa)
        "A": (3, 0.125, 87.5, 1, 1.5),
        "B": (2, 0.5, 50.0, 2, 0.5),
        "C": (1, 0.875, 12.5, 3, -0.5),
        "D": (0, 1.0, 0.0, 4, -1.5),
    }
    for team, (wins, sor_p, sor, sor_rank, waa) in expected.items():
        row = _row(rows, team)
        assert row.wins == wins
        assert row.sor_p == pytest.approx(sor_p)
        assert row.sor == pytest.approx(sor)
        assert row.sor_rank == sor_rank
        assert row.waa == pytest.approx(waa)


# --- Fixtures 2-5: elite reference self-exclusion ---------------------------------


def test_top25_team_reference_excludes_self_and_includes_26th() -> None:
    members = elite_reference_members(_league30_teams())
    expected = {f"T{i:02d}" for i in range(1, 27)} - {"T07"}

    assert set(members["T07"]) == expected
    assert len(members["T07"]) == 25


def test_top25_team_sos_uses_self_excluded_reference_value() -> None:
    # Reference offense = (24 * 1.0 + (-1.0)) / 25 = 0.92; opponent offense 0.
    # Opponent difficulty = 1 - Phi(0.92) = 0.17879, so SOS = 17.879.
    rows = _build(_ratings(_league30()), _league30_schedule(), _finals())

    assert _row(rows, "T07").sos_full_elite == pytest.approx(17.879, abs=1e-3)


def test_26th_ranked_team_uses_plain_top25_mean_without_self_exclusion() -> None:
    members = elite_reference_members(_league30_teams())

    assert set(members["T26"]) == {f"T{i:02d}" for i in range(1, 26)}
    rows = _build(_ratings(_league30()), _league30_schedule(), _finals())
    # Reference offense = 1.0; difficulty = 1 - Phi(1.0) = 0.15866.
    assert _row(rows, "T26").sos_full_elite == pytest.approx(15.866, abs=1e-3)


def test_rank30_team_uses_plain_top25_mean_not_the_rank7_reference() -> None:
    members = elite_reference_members(_league30_teams())

    assert set(members["T30"]) == {f"T{i:02d}" for i in range(1, 26)}
    rows = _build(_ratings(_league30()), _league30_schedule(), _finals())
    assert _row(rows, "T30").sos_full_elite == pytest.approx(15.866, abs=1e-3)
    assert _row(rows, "T30").sos_full_elite != pytest.approx(
        _row(rows, "T07").sos_full_elite
    )


def test_each_top25_team_gets_its_own_self_excluded_reference() -> None:
    teams = _league30_teams()
    members = elite_reference_members(teams)
    top25 = set(teams[:25])
    rank26 = {"T26"}

    self_excluded = {}
    for team in teams[:25]:
        assert set(members[team]) == (top25 | rank26) - {team}
        assert len(members[team]) == 25
        self_excluded[team] = frozenset(members[team])
    assert len(set(self_excluded.values())) == 25
    assert set(members["T26"]) == top25
    assert set(members["T30"]) == top25


# --- Fixture 6: rank-25 tie --------------------------------------------------------


def test_rank25_tie_is_broken_by_team_name_ascending_regardless_of_input_order() -> (
    None
):
    overall = {f"T{i:02d}": 100.0 - i for i in range(1, 25)}
    overall["Zulu"] = 10.0
    overall["Bravo"] = 50.0
    overall["Alpha"] = 50.0
    expected = [f"T{i:02d}" for i in range(1, 25)] + ["Alpha", "Bravo", "Zulu"]

    assert rank_order(overall) == expected
    assert rank_order(dict(reversed(list(overall.items())))) == expected

    members = elite_reference_members(expected)
    assert "Bravo" in members["Alpha"]
    assert "Alpha" not in members["Alpha"]
    assert "Alpha" in members["Bravo"]
    assert "Bravo" not in members["Bravo"]


# --- Fixture 7: unfinished game before the cutoff ---------------------------------


def test_kicked_off_game_without_final_changes_no_record_or_played_metric() -> None:
    schedule, finals = _round_robin_schedule()
    ratings = _zero_ratings(["A", "B", "C", "D"])
    base = _row(_build(ratings, schedule, finals), "A")

    unfinished = _schedule(
        *[
            (int(g), k, h, a)
            for g, k, h, a in schedule.itertuples(index=False, name=None)
        ],
        (99, "2026-09-03T12:00:00Z", "A", "C"),
    )
    with_unfinished = _row(_build(ratings, unfinished, finals), "A")

    assert with_unfinished.completed_games == base.completed_games == 3
    assert with_unfinished.wins == base.wins
    assert with_unfinished.losses == base.losses
    assert with_unfinished.sos_played_elite == pytest.approx(base.sos_played_elite)
    assert with_unfinished.sor == pytest.approx(base.sor)
    assert with_unfinished.waa == pytest.approx(base.waa)
    assert with_unfinished.scheduled_games == base.scheduled_games + 1


# --- Fixture 8: preseason and short résumé ----------------------------------------


def test_short_resume_has_null_sor_and_waa_but_keeps_sos() -> None:
    schedule = _schedule(
        (1, "2026-09-01T16:00:00Z", "A", "B"),
        (2, "2026-09-02T16:00:00Z", "C", "A"),
        (3, "2026-09-10T16:00:00Z", "A", "D"),
    )
    finals = _finals((1, 28, 14), (2, 24, 17))
    ratings = _zero_ratings(["A", "B", "C", "D"])

    row = _row(_build(ratings, schedule, finals), "A")

    assert row.completed_games == 2
    assert (row.wins, row.losses) == (1, 1)
    assert row.sor is None
    assert row.sor_p is None
    assert row.sor_rank is None
    assert row.waa is None
    assert row.sos_played_elite == pytest.approx(50.0)
    assert row.sos_remaining_elite == pytest.approx(50.0)
    assert row.sos_full_elite == pytest.approx(50.0)


def test_preseason_has_null_played_sor_and_waa_with_full_and_remaining_sos() -> None:
    schedule = _schedule(
        (1, "2026-09-01T16:00:00Z", "A", "B"),
        (2, "2026-09-02T16:00:00Z", "C", "A"),
        (3, "2026-09-10T16:00:00Z", "A", "D"),
    )
    ratings = _zero_ratings(["A", "B", "C", "D"], period_id="preseason")
    ratings["cutoff_utc"] = "2026-08-01T00:00:00Z"
    ratings["post_week"] = None

    row = _row(_build(ratings, schedule, _finals()), "A", period_id="preseason")

    assert row.post_week is None
    assert row.completed_games == 0
    assert row.wins == 0
    assert row.sos_played_elite is None
    assert row.sor is None
    assert row.waa is None
    assert row.sos_remaining_elite == pytest.approx(50.0)
    assert row.sos_full_elite == pytest.approx(50.0)


# --- Fixture 9: FCS opponent excluded ----------------------------------------------


def test_fcs_opponent_is_excluded_from_record_sos_and_sor() -> None:
    schedule = _schedule(
        (1, "2026-08-30T16:00:00Z", "A", "B"),
        (2, "2026-08-31T16:00:00Z", "C", "A"),
        (3, "2026-09-01T16:00:00Z", "D", "A"),
        (4, "2026-09-02T16:00:00Z", "Tiny", "A"),
    )
    finals = _finals((1, 28, 14), (2, 10, 17), (3, 24, 20), (4, 7, 27))
    # Tiny is rated and very strong, so a leak would move the averages off 0.
    ratings = _ratings(
        [
            ("A", 0.0, 0.0, 40.0),
            ("B", 0.0, 0.0, 39.0),
            ("C", 0.0, 0.0, 38.0),
            ("D", 0.0, 0.0, 37.0),
            ("Tiny", 10.0, 0.0, 50.0),
        ]
    )

    rows = _build(ratings, schedule, finals, fbs={"A", "B", "C", "D"})
    row = _row(rows, "A")

    assert (row.wins, row.losses) == (2, 1)
    assert row.completed_games == 3
    assert row.scheduled_games == 3
    assert row.sos_full_elite == pytest.approx(50.0)
    assert row.sor == pytest.approx(50.0)
    assert row.waa == pytest.approx(0.5)
    assert all(r.team != "Tiny" for r in rows)


# --- Fixture 10: equal final score ---------------------------------------------------


def test_equal_final_score_raises_value_error() -> None:
    schedule, _ = _round_robin_schedule()
    tied = _finals((1, 14, 14))

    with pytest.raises(ValueError, match="cannot end tied"):
        _build(_zero_ratings(["A", "B", "C", "D"]), schedule, tied)


# --- Fixture 11: completed-set parity -------------------------------------------------


def test_completed_set_is_kickoff_before_cutoff_with_a_final() -> None:
    schedule = _schedule(
        (1, "2026-09-01T16:00:00Z", "A", "B"),
        (2, "2026-09-02T16:00:00Z", "C", "A"),
        (3, "2026-09-20T16:00:00Z", "A", "D"),
    )
    finals = _finals((1, 28, 14), (3, 21, 17))

    assert completed_game_ids(schedule, finals, CUTOFF) == {1}
    assert completed_game_ids(schedule, finals, "2026-09-30T00:00:00Z") == {1, 3}


def _serving_parity_path() -> Path:
    return Path(os.environ.get("CKS_PARITY_SERVING_JSON", ""))


@pytest.mark.skipif(
    not _serving_parity_path().is_file(),
    reason="set CKS_PARITY_SERVING_JSON to a served serving-projections.json",
)
def test_completed_set_matches_game_results_filtered_by_cutoff_for_every_period() -> (
    None
):
    served = json.loads(_serving_parity_path().read_bytes())
    games = pd.DataFrame(served["games"])
    results = pd.DataFrame(served["game_results"])
    schedule = pd.DataFrame(
        {
            "game_id": games["game_id"],
            "kickoff_utc": games["start_date"],
            "home_team": games["home_team"],
            "away_team": games["away_team"],
        }
    )
    finals = results[["game_id", "home_points", "away_points"]]
    cutoffs = {
        row["cutoff_utc"]
        for row in served["v5_rating_snapshots"]
        if row["snapshot_class"] == "current"
    }
    assert cutoffs
    kickoff = dict(zip(games["game_id"], pd.to_datetime(games["start_date"], utc=True)))
    for cutoff in sorted(cutoffs):
        expected = {
            int(row["game_id"])
            for row in served["game_results"]
            if kickoff[row["game_id"]] <= pd.Timestamp(cutoff)
        }
        assert completed_game_ids(schedule, finals, cutoff) == expected


# --- Fixture 12: short rating table ----------------------------------------------------


def test_short_table_elite_reference_is_all_other_teams() -> None:
    members = elite_reference_members(["A", "B", "C", "D"])

    assert set(members["A"]) == {"B", "C", "D"}
    assert set(members["D"]) == {"A", "B", "C"}
    schedule, finals = _round_robin_schedule()
    rows = _build(_zero_ratings(["A", "B", "C", "D"]), schedule, finals)
    row = _row(rows, "A")
    assert row.elite_reference_size == 3
    assert row.elite_reference_kind == "top25_excluding_self"
    assert row.average_reference_size == 4


# --- Determinism and bridge ---------------------------------------------------------


def test_output_does_not_depend_on_input_row_order() -> None:
    schedule, finals = _round_robin_schedule()
    ratings = _zero_ratings(["A", "B", "C", "D"])
    forward = _build(ratings, schedule, finals)
    reverse = _build(ratings.iloc[::-1], schedule.iloc[::-1], finals.iloc[::-1])

    assert forward == reverse


def test_pinned_bridge_coefficients_come_from_the_artifact() -> None:
    assert hashlib.sha256(PINNED_BUNDLE.read_bytes()).hexdigest() == BRIDGE_SHA256

    bridge = load_pinned_bridge(PINNED_BUNDLE)

    assert bridge.intercept == pytest.approx(6.5442094507, abs=1e-9)
    assert bridge.home_offense == pytest.approx(8.5067766511, abs=1e-9)
    assert bridge.home_defense == pytest.approx(9.8433322793, abs=1e-9)
    assert bridge.away_offense == pytest.approx(-10.2416516547, abs=1e-9)
    assert bridge.away_defense == pytest.approx(-10.9680927057, abs=1e-9)
    assert bridge.sigma == pytest.approx(17.8226309998, abs=1e-9)


def test_pinned_bridge_gives_home_advantage_for_equal_teams() -> None:
    bridge = load_pinned_bridge(PINNED_BUNDLE)

    home = win_probability(
        bridge, reference_is_home=True, reference=(0.0, 0.0), opponent=(0.0, 0.0)
    )
    away = win_probability(
        bridge, reference_is_home=False, reference=(0.0, 0.0), opponent=(0.0, 0.0)
    )
    # Phi(6.5442 / 17.8226) = Phi(0.3672) ~= 0.6433 from the standard normal table.
    assert home == pytest.approx(0.6433, abs=1e-4)
    assert away == pytest.approx(1 - home, abs=1e-12)


def test_tampered_bridge_bytes_fail_the_pin(tmp_path: Path) -> None:
    tampered = tmp_path / "bundle.json"
    tampered.write_bytes(PINNED_BUNDLE.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="pinned"):
        load_pinned_bridge(tampered)
