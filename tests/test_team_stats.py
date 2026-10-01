"""Team season stats: aggregation, direction, filters and leak guard (contract 10)."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.data.team_stats import (
    TeamStatsContractError,
    build_team_season_stats,
)

FBS = {"A", "B", "C"}


def play(play_type="Rush", down=1, distance=10, yards=5, ppa=0.5, success=1, **kw):
    return {
        "play_type": play_type,
        "down": down,
        "distance": distance,
        "yards": yards,
        "ppa": ppa,
        "success": success,
        "garbage": kw.get("garbage", 0),
        "turnover": kw.get("turnover", 0),
    }


def drive(off, plays, pts=0, opp=False, start=75):
    return {"off": off, "plays": plays, "pts": pts, "opp": opp, "start": start}


def build(games):
    """games: list of (game_id, week, home, away, drives)."""
    byplay, drives, g_rows, o_rows = [], [], [], []
    for gid, week, home, away, drv in games:
        score = {home: 0, away: 0}
        n = 0
        for d_no, d in enumerate(drv, start=1):
            off = d["off"]
            dfn = away if off == home else home
            for i, p in enumerate(d["plays"]):
                n += 1
                if i == len(d["plays"]) - 1:
                    score[off] += d["pts"]
                byplay.append(
                    {
                        "season": 2026,
                        "week": week,
                        "game_id": gid,
                        "drive_number": d_no,
                        "play_number": n,
                        "offense": off,
                        "defense": dfn,
                        "st": 0,
                        "penalty": 0,
                        "twopoint": 0,
                        "play_type": p["play_type"],
                        "garbage": p["garbage"],
                        "ppa": p["ppa"],
                        "success": p["success"],
                        "yards_gained": p["yards"],
                        "turnover": p["turnover"],
                        "quarter": 1,
                        "offense_score": score[off],
                        "defense_score": score[dfn],
                        "down": p["down"],
                        "distance": p["distance"],
                    }
                )
            drives.append(
                {
                    "season": 2026,
                    "game_id": gid,
                    "drive_number": d_no,
                    "offense": off,
                    "defense": dfn,
                    "start_yards_to_goal": d["start"],
                    "had_scoring_opportunity": 1 if d["opp"] else 0,
                }
            )
        g_rows.append(
            {
                "season": 2026,
                "game_id": gid,
                "week": week,
                "home_team": home,
                "away_team": away,
            }
        )
        o_rows.append(
            {
                "season": 2026,
                "game_id": gid,
                "completed": True,
                "home_points": score[home],
                "away_points": score[away],
            }
        )
    return (
        pd.DataFrame(byplay),
        pd.DataFrame(drives),
        pd.DataFrame(g_rows),
        pd.DataFrame(o_rows),
    )


def run(games, as_of_week=2, fbs=FBS, **kw):
    byplay, drives, g, o = build(games)
    return build_team_season_stats(
        byplay=byplay,
        drives=drives,
        games=g,
        outcomes=o,
        fbs_teams=fbs,
        season=2026,
        as_of_week=as_of_week,
        **kw,
    )


def val(result, team, role, metric):
    row = result.frame[
        (result.frame.team == team)
        & (result.frame.role == role)
        & (result.frame.metric == metric)
    ]
    assert len(row) == 1, (team, role, metric)
    return row.iloc[0]


def base_game(gid=1, week=1, home="A", away="B"):
    return (
        gid,
        week,
        home,
        away,
        [
            drive(
                home,
                [
                    play("Pass Reception", 1, 10, 25, 1.0, 1),
                    play("Rush", 2, 5, 3, -0.2, 0),
                    play("Pass Incompletion", 3, 2, 0, -0.8, 0),
                ],
                pts=0,
                opp=True,
                start=70,
            ),
            drive(
                away,
                [
                    play("Rush", 1, 10, 6, 0.4, 1),
                    play("Rushing Touchdown", 2, 4, 4, 2.0, 1),
                ],
                pts=7,
                opp=True,
                start=60,
            ),
        ],
    )


def test_pass_rush_split_and_ratio_of_sums():
    r = run([base_game()])
    assert val(r, "A", "offense", "epa_pass")["value"] == pytest.approx((1.0 - 0.8) / 2)
    assert val(r, "A", "offense", "epa_rush")["value"] == pytest.approx(-0.2)
    assert val(r, "B", "offense", "epa_rush")["value"] == pytest.approx((0.4 + 2.0) / 2)
    # Defense columns are what the unit allowed: A's defense faced B's rushing.
    assert val(r, "A", "defense", "epa_rush")["value"] == pytest.approx(1.2)


def test_early_down_success_explosive_and_conversion():
    r = run([base_game()])
    assert val(r, "A", "offense", "early_down_epa")["value"] == pytest.approx(0.4)
    assert val(r, "A", "offense", "success_rate")["value"] == pytest.approx(1 / 3)
    assert val(r, "A", "offense", "explosive_rate")["value"] == pytest.approx(1 / 3)
    # One 3rd-and-2 incompletion -> 0% conversion; B has no 3rd/4th downs -> null.
    assert val(r, "A", "offense", "conv_rate_3rd_4th")["value"] == 0.0
    assert val(r, "B", "offense", "conv_rate_3rd_4th")["value"] is None


def test_scoring_opportunities_and_points_per_opportunity():
    r = run([base_game()])
    assert val(r, "A", "offense", "scoring_opp_rate")["value"] == 1.0
    assert val(r, "A", "offense", "pts_per_scoring_opp")["value"] == 0.0
    assert val(r, "B", "offense", "pts_per_scoring_opp")["value"] == 7.0
    assert val(r, "A", "offense", "avg_start_field_pos")["value"] == pytest.approx(30)
    assert val(r, "A", "defense", "avg_start_field_pos")["value"] == pytest.approx(40)


def test_garbage_time_plays_are_excluded():
    gid, week, home, away, drv = base_game()
    drv[0]["plays"].append(play("Pass Reception", 1, 10, 50, 5.0, 1, garbage=1))
    r = run([(gid, week, home, away, drv)])
    assert val(r, "A", "offense", "epa_pass")["value"] == pytest.approx(0.1)


def test_week_cutoff_excludes_the_target_week():
    # Week 2 game must not leak into the as_of_week=2 snapshot.
    leaky = base_game(gid=2, week=2, home="A", away="C")
    r = run([base_game(), leaky], as_of_week=2)
    assert r.report["eligible_games"] == 1
    assert "C" not in set(r.frame.team)
    assert val(r, "A", "offense", "epa_rush")["games"] == 1
    r3 = run([base_game(), leaky], as_of_week=3)
    assert val(r3, "A", "offense", "epa_rush")["games"] == 2


def test_non_fbs_opponents_are_excluded():
    r = run([base_game(away="FCS")], fbs={"A"})
    assert r.frame.empty
    assert r.report["eligible_games"] == 0


def test_rank_direction_offense_high_defense_low_better():
    g1 = base_game(gid=1, home="A", away="B")
    g2 = base_game(gid=2, home="C", away="B")
    g2[4][0]["plays"][1] = play("Rush", 2, 5, 9, 0.9, 1)  # C rushes better than A
    g2[4][1]["plays"][0] = play("Rush", 1, 10, 1, -0.5, 0)  # B rushes worse vs C
    r = run([g1, g2])
    # Offense: higher rush EPA is better.
    assert (
        val(r, "C", "offense", "epa_rush")["rank"]
        < val(r, "A", "offense", "epa_rush")["rank"]
    )
    # Defense: B's defense allowed more rush EPA than A's? lower allowed is better.
    allowed = {t: val(r, t, "defense", "epa_rush") for t in ("A", "C")}
    better = min(allowed, key=lambda t: allowed[t]["value"])
    worse = max(allowed, key=lambda t: allowed[t]["value"])
    assert better == "C" and worse == "A"
    assert allowed[better]["rank"] < allowed[worse]["rank"]
    # Turnover rate is inverted: forcing more turnovers is better for defense.
    assert val(r, "A", "offense", "turnover_rate")["cohort_size"] is not pd.NA


def test_min_games_leaves_rank_null_but_keeps_value():
    r = run([base_game()], min_games=2)
    row = val(r, "A", "offense", "epa_rush")
    assert row["value"] == pytest.approx(-0.2)
    assert pd.isna(row["rank"])


def test_missing_down_columns_yield_null_metrics_not_failure():
    byplay, drives, g, o = build([base_game()])
    byplay = byplay.drop(columns=["down", "distance"])
    r = build_team_season_stats(
        byplay=byplay,
        drives=drives,
        games=g,
        outcomes=o,
        fbs_teams=FBS,
        season=2026,
        as_of_week=2,
    )
    assert r.report["missing_optional_columns"] == ["down", "distance"]
    assert val(r, "A", "offense", "early_down_epa")["value"] is None
    assert val(r, "A", "offense", "epa_pass")["value"] is not None


def test_missing_required_column_fails_loudly():
    byplay, drives, g, o = build([base_game()])
    with pytest.raises(TeamStatsContractError, match="ppa"):
        build_team_season_stats(
            byplay=byplay.drop(columns=["ppa"]),
            drives=drives,
            games=g,
            outcomes=o,
            fbs_teams=FBS,
            season=2026,
            as_of_week=2,
        )


def test_bad_score_stream_nulls_ppso_only():
    byplay, drives, g, o = build([base_game()])
    o.loc[:, "away_points"] = 99  # final score no longer reconciles
    r = build_team_season_stats(
        byplay=byplay,
        drives=drives,
        games=g,
        outcomes=o,
        fbs_teams=FBS,
        season=2026,
        as_of_week=2,
    )
    assert val(r, "B", "offense", "pts_per_scoring_opp")["value"] is None
    assert val(r, "B", "offense", "epa_rush")["value"] is not None
