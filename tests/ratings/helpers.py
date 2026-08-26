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
    quarter=1,
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
    offense_score=0,
    defense_score=0,
):
    return {
        "season": season,
        "week": week,
        "game_id": game_id,
        "drive_number": drive_number,
        "quarter": quarter,
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
        "offense_score": offense_score,
        "defense_score": defense_score,
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


HISTORICAL_SEASONS = (2021, 2022, 2023, 2024, 2025)


def multi_season_league(include_completed_2026: bool = True):
    """A compact league per historical season plus protected 2026 targets.

    Each historical season has two weekends of games for the same four teams.
    2026 adds one completed pre-cutoff game and one scheduled future game so
    CLI runs can prove protected-season targets keep strictly prior-only
    measurement evidence.
    """
    byplay = []
    drives = []
    games = []
    outcomes = []
    reconciled = []

    def add_game(
        season,
        week,
        game_id,
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

    for season in HISTORICAL_SEASONS:
        add_game(
            season,
            1,
            season * 100 + 1,
            f"{season}-09-06T18:00:00+00:00",
            "Alpha",
            "Beta",
        )
        add_game(
            season,
            1,
            season * 100 + 2,
            f"{season}-09-06T22:00:00+00:00",
            "Gamma",
            "Delta",
        )
        add_game(
            season,
            2,
            season * 100 + 3,
            f"{season}-09-13T18:00:00+00:00",
            "Alpha",
            "Gamma",
        )
        add_game(
            season,
            2,
            season * 100 + 4,
            f"{season}-09-13T22:00:00+00:00",
            "Beta",
            "Delta",
        )
    if include_completed_2026:
        add_game(2026, 0, 2060, "2026-08-29T19:00:00+00:00", "Alpha", "Beta")
    add_game(
        2026,
        1,
        2061,
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


def stage_rating_parents(storage, league) -> dict[str, list[str]]:
    """Stage immutable parents with season-partitioned byplay/drives refs.

    Historical byplay and drives evidence is staged as one single-season
    dataset per season (matching the lake's season partitioning), while the
    compact schedule, outcome, and reconciliation parents are staged whole.
    """
    import json
    from dataclasses import asdict

    from cks_picks_cfb.data.lake import BuildRequest, build_dataset_version

    uris: dict[str, list[str]] = {"byplay": [], "drives": []}
    for dataset, key, schema_version in (
        ("byplay", "byplay", "byplay_v1"),
        ("drives", "drives", "drives_v1"),
    ):
        for season in HISTORICAL_SEASONS:
            frame = league[key][pd.to_numeric(league[key]["season"]) == season]
            ref, _ = build_dataset_version(
                storage,
                build=BuildRequest(
                    dataset=dataset,
                    parent_refs=(),
                    code_sha="seed",
                    config_sha="seed",
                    as_of=AS_OF,
                    schema_version=schema_version,
                    tier="silver",
                ),
                records=frame.to_dict("records"),
                partitions={"seasons": [season]},
            )
            uri = f"artifacts/test/parents/{dataset}-{season}.json"
            storage.write_bytes(json.dumps(asdict(ref), sort_keys=True).encode(), uri)
            uris[dataset].append(uri)

    for dataset, key, schema_version in (
        ("games", "games", "games_v2"),
        ("game_outcomes", "outcomes", "game_outcomes_v1"),
        ("reconciled_team_game", "reconciled_team_game", "team_game_v1"),
    ):
        ref, _ = build_dataset_version(
            storage,
            build=BuildRequest(
                dataset=dataset,
                parent_refs=(),
                code_sha="seed",
                config_sha="seed",
                as_of=AS_OF,
                schema_version=schema_version,
                tier="silver",
            ),
            records=league[key].to_dict("records"),
        )
        uri = f"artifacts/test/parents/{dataset}.json"
        storage.write_bytes(json.dumps(asdict(ref), sort_keys=True).encode(), uri)
        uris[dataset] = [uri]
    return uris
