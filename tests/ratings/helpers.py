"""Hand-built league fixtures for the Phase 1 rating measurement tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

AS_OF = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)


def play_row(
    *,
    season=2025,
    week=1,
    game_id=1,
    drive_number=1,
    play_number=1,
    offense="Alpha",
    defense="Beta",
    st=0,
    penalty=0,
    twopoint=0,
    play_type="Rush",
    garbage=0,
    ppa=0.2,
    success=1,
    yards_gained=5,
    turnover=0,
):
    return {
        "season": season,
        "week": week,
        "game_id": game_id,
        "drive_number": drive_number,
        "play_number": play_number,
        "offense": offense,
        "defense": defense,
        "st": st,
        "penalty": penalty,
        "twopoint": twopoint,
        "play_type": play_type,
        "garbage": garbage,
        "ppa": ppa,
        "success": success,
        "yards_gained": yards_gained,
        "turnover": turnover,
    }


def drive_row(
    *,
    season=2025,
    week=1,
    game_id=1,
    drive_number=1,
    offense="Alpha",
    defense="Beta",
    start_yards_to_goal=80,
    had_scoring_opportunity=1,
    points=7,
    points_on_opps=7,
):
    return {
        "season": season,
        "week": week,
        "game_id": game_id,
        "drive_number": drive_number,
        "offense": offense,
        "defense": defense,
        "drive_plays": 4,
        "drive_yards": 25,
        "start_yards_to_goal": start_yards_to_goal,
        "end_yards_to_goal": 55,
        "had_scoring_opportunity": had_scoring_opportunity,
        "points": points,
        "points_on_opps": points_on_opps,
        "turnovers": 0,
    }


def game_row(
    *,
    season=2025,
    game_id=1,
    week=1,
    kickoff_utc="2025-09-06T18:00:00+00:00",
    home_team="Alpha",
    away_team="Beta",
    completed=True,
    status="completed",
):
    return {
        "season": season,
        "game_id": game_id,
        "week": week,
        "provider_week": week,
        "kickoff_utc": kickoff_utc,
        "home_team": home_team,
        "away_team": away_team,
        "completed": completed,
        "status": status,
    }


def outcome_row(
    *, season=2025, game_id=1, home_points=31, away_points=17, completed=True
):
    return {
        "season": season,
        "game_id": game_id,
        "completed": completed,
        "home_points": home_points,
        "away_points": away_points,
    }


def reconciled_row(*, season=2025, game_id=1, team="Alpha"):
    return {"season": season, "game_id": game_id, "team": team}


def simple_league():
    """Two weekends for four teams plus one protected 2026 game.

    Games:
      2025 week 1 (Sep 6): 1 Alpha-Beta, 2 Gamma-Delta
      2025 week 2 (Sep 13): 3 Alpha-Gamma, 4 Beta-Delta
      2026 week 0 (Aug 29): 5 Alpha-Beta (completed before as_of)
      2026 week 1 (Sep 5): 6 Gamma-Delta (scheduled, future)
    """
    byplay = []
    drives = []
    games = []
    outcomes = []
    reconciled = []

    def add_game(
        game_id,
        season,
        week,
        kickoff,
        home,
        away,
        completed=True,
        status="completed",
    ):
        games.append(
            game_row(
                season=season,
                game_id=game_id,
                week=week,
                kickoff_utc=kickoff,
                home_team=home,
                away_team=away,
                completed=completed,
                status=status,
            )
        )
        outcomes.append(outcome_row(season=season, game_id=game_id))
        reconciled.append(reconciled_row(season=season, game_id=game_id, team=home))
        reconciled.append(reconciled_row(season=season, game_id=game_id, team=away))
        for drive_number, (offense, defense) in enumerate(
            [(home, away), (away, home)], start=1
        ):
            for play_number in range(1, 3):
                byplay.append(
                    play_row(
                        season=season,
                        week=week,
                        game_id=game_id,
                        drive_number=drive_number,
                        play_number=play_number,
                        offense=offense,
                        defense=defense,
                        ppa=0.25 if offense == home else -0.1,
                        success=1 if offense == home else 0,
                        yards_gained=25 if play_number == 1 else 4,
                    )
                )
            drives.append(
                drive_row(
                    season=season,
                    week=week,
                    game_id=game_id,
                    drive_number=drive_number,
                    offense=offense,
                    defense=defense,
                    start_yards_to_goal=75,
                    had_scoring_opportunity=1,
                    points=7 if offense == home else 3,
                    points_on_opps=7 if offense == home else 3,
                )
            )

    add_game(1, 2025, 1, "2025-09-06T18:00:00+00:00", "Alpha", "Beta")
    add_game(2, 2025, 1, "2025-09-06T22:00:00+00:00", "Gamma", "Delta")
    add_game(3, 2025, 2, "2025-09-13T18:00:00+00:00", "Alpha", "Gamma")
    add_game(4, 2025, 2, "2025-09-13T22:00:00+00:00", "Beta", "Delta")
    add_game(5, 2026, 0, "2026-08-29T19:00:00+00:00", "Alpha", "Beta")
    add_game(
        6,
        2026,
        1,
        "2026-09-05T19:00:00+00:00",
        "Gamma",
        "Delta",
        completed=False,
        status="scheduled",
    )

    return {
        "byplay": pd.DataFrame(byplay),
        "drives": pd.DataFrame(drives),
        "games": pd.DataFrame(games),
        "outcomes": pd.DataFrame(outcomes),
        "reconciled_team_game": pd.DataFrame(reconciled),
    }
