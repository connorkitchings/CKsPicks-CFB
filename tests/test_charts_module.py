"""Chart metric definitions, venue estimator and opponent adjustment."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.charts.adjusted_epa import (
    ADJUSTMENT_METHOD,
    adjusted_epa_window,
    build_team_adjusted_epa,
    estimate_venue_coefficient,
    venue_design,
)
from cks_picks_cfb.charts.roster import RosterError, build_team_season_roster
from cks_picks_cfb.charts.team_game_stats import (
    TEAM_GAME_COLUMNS,
    build_team_game_stats,
)
from cks_picks_cfb.ratings.possession_measurements import adjust_possession_history

# ---------------------------------------------------------------- definitions


def play(game_id, offense, defense, ppa, success, **extra):
    return {
        "season": 2026,
        "game_id": game_id,
        "offense": offense,
        "defense": defense,
        "ppa": ppa,
        "success": success,
        "quarter": 1,
        "st": 0,
        "penalty": 0,
        "twopoint": 0,
        "garbage": 0,
        "play_type": "Rush",
        **extra,
    }


def schedule(*games):
    return pd.DataFrame(
        [
            {"season": 2026, "week": w, "game_id": g, "home_team": h, "away_team": a}
            for g, w, h, a in games
        ]
    )


def finals(*games):
    return pd.DataFrame(
        [
            {"season": 2026, "game_id": g, "home_points": hp, "away_points": ap}
            for g, hp, ap in games
        ]
    )


FBS = {"A", "B", "C", "Z"}


def definitions_case():
    plays = [
        # A offense: 5 eligible plays, EPA valid on 3, success valid on 4.
        play(1, "A", "B", 0.1, 1),
        play(1, "A", "B", 0.2, 0),
        play(1, "A", "B", np.nan, 1),
        play(1, "A", "B", 0.4, np.nan, ppa_missing=True),
        play(1, "A", "B", 0.5, 1),
        play(1, "A", "B", 9.0, 1, garbage=1),  # garbage time: excluded
        play(1, "A", "B", 9.0, 1, play_type="Punt", st=1),  # special teams
        # B offense: success present, every EPA missing.
        play(1, "B", "A", np.nan, 1),
        play(1, "B", "A", np.nan, 0),
        # non-FBS and incomplete games never appear
        play(2, "C", "X", 1.0, 1),
        play(3, "A", "C", 1.0, 1),
    ]
    return {
        "byplay": pd.DataFrame(plays),
        "games": schedule((1, 0, "A", "B"), (2, 0, "C", "X"), (3, 1, "A", "C")),
        "finals": finals((1, 21, 14), (2, 10, 3)),
        "fbs_teams": FBS,
        "neutral_game_ids": set(),
        "season": 2026,
        "active_week": 2,
    }


def test_definitions_count_each_metric_independently():
    out = build_team_game_stats(**definitions_case())
    assert list(out.columns) == list(TEAM_GAME_COLUMNS)
    assert len(out) == 2  # game 2 has a non-FBS side; game 3 has no final
    a = out[out.team == "A"].iloc[0]
    assert (a.off_plays, a.off_success_n, a.off_success_sum) == (5, 4, 3.0)
    assert a.off_epa_n == 3 and a.off_epa_sum == pytest.approx(0.8)
    assert (a.points_for, a.points_against, a.site) == (21, 14, "home")
    assert (a.off_epa_n, a.off_success_n, a.off_plays) != (5, 5, 5)


def test_zero_valid_observations_leave_the_metric_unobserved():
    b = build_team_game_stats(**definitions_case()).query("team == 'B'").iloc[0]
    assert (b.off_plays, b.off_success_n, b.off_epa_n) == (2, 2, 0)
    assert b.off_epa_sum == 0.0


def test_rows_mirror_and_are_sorted_by_key():
    out = build_team_game_stats(**definitions_case())
    a, b = (out[out.team == t].iloc[0] for t in "AB")
    for field in ("plays", "success_n", "success_sum", "epa_n", "epa_sum"):
        assert a[f"off_{field}"] == b[f"def_{field}"]
        assert b[f"off_{field}"] == a[f"def_{field}"]
    assert (a.opponent, b.opponent) == ("B", "A")
    assert (a.points_for, a.points_against) == (b.points_against, b.points_for)
    assert (a.site, b.site) == ("home", "away")
    assert list(out.game_id) == sorted(out.game_id)


def test_neutral_site_is_mirrored_and_weeks_are_windowed():
    case = definitions_case()
    out = build_team_game_stats(**{**case, "neutral_game_ids": {1}})
    assert set(out.site) == {"neutral"}
    assert build_team_game_stats(**{**case, "active_week": 0}).empty


def test_roster_lists_every_fbs_team_including_one_without_games():
    teams = pd.DataFrame(
        [
            {"team": "A", "classification": "fbs", "conference": "SEC"},
            {"team": "Idle", "classification": "FBS", "conference": None},
            {"team": "X", "classification": "fcs", "conference": "CAA"},
        ]
    )
    roster = build_team_season_roster(teams, 2026)
    assert list(roster.team) == ["A", "Idle"]
    assert list(roster.conference) == ["SEC", None]
    with pytest.raises(RosterError):
        build_team_season_roster(teams.drop(columns="conference"), 2026)
    with pytest.raises(RosterError):
        build_team_season_roster(None, 2026)


# ------------------------------------------------------------ venue estimator

TEAMS = list("ABCDEFGH")
MU, H = 0.05, 0.12
OFF = dict(zip(TEAMS, [0.30, -0.10, 0.05, 0.20, -0.25, 0.00, 0.15, -0.05]))
DEF = dict(zip(TEAMS, [-0.10, 0.20, 0.00, -0.15, 0.25, 0.05, -0.20, 0.10]))
#: Unbalanced schedule: (home, away, home plays, away plays)
GAMES = [
    ("A", "B", 70, 55),
    ("C", "A", 62, 80),
    ("B", "D", 58, 66),
    ("D", "E", 75, 49),
    ("E", "C", 53, 71),
    ("F", "A", 64, 60),
    ("G", "H", 90, 40),
    ("H", "F", 45, 77),
    ("A", "G", 68, 51),
    ("C", "H", 59, 63),
    ("G", "B", 72, 57),
    ("E", "F", 66, 48),
    ("D", "H", 61, 69),
]


def game_rows(games=GAMES, h=H, neutral=()):
    """Team-game rows with noiseless EPA following mu + o_i + d_j + h*s."""
    rows = []
    for number, (home, away, home_plays, away_plays) in enumerate(games, start=1):
        s = 0.0 if number in neutral else 1.0
        home_epa = MU + OFF[home] + DEF[away] + h * s
        away_epa = MU + OFF[away] + DEF[home] - h * s
        for team, opponent, site, own, other, epa_own, epa_other in (
            (
                home,
                away,
                "neutral" if s == 0 else "home",
                home_plays,
                away_plays,
                home_epa,
                away_epa,
            ),
            (
                away,
                home,
                "neutral" if s == 0 else "away",
                away_plays,
                home_plays,
                away_epa,
                home_epa,
            ),
        ):
            rows.append(
                {
                    "season": 2026,
                    "week": (number - 1) // 3,
                    "game_id": number,
                    "team": team,
                    "opponent": opponent,
                    "site": site,
                    "off_epa_n": own,
                    "off_epa_sum": epa_own * own,
                    "def_epa_n": other,
                    "def_epa_sum": epa_other * other,
                }
            )
    return pd.DataFrame(rows)


def observations(frame):
    sign = {"home": 1.0, "away": -1.0, "neutral": 0.0}
    return dict(
        offense=frame.team.tolist(),
        defense=frame.opponent.tolist(),
        sign=[sign[s] for s in frame.site],
        y=(frame.off_epa_sum / frame.off_epa_n).tolist(),
        weight=frame.off_epa_n.astype(float).tolist(),
    )


def test_venue_coefficient_is_recovered_where_the_naive_average_is_not():
    obs = observations(game_rows())
    fit = estimate_venue_coefficient(**obs)
    assert fit.identified and fit.coefficient == pytest.approx(H, abs=1e-9)
    y, s = np.array(obs["y"]), np.array(obs["sign"])
    naive = y[s > 0].mean() - y[s < 0].mean()
    assert abs(naive - H) > 1e-3 and abs(naive / 2 - H) > 1e-3


def test_design_columns_follow_the_documented_layout():
    design, teams = venue_design(["B", "A"], ["A", "C"], [1.0, -1.0])
    assert teams == ["A", "B", "C"]
    assert design.shape == (2, 1 + 3 + 3 + 1)
    assert design[0].tolist() == [1, 0, 1, 0, 1, 0, 0, 1]  # int, off B, def A, s
    assert design[1].tolist() == [1, 1, 0, 0, 0, 0, 1, -1]


def test_weights_scale_rows_not_columns():
    """Duplicating a game is the same as doubling its weight."""
    base = game_rows()
    noisy = base.copy()
    noisy.loc[noisy.index[0], "off_epa_sum"] += 5.0  # contradicts the model
    doubled = pd.concat([noisy, noisy.iloc[[0, 1]]], ignore_index=True)
    heavy = noisy.copy()
    heavy.loc[heavy.index[[0, 1]], ["off_epa_n"]] *= 2
    heavy.loc[heavy.index[[0, 1]], ["off_epa_sum"]] *= 2
    a = estimate_venue_coefficient(**observations(doubled)).coefficient
    b = estimate_venue_coefficient(**observations(heavy)).coefficient
    assert a == pytest.approx(b, abs=1e-9)


def test_all_neutral_window_is_not_identified():
    frame = game_rows(neutral=set(range(1, len(GAMES) + 1)))
    assert estimate_venue_coefficient(**observations(frame)) == (0.0, False)
    assert estimate_venue_coefficient([], [], [], [], []) == (0.0, False)


def rank_condition(offense, defense, sign, y, weight):
    design, _ = venue_design(offense, defense, sign)
    root = np.sqrt(np.asarray(weight, dtype=float))
    x = design * root[:, None]
    rcond = max(x.shape) * np.finfo(np.float64).eps
    return np.linalg.matrix_rank(x, rtol=rcond) == (
        np.linalg.matrix_rank(x[:, :-1], rtol=rcond) + 1
    )


def test_disconnected_schedules_follow_the_rank_condition_only():
    games = [("A", "B", 60, 60), ("B", "A", 60, 60), ("C", "D", 60, 60)]
    frame = game_rows(games)
    obs = observations(frame)
    fit = estimate_venue_coefficient(**obs)
    assert fit.identified == rank_condition(**obs)
    assert fit.identified is True and fit.coefficient == pytest.approx(H, abs=1e-9)
    # a one-sided schedule inside each component cannot separate venue
    games = [("A", "B", 60, 60), ("C", "D", 60, 60)]
    obs = observations(game_rows(games))
    assert estimate_venue_coefficient(**obs).identified == rank_condition(**obs)
    assert estimate_venue_coefficient(**obs) == (0.0, False)


def test_near_collinear_venue_column_is_governed_by_rcond():
    obs = observations(game_rows())
    tiny = {**obs, "sign": [s * 1e-16 for s in obs["sign"]]}
    assert estimate_venue_coefficient(**tiny) == (0.0, False)
    small = {**obs, "sign": [s * 1e-6 for s in obs["sign"]]}
    assert estimate_venue_coefficient(**small).identified is True


# ------------------------------------------------------------------ adjustment


def window(frame, as_of_week=99):
    return adjusted_epa_window(frame, set(TEAMS), season=2026, as_of_week=as_of_week)


def plain_history(frame):
    rows = []
    for r in frame.itertuples(index=False):
        for role, prefix in (("offense", "off"), ("defense", "def")):
            n = getattr(r, f"{prefix}_epa_n")
            if n > 0:
                rows.append(
                    {
                        "team": r.team,
                        "unit_role": role,
                        "measurement_id": "epa_per_play",
                        "opponent": r.opponent,
                        "numerator": getattr(r, f"{prefix}_epa_sum"),
                        "denominator": float(n),
                    }
                )
    return pd.DataFrame(rows)


def test_without_venue_effect_the_result_is_plain_adjustment_of_raw():
    frame = game_rows(neutral=set(range(1, len(GAMES) + 1)))
    raw, adjusted = adjust_possession_history(plain_history(frame))
    rows = {(r["team"], r["role"]): r for r in window(frame)}
    for (team, role, _), value in adjusted.items():
        row = rows[(team, role)]
        assert row["adjusted_epa_per_play"] == pytest.approx(value, abs=1e-12)
        assert row["raw_epa_per_play"] == pytest.approx(
            raw[(team, role, "epa_per_play")]
        )
        assert row["venue_correction"] == pytest.approx(0.0, abs=1e-12)
        assert not row["venue_identified"] and row["venue_coefficient"] == 0.0


def test_raw_is_unneutralized_and_decomposition_closes():
    frame = game_rows()
    rows = window(frame)
    plain = plain_history(frame)
    for row in rows:
        mine = plain[(plain.team == row["team"]) & (plain.unit_role == row["role"])]
        assert row["raw_epa_per_play"] == pytest.approx(
            mine.numerator.sum() / mine.denominator.sum()
        )
        identity = (
            row["raw_epa_per_play"]
            - row["venue_correction"]
            - row["opponent_adjustment"]
        )
        assert identity == pytest.approx(row["adjusted_epa_per_play"], abs=1e-12)
        assert row["adjustment_method"] == ADJUSTMENT_METHOD
    assert all(r["venue_identified"] for r in rows)
    assert rows[0]["venue_coefficient"] == pytest.approx(H, abs=1e-9)
    assert any(abs(r["venue_correction"]) > 1e-3 for r in rows)
    assert any(
        r["raw_epa_per_play"] != pytest.approx(r["neutral_epa_per_play"]) for r in rows
    )


def test_adjusted_values_equal_the_unchanged_adjuster_on_the_neutral_baseline():
    frame = game_rows()
    rows = window(frame)
    history = plain_history(frame)
    h = rows[0]["venue_coefficient"]
    site = {(r.game_id, r.team): r.site for r in frame.itertuples()}
    sign = {"home": 1.0, "away": -1.0, "neutral": 0.0}
    pairs = [(r, role) for r in frame.itertuples() for role in ("offense", "defense")]
    neutral_numerators = []
    for r, role in pairs:
        s = sign[site[(r.game_id, r.team)]]
        if role == "offense":
            neutral_numerators.append(r.off_epa_sum - s * h * r.off_epa_n)
        else:
            neutral_numerators.append(r.def_epa_sum + s * h * r.def_epa_n)
    history = history.assign(numerator=neutral_numerators)
    neutral, adjusted = adjust_possession_history(history)
    for row in rows:
        key = (row["team"], row["role"], "epa_per_play")
        assert row["neutral_epa_per_play"] == pytest.approx(neutral[key], abs=1e-12)
        assert row["adjusted_epa_per_play"] == pytest.approx(adjusted[key], abs=1e-12)


def test_ranks_are_min_ranks_among_roster_teams_per_role():
    rows = window(game_rows())
    for role, descending in (("offense", True), ("defense", False)):
        mine = [r for r in rows if r["role"] == role]
        values = [r["adjusted_epa_per_play"] for r in mine]
        assert {r["cohort_size"] for r in mine} == {len(mine)}
        for r in mine:
            better = sum(
                v > r["adjusted_epa_per_play"]
                if descending
                else v < r["adjusted_epa_per_play"]
                for v in values
            )
            assert r["adjusted_rank"] == better + 1


def test_a_team_with_one_observed_role_gets_only_that_row():
    frame = game_rows()
    # Z's opponents never produced valid EPA, so Z has offense but no defense.
    extra = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 0,
                "game_id": 90,
                "team": "Z",
                "opponent": "A",
                "site": "home",
                "off_epa_n": 30,
                "off_epa_sum": 6.0,
                "def_epa_n": 0,
                "def_epa_sum": 0.0,
            },
            {
                "season": 2026,
                "week": 0,
                "game_id": 90,
                "team": "A",
                "opponent": "Z",
                "site": "away",
                "off_epa_n": 0,
                "off_epa_sum": 0.0,
                "def_epa_n": 30,
                "def_epa_sum": 6.0,
            },
        ]
    )
    rows = adjusted_epa_window(
        pd.concat([frame, extra], ignore_index=True),
        set(TEAMS) | {"Z"},
        season=2026,
        as_of_week=99,
    )
    z = [(r["team"], r["role"]) for r in rows if r["team"] == "Z"]
    assert z == [("Z", "offense")]


def test_windows_start_at_week_three_and_stop_at_the_active_week():
    frame = game_rows()
    assert build_team_adjusted_epa(frame, TEAMS, season=2026, active_week=2) == []
    rows = build_team_adjusted_epa(frame, TEAMS, season=2026, active_week=4)
    assert sorted({r["as_of_week"] for r in rows}) == [3, 4]
    window_three = [r for r in rows if r["as_of_week"] == 3]
    assert max(r["epa_n"] for r in window_three) <= max(
        r["epa_n"] for r in rows if r["as_of_week"] == 4
    )


def test_team_outside_the_roster_is_refused():
    with pytest.raises(ValueError, match="roster"):
        adjusted_epa_window(game_rows(), {"A"}, season=2026, as_of_week=99)


def test_tied_adjusted_values_share_the_minimum_rank():
    """Symmetric league: A and B tie for the best offense, C and D for the worst."""
    rows = []
    games = (
        ("A", "C", 0, "home"),
        ("B", "D", 0, "home"),
        ("A", "D", 1, "away"),
        ("B", "C", 1, "away"),
    )
    for number, (team, opponent, week, site) in enumerate(games, start=1):
        other_site = "away" if site == "home" else "home"
        strong = 0.2 if team in "AB" else 0.0
        weak = 0.2 if opponent in "AB" else 0.0
        for who, whom, where, epa in (
            (team, opponent, site, strong),
            (opponent, team, other_site, weak),
        ):
            own, other = (strong, weak) if who == team else (weak, strong)
            rows.append(
                {
                    "season": 2026,
                    "week": week,
                    "game_id": number,
                    "team": who,
                    "opponent": whom,
                    "site": where,
                    "off_epa_n": 50,
                    "off_epa_sum": 50 * own,
                    "def_epa_n": 50,
                    "def_epa_sum": 50 * other,
                }
            )
    out = adjusted_epa_window(
        pd.DataFrame(rows), set("ABCD"), season=2026, as_of_week=99
    )
    offense = {r["team"]: r["adjusted_rank"] for r in out if r["role"] == "offense"}
    assert offense == {"A": 1, "B": 1, "C": 3, "D": 3}
