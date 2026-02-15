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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
from dataclasses import dataclass
from typing import Iterable, Sequence

import typer
from typing_extensions import Annotated

from cks_picks_cfb.config import REPORTS_DIR, get_data_root
from cks_picks_cfb.data.base import BaseIngester
from cks_picks_cfb.data.betting_lines import BettingLinesIngester
from cks_picks_cfb.data.coaches import CoachesIngester
from cks_picks_cfb.data.game_stats import GameStatsIngester
from cks_picks_cfb.data.games import GamesIngester
from cks_picks_cfb.data.plays import PlaysIngester
from cks_picks_cfb.data.rosters import RostersIngester
from cks_picks_cfb.data.teams import TeamsIngester
from cks_picks_cfb.data.venues import VenuesIngester
from cks_picks_cfb.features.persist import (
    persist_byplay_only,
    persist_preaggregations,
)
from cks_picks_cfb.utils.local_storage import LocalStorage
from scripts.analysis import analysis_cli
from scripts.pipeline import training_cli


@dataclass(frozen=True)
class IngestionTask:
    """Metadata describing a runnable ingestion step."""

    key: str
    cls: type[BaseIngester]
    supports_season_type: bool = False
    supports_week: bool = False
    week_kwarg: str = "week"
    supports_limit_games: bool = False
    supports_limit_teams: bool = False


INGESTION_REGISTRY: dict[str, IngestionTask] = {
    "teams": IngestionTask("teams", TeamsIngester),
    "venues": IngestionTask("venues", VenuesIngester),
    "games": IngestionTask(
        "games", GamesIngester, supports_season_type=True, supports_week=True
    ),
    "rosters": IngestionTask("rosters", RostersIngester, supports_limit_teams=True),
    "coaches": IngestionTask("coaches", CoachesIngester, supports_limit_teams=True),
    "betting_lines": IngestionTask(
        "betting_lines",
        BettingLinesIngester,
        supports_season_type=True,
        supports_week=True,
        supports_limit_games=True,
    ),
    "plays": IngestionTask(
        "plays",
        PlaysIngester,
        supports_season_type=True,
        supports_week=True,
        week_kwarg="only_week",
        supports_limit_games=True,
    ),
    "game_stats_raw": IngestionTask(
        "game_stats_raw",
        GameStatsIngester,
        supports_season_type=True,
        supports_limit_games=True,
    ),
}

DEFAULT_INGESTION_ORDER: list[str] = [
    "teams",
    "venues",
    "games",
    "rosters",
    "coaches",
    "betting_lines",
    "plays",
    "game_stats_raw",
]


def resolve_ingestion_task(key: str) -> IngestionTask:
    try:
        return INGESTION_REGISTRY[key.lower()]
    except KeyError as exc:
        raise ValueError(f"Unknown ingestion entity '{key}'") from exc


def _validate_keys(keys: Iterable[str]) -> set[str]:
    unknown = {k.lower() for k in keys if k.lower() not in INGESTION_REGISTRY}
    if unknown:
        raise ValueError(f"Unknown ingestion entities: {', '.join(sorted(unknown))}")
    return {k.lower() for k in keys}


def plan_ingestion_sequence(
    only: Sequence[str] | None, skip: Sequence[str] | None
) -> list[IngestionTask]:
    """Return the ordered list of ingestion tasks to execute."""
    skip_set = _validate_keys(skip or [])

    if only:
        only_validated = _validate_keys(only)
        planned_keys = [
            key.lower()
            for key in only
            if key.lower() in only_validated and key.lower() not in skip_set
        ]
    else:
        planned_keys = [key for key in DEFAULT_INGESTION_ORDER if key not in skip_set]

    # Ensure skip entries existed; the validation step above already raised if not.
    return [resolve_ingestion_task(key) for key in planned_keys]


def build_ingest_kwargs(
    task: IngestionTask,
    *,
    year: int,
    data_root: str,
    season_type: str,
    week: int | None,
    limit_games: int | None,
    limit_teams: int | None,
    storage: LocalStorage | None = None,
) -> dict:
    """Construct keyword arguments for an ingestion task."""
    kwargs: dict[str, object] = {"year": year, "data_root": data_root}
    if storage is not None:
        kwargs["storage"] = storage
    if task.supports_season_type:
        kwargs["season_type"] = season_type
    if task.supports_week and week is not None:
        kwargs[task.week_kwarg] = week
    if task.supports_limit_games and limit_games is not None:
        kwargs["limit_games"] = limit_games
    if task.supports_limit_teams and limit_teams is not None:
        kwargs["limit_teams"] = limit_teams
    return kwargs


def run_ingester(task: IngestionTask, **kwargs) -> None:
    """Instantiate and execute a single ingestion task."""
    ingester = task.cls(**kwargs)
    ingester.run()


app = typer.Typer(help="CFB Model CLI for data ingestion and processing.")
app.add_typer(analysis_cli.app, name="analysis")
app.add_typer(training_cli.app, name="training")


@app.command()
def ingest(
    entity: Annotated[
        str,
        typer.Argument(help="Entity type to ingest", case_sensitive=False),
    ],
    data_root: Annotated[
        str,
        typer.Option(
            help="Absolute path to the root directory for data storage.",
            default_factory=get_data_root,
        ),
    ],
    year: Annotated[int, typer.Option(help="Year to ingest data for")] = 2024,
    season_type: Annotated[
        str, typer.Option(help="Season type for games/plays")
    ] = "regular",
    week: Annotated[
        int | None, typer.Option(help="Optional specific week to ingest (games/plays)")
    ] = None,
    limit_games: Annotated[
        int, typer.Option(help="Limit number of games for testing")
    ] = None,
    limit_teams: Annotated[
        int, typer.Option(help="Limit number of teams for testing")
    ] = None,
):
    """Ingest data from the CFBD API."""
    try:
        task = resolve_ingestion_task(entity)
    except ValueError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(code=1)

    kwargs = build_ingest_kwargs(
        task,
        year=year,
        data_root=data_root,
        season_type=season_type,
        week=week,
        limit_games=limit_games,
        limit_teams=limit_teams,
    )
    typer.echo(
        f"Running ingestion for '{task.key}' (year={year}"
        + (f", week={week}" if week is not None else "")
        + ")"
    )
    try:
        run_ingester(task, **kwargs)
    except Exception as exc:  # pragma: no cover - CLI surface
        typer.echo(f"Error during {task.key}: {exc}")
        raise typer.Exit(code=1)


@app.command()
def aggregate(
    command: Annotated[
        str,
        typer.Argument(help="Aggregation command to run", case_sensitive=False),
    ],
    data_root: Annotated[
        str,
        typer.Option(
            help="Absolute path to the root directory for data storage.",
            default_factory=get_data_root,
        ),
    ],
    year: Annotated[int, typer.Option(help="Season year")] = 2024,
    quiet: Annotated[bool, typer.Option(help="Reduce per-game logging")] = False,
):
    """Run data aggregation pipelines."""
    if command == "preagg":
        persist_preaggregations(year=year, data_root=data_root, verbose=not quiet)
    elif command == "byplay":
        persist_byplay_only(year=year, data_root=data_root, verbose=not quiet)
    else:
        print(f"Error: Unknown aggregate command '{command}'")
        raise typer.Exit(code=1)


@app.command()
def ingest_year(
    year: Annotated[int, typer.Argument(help="The year to ingest data for.")],
    data_root: Annotated[
        str,
        typer.Option(
            help="Absolute path to the root directory for data storage.",
            default_factory=get_data_root,
        ),
    ],
    limit_games: Annotated[
        int,
        typer.Option(
            help="Limit number of games for testing (applies to plays, betting_lines, game_stats)"
        ),
    ] = None,
    season_type: Annotated[str, typer.Option(help="Season type to ingest")] = "regular",
    only: Annotated[
        list[str] | None,
        typer.Option(
            "--only",
            help="Restrict ingestion to these entities (may be provided multiple times).",
        ),
    ] = None,
    skip: Annotated[
        list[str] | None,
        typer.Option(
            "--skip",
            help="Skip these entities when running the ingestion pipeline.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Display the resolved ingestion plan and exit without running it.",
        ),
    ] = False,
):
    """Runs the complete data ingestion pipeline for a given year."""
    print(f"--- Starting full data ingestion for year {year} ---")

    storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    print(f"Using data root: {storage.root()}")

    try:
        tasks = plan_ingestion_sequence(only, skip)
    except ValueError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(code=1)

    if not tasks:
        typer.echo("No ingestion tasks selected; nothing to run.")
        return

    typer.echo("Ingestion plan: " + ", ".join(task.key for task in tasks))
    if dry_run:
        typer.echo("Dry run requested; exiting without execution.")
        return

    failures: list[str] = []
    for task in tasks:
        typer.echo(f"\n--> Running {task.key}")
        kwargs = build_ingest_kwargs(
            task,
            year=year,
            data_root=data_root,
            season_type=season_type,
            week=None,
            limit_games=limit_games,
            limit_teams=None,
            storage=storage,
        )
        try:
            run_ingester(task, **kwargs)
            typer.echo(f"✅ Successfully completed {task.cls.__name__}")
        except Exception as e:
            msg = f"❌ Error during {task.cls.__name__}: {e}"
            typer.echo(msg)
            failures.append(msg)

    if failures:
        print(f"--- Completed ingestion for {year} with {len(failures)} failure(s) ---")
        for f in failures:
            print(f)
    else:
        print(f"--- Successfully completed full data ingestion for year {year} ---")


@app.command()
def run_season(
    data_root: Annotated[
        str,
        typer.Option(help="Path to data root directory", default_factory=get_data_root),
    ],
    year: Annotated[int, typer.Option(help="Season year to process")] = 2024,
    start_week: Annotated[int, typer.Option(help="Starting week (inclusive)")] = 5,
    end_week: Annotated[int, typer.Option(help="Ending week (inclusive)")] = 16,
    bankroll: Annotated[
        float,
        typer.Option(help="Current bankroll used for bet sizing and exposure caps"),
    ] = 10000.0,
    spread_threshold: Annotated[
        float, typer.Option(help="Spread edge threshold for betting")
    ] = 3.5,
    total_threshold: Annotated[
        float, typer.Option(help="Total edge threshold for betting")
    ] = 3.5,
):
    """Run model predictions and scoring for a full season using the champion model."""
    from cks_picks_cfb.config.champion import get_champion_model_paths
    from cks_picks_cfb.inference.predict import predict_week
    from cks_picks_cfb.inference.report import generate_report

    weeks_to_run = list(range(start_week, end_week + 1))
    print(f"Running champion model for {len(weeks_to_run)} weeks: {weeks_to_run}")

    champion_paths = get_champion_model_paths()
    spread_model_path = str(champion_paths["spread"])
    # total_model_path = str(champion_paths["total"]) # TODO: Add total support

    for week in weeks_to_run:
        print(f"\n=== Processing Week {week} ===")
        try:
            # 1. Predict
            # For now, we only predict spread. Total needs to be added.
            predictions_path = f"predictions_week_{week}.csv"
            predict_week(
                year=year,
                week=week,
                model_path=spread_model_path,
                output_path=predictions_path,
                data_root=data_root,
                use_subprocess=True,
            )

            # 2. Report
            generate_report(
                predictions_path=predictions_path,
                year=year,
                week=week,
                bankroll=bankroll,
                spread_threshold=spread_threshold,
                total_threshold=total_threshold,
                output_dir=str(REPORTS_DIR / str(year)),
            )

            # Cleanup temp file
            if os.path.exists(predictions_path):
                os.remove(predictions_path)

        except Exception as e:
            print(f"ERROR processing week {week}: {e}")
            continue


if __name__ == "__main__":
    app()
