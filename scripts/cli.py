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
import subprocess

import pandas as pd
import typer
from typing_extensions import Annotated

from src.config import (
    get_data_root,
    REPORTS_DIR,
    PREDICTIONS_SUBDIR,
    SCORED_SUBDIR,
)
from src.features.persist import (
    persist_preaggregations,
    persist_byplay_only,
)
from src.data.betting_lines import BettingLinesIngester
from src.data.coaches import CoachesIngester
from src.data.games import GamesIngester
from src.data.game_stats import GameStatsIngester
from src.data.plays import PlaysIngester
from src.data.rosters import RostersIngester
from src.data.teams import TeamsIngester
from src.data.venues import VenuesIngester
from src.utils.local_storage import LocalStorage

app = typer.Typer(help="CFB Model CLI for data ingestion and processing.")


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
    if entity in ["games"] and week is not None:
        kwargs["week"] = week
    if entity in ["plays"] and week is not None:
        kwargs["only_week"] = week
    if entity in ["betting_lines", "plays", "game_stats_raw"]:
        kwargs["limit_games"] = limit_games
    if entity in ["rosters", "coaches"]:
        kwargs["limit_teams"] = limit_teams

    ingester = ingester_class(**kwargs)
    ingester.run()


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
):
    """Runs the complete data ingestion pipeline for a given year."""
    print(f"--- Starting full data ingestion for year {year} ---")

    storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    print(f"Using data root: {storage.root()}")

    ingestion_sequence = [
        (TeamsIngester, {{}}),
        (VenuesIngester, {{}}),
        (GamesIngester, {{"season_type": season_type}}),
        (RostersIngester, {{}}),
        (CoachesIngester, {{}}),
        (
            BettingLinesIngester,
            {{"season_type": season_type, "limit_games": limit_games}},
        ),
        (PlaysIngester, {{"season_type": season_type, "limit_games": limit_games}}),
        (GameStatsIngester, {{"limit_games": limit_games, "season_type": season_type}}),
    ]

    failures: list[str] = []
    for ingester_class, kwargs in ingestion_sequence:
        try:
            ingester = ingester_class(year=year, storage=storage, **kwargs)
            if limit_games is not None and hasattr(ingester, "limit_games"):
                setattr(ingester, "limit_games", limit_games)
            ingester.run()
            print(f"✅ Successfully completed {ingester_class.__name__}")
        except Exception as e:
            msg = f"❌ Error during {ingester_class.__name__}: {e}"
            print(msg)
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
    model_dir: Annotated[
        str, typer.Option(help="Path to model directory")
    ] = "./models/ridge_baseline",
    report_dir: Annotated[
        str, typer.Option(help="Path to reports output directory")
    ] = str(REPORTS_DIR),
    start_week: Annotated[int, typer.Option(help="Starting week (inclusive)")] = 5,
    end_week: Annotated[int, typer.Option(help="Ending week (inclusive)")] = 16,
    spread_threshold: Annotated[
        float, typer.Option(help="Spread edge threshold for betting")
    ] = 6.0,
    total_threshold: Annotated[
        float, typer.Option(help="Total edge threshold for betting")
    ] = 6.0,
    spread_std_dev_threshold: Annotated[
        float,
        typer.Option(help="Standard deviation threshold for spread bets"),
    ] = 2.0,
    total_std_dev_threshold: Annotated[
        float, typer.Option(help="Standard deviation threshold for total bets")
    ] = None,
):
    """Run model predictions and scoring for a full season."""
    weeks_to_run = list(range(start_week, end_week + 1))
    print(f"Running model for {len(weeks_to_run)} weeks: {weeks_to_run}")

    all_results = []
    bet_summary = []

    for week in weeks_to_run:
        print(f"\n=== Processing Week {week} ===")
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = "./src"
            cmd = [
                "python3",
                "-m",
                "src.scripts.generate_weekly_bets_clean",
                "--year",
                str(year),
                "--week",
                str(week),
                "--data-root",
                data_root,
                "--model-dir",
                model_dir,
                "--output-dir",
                report_dir,
                "--spread-threshold",
                str(spread_threshold),
                "--total-threshold",
                str(total_threshold),
            ]
            if spread_std_dev_threshold is not None:
                cmd.extend([
                    "--spread-std-dev-threshold",
                    str(spread_std_dev_threshold),
                ])
            if total_std_dev_threshold is not None:
                cmd.extend(["--total-std-dev-threshold", str(total_std_dev_threshold)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
            )
            if result.returncode != 0:
                print(f"ERROR generating week {week}: {result.stderr}")
                continue
            print(f"Generated predictions for week {week}")
        except Exception as e:
            print(f"ERROR running predictions for week {week}: {e}")
            continue

        try:
            result = subprocess.run(
                [
                    "python3",
                    "scripts/score_weekly_picks.py",
                    "--year",
                    str(year),
                    "--week",
                    str(week),
                    "--data-root",
                    data_root,
                    "--report-dir",
                    report_dir,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print(f"ERROR scoring week {week}: {result.stderr}")
                continue
            print(f"Scored predictions for week {week}")
        except Exception as e:
            print(f"ERROR scoring week {week}: {e}")
            continue

        scored_path = os.path.join(
            report_dir, str(year), SCORED_SUBDIR, f"CFB_week{week}_bets_scored.csv"
        )
        if not os.path.exists(scored_path):
            legacy_scored = os.path.join(
                report_dir, str(year), f"CFB_week{week}_bets_scored.csv"
            )
            if os.path.exists(legacy_scored):
                scored_path = legacy_scored
        if os.path.exists(scored_path):
            try:
                scored_df = pd.read_csv(scored_path)
                wins = 0
                total = 0
                hit_rate = None

                # Schema variant 1: legacy internal columns
                if {"bet_spread", "pick_win"}.issubset(scored_df.columns):
                    placed = scored_df[
                        scored_df["bet_spread"]
                        .astype(str)
                        .str.lower()
                        .isin(["home", "away"])
                    ]
                    decided = placed[placed["pick_win"].isin([0, 1])]
                    total = len(decided)
                    if total > 0:
                        wins = int(decided["pick_win"].sum())
                        hit_rate = wins / total

                # Schema variant 2: report columns
                elif {"Spread Bet", "Spread Bet Result"}.issubset(scored_df.columns):
                    placed = scored_df[
                        scored_df["Spread Bet"]
                        .astype(str)
                        .str.lower()
                        .isin(["home", "away"])
                    ]
                    decided = placed[placed["Spread Bet Result"].isin(["Win", "Loss"])]
                    total = len(decided)
                    if total > 0:
                        wins = int((decided["Spread Bet Result"] == "Win").sum())
                        hit_rate = wins / total

                else:
                    print(
                        f"Week {week}: Unknown scored schema; columns: {list(scored_df.columns)[:8]}..."
                    )

                if total > 0:
                    print(f"Week {week}: {wins}/{total} = {hit_rate:.3f}")
                    bet_summary.append(
                        {
                            "week": week,
                            "wins": wins,
                            "total_bets": total,
                            "hit_rate": hit_rate,
                        }
                    )
                else:
                    print(f"Week {week}: No bets generated")
                    bet_summary.append(
                        {"week": week, "wins": 0, "total_bets": 0, "hit_rate": None}
                    )

                all_results.append(scored_df)
            except Exception as e:
                print(f"ERROR analyzing week {week}: {e}")
        else:
            print(f"ERROR: Scored file not found for week {week}")

    print("\n" + "=" * 60)
    print("SEASON SUMMARY")
    print("=" * 60)
    total_wins = sum(s["wins"] for s in bet_summary)
    total_bets = sum(s["total_bets"] for s in bet_summary)
    print("\nWeekly Results:")
    for summary in bet_summary:
        if summary["hit_rate"] is not None:
            print(
                f"Week {summary['week']:2d}: {summary['wins']:2d}/{summary['total_bets']:2d} = {summary['hit_rate']:5.3f}"
            )
        else:
            print(f"Week {summary['week']:2d}: No bets")
    if total_bets > 0:
        overall_hit_rate = total_wins / total_bets
        print(f"\nOVERALL: {total_wins}/{total_bets} = {overall_hit_rate:.3f}")
    else:
        print("\nNo bets generated across all weeks")

    if all_results:
        combined_df = pd.concat(all_results, ignore_index=True)
        combined_dir = os.path.join(report_dir, str(year), SCORED_SUBDIR)
        os.makedirs(combined_dir, exist_ok=True)
        combined_path = os.path.join(
            combined_dir, f"CFB_season_{year}_all_bets_scored.csv"
        )
        combined_df.to_csv(combined_path, index=False)

        print(f"\nCombined results saved to: {combined_path}")


if __name__ == "__main__":
    app()
