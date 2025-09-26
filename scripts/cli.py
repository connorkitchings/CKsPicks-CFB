"""
CLI entrypoint for Vibe Coding utility scripts.

This script aggregates subcommands from init_session, init_template, and check_links.

Usage:
    python scripts/cli.py [subcommand]

Subcommands:
    init-session
    init-template
    check-links
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import typer
from typing_extensions import Annotated

from cfb_model.data.ingestion import (
    BettingLinesIngester,
    CoachesIngester,
    GamesIngester,
    GameStatsIngester,
    PlaysIngester,
    RostersIngester,
    TeamsIngester,
    VenuesIngester,
)
from cfb_model.data.aggregations.persist import (
    persist_preaggregations,
    persist_byplay_only,
)

app = typer.Typer(help="CFB Model CLI for data ingestion and processing.")


@app.command()
def ingest(
    entity: Annotated[
        str, typer.Argument(help="Entity type to ingest", case_sensitive=False)
    ],
    year: Annotated[int, typer.Option(help="Year to ingest data for")] = 2024,
    season_type: Annotated[
        str, typer.Option(help="Season type for games/plays")
    ] = "regular",
    data_root: Annotated[
        str, typer.Option(help="Absolute path to the root directory for data storage.")
    ] = None,
    limit_games: Annotated[
        int, typer.Option(help="Limit number of games for testing")
    ] = None,
    limit_teams: Annotated[
        int, typer.Option(help="Limit number of teams for testing")
    ] = None,
):
    """Ingest data from the CFBD API."""
    ingester_map = {
        "teams": TeamsIngester,
        "venues": VenuesIngester,
        "games": GamesIngester,
        "betting_lines": BettingLinesIngester,
        "rosters": RostersIngester,
        "coaches": CoachesIngester,
        "plays": PlaysIngester,
        "game_stats_raw": GameStatsIngester,
    }
    ingester_class = ingester_map.get(entity.lower())
    if not ingester_class:
        print(f"Error: Unknown entity '{entity}'")
        raise typer.Exit(code=1)

    kwargs = {"year": year, "data_root": data_root}
    if entity in ["games", "betting_lines", "plays", "game_stats_raw"]:
        kwargs["season_type"] = season_type
    if entity in ["betting_lines", "plays", "game_stats_raw"]:
        kwargs["limit_games"] = limit_games
    if entity in ["rosters", "coaches"]:
        kwargs["limit_teams"] = limit_teams

    ingester = ingester_class(**kwargs)
    ingester.run()


@app.command()
def aggregate(
    command: Annotated[
        str, typer.Argument(help="Aggregation command to run", case_sensitive=False)
    ],
    year: Annotated[int, typer.Option(help="Season year")] = 2024,
    quiet: Annotated[bool, typer.Option(help="Reduce per-game logging")] = False,
):
    """Run data aggregation pipelines."""
    if command == "preagg":
        persist_preaggregations(year=year, verbose=not quiet)
    elif command == "byplay":
        persist_byplay_only(year=year, verbose=not quiet)
    else:
        print(f"Error: Unknown aggregate command '{command}'")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
