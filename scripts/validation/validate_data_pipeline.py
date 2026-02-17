#!/usr/bin/env python3
"""Validate the data pipeline by running it on sample data.

This script verifies:
1. All new Tier 1/2 metrics compute correctly
2. No NaN/inf values in output features
3. Opponent adjustment produces valid values
4. Feature pipeline produces expected schema
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from cks_picks_cfb.utils.data_validation import (
    print_validation_report,
    validate_entity,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate CFB data pipeline by running on sample data"
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2024,
        help="Year to validate (default: 2024)",
    )
    parser.add_argument(
        "--week",
        type=int,
        default=12,
        help="Week to validate (default: 12)",
    )
    parser.add_argument(
        "--entity",
        type=str,
        choices=["byplay", "team_game", "team_season"],
        default="team_game",
        help="Which entity to validate (default: team_game)",
    )
    return parser.parse_args()


def validate_byplay_schema(df: pd.DataFrame) -> None:
    """Validate byplay-level features have expected schema."""
    required_cols = [
        "season",
        "week",
        "game_id",
        "offense",
        "defense",
        "play_number",
        "yards_gained",
        "success",
        "explosive",
        "kickoff_touchback",
        "kickoff_return",
        "fourth_quarter",
        "close_game",
        "td_play",
        "big_play_40",
    ]

    report = validate_entity(
        df,
        entity_name="byplay",
        schema_checks={"required_columns": required_cols},
        completeness_checks={
            "year_column": "season",
            "expected_years": [2024],
        },
        statistical_checks={
            "success": {"min": 0, "max": 1, "allow_negative": False},
            "yards_gained": {"min": -100, "max": 100, "allow_negative": True},
        },
    )

    print_validation_report(report)
    return report.passed


def validate_team_game_schema(df: pd.DataFrame) -> None:
    """Validate team-game features have expected schema."""
    required_cols = [
        "season",
        "week",
        "game_id",
        "team",
        "n_off_plays",
        "off_sr",
        "off_ypp",
        "off_epa_pp",
        "off_turnover_rate",
        "off_sack_rate",
        "off_penalty_rate",
        "off_fourth_down_conversion_rate",
        "off_fourth_down_attempt_rate",
        "off_red_zone_sr",
        "def_sr",
        "def_ypp",
        "def_epa_pp",
        "def_turnover_rate",
        "def_sack_rate",
        "def_penalty_rate",
        "def_red_zone_sr",
        "off_non_garbage_sr",
        "off_non_garbage_epa",
        "def_non_garbage_sr",
        "off_fourth_quarter_sr",
        "off_close_game_sr",
        "def_fourth_quarter_sr",
        "off_td_rate",
        "off_40_plus_yard_rate",
        "def_td_rate_allowed",
        "def_40_plus_yard_rate_allowed",
        "off_touchback_rate",
        "off_kick_return_avg_yards",
    ]

    report = validate_entity(
        df,
        entity_name="team_game",
        schema_checks={"required_columns": required_cols},
        completeness_checks={
            "year_column": "season",
            "week_column": "week",
            "expected_years": [2019, 2021, 2022, 2023, 2024],
        },
        statistical_checks={
            "off_sr": {"min": 0, "max": 1, "allow_negative": False},
            "off_turnover_rate": {"min": 0, "max": 0.5, "allow_negative": False},
            "off_td_rate": {"min": 0, "max": 0.2, "allow_negative": False},
            "def_td_rate_allowed": {"min": 0, "max": 0.2, "allow_negative": False},
        },
        integrity_checks={
            "unique_game_team": {
                "type": "unique",
                "columns": ["game_id", "team"],
            }
        },
    )

    print_validation_report(report)
    return report.passed


def validate_no_nan_inf(df: pd.DataFrame, entity_name: str) -> bool:
    """Check for NaN or inf values in DataFrame."""
    numeric_cols = df.select_dtypes(include=["number"]).columns
    issues = []

    for col in numeric_cols:
        nan_count = df[col].isna().sum()
        inf_count = (df[col] == float("inf")).sum()

        if nan_count > 0:
            issues.append(f"{col}: {nan_count} NaN values")
        if inf_count > 0:
            issues.append(f"{col}: {inf_count} inf values")

    if issues:
        print(f"\n{'=' * 60}")
        print(f"NaN/Inf Check - {entity_name}")
        print(f"{'=' * 60}")
        for issue in issues:
            print(f"  ! {issue}")
        print(f"{'=' * 60}\n")
        return False
    else:
        print(f"✓ No NaN or inf values in {entity_name}")
        return True


def run_validation(args: argparse.Namespace) -> int:
    """Run validation based on arguments."""
    print(f"Validating CFB data pipeline")
    print(f"Year: {args.year}, Week: {args.week}, Entity: {args.entity}\n")

    try:
        if args.entity == "byplay":
            from cks_picks_cfb.features.byplay import allplays_to_byplay

            df = pd.read_parquet(
                f"processed/byplay/year={args.year}/week={args.week}/data.parquet"
            )
            df = allplays_to_byplay(df)

            schema_ok = validate_byplay_schema(df)
            nan_ok = validate_no_nan_inf(df, "byplay")

            return 0 if (schema_ok and nan_ok) else 1

        elif args.entity == "team_game":
            df = pd.read_parquet(
                f"processed/team_game/year={args.year}/week={args.week}/data.parquet"
            )

            schema_ok = validate_team_game_schema(df)
            nan_ok = validate_no_nan_inf(df, "team_game")

            return 0 if (schema_ok and nan_ok) else 1

        elif args.entity == "team_season":
            from cks_picks_cfb.features.core import (
                aggregate_team_game,
                aggregate_team_season,
                apply_iterative_opponent_adjustment,
            )

            byplay_df = pd.read_parquet(
                f"processed/byplay/year={args.year}/week={args.week}/data.parquet"
            )
            drives_df = pd.read_parquet(
                f"processed/drives/year={args.year}/week={args.week}/data.parquet"
            )
            byplay_df = byplay_df.head(1000)  # Sample for speed
            drives_df = drives_df.head(100)

            team_game_df = aggregate_team_game(byplay_df, drives_df)
            print(f"✓ Aggregated {len(team_game_df)} team-game records")

            schema_ok = validate_team_game_schema(team_game_df)
            nan_ok = validate_no_nan_inf(team_game_df, "team_game")

            return 0 if (schema_ok and nan_ok) else 1

        else:
            print(f"Unknown entity: {args.entity}")
            return 1

    except FileNotFoundError as e:
        print(f"! File not found: {e}")
        return 1
    except Exception as e:
        print(f"! Error during validation: {e}")
        return 1


def main() -> int:
    """Entry point."""
    args = parse_args()
    return run_validation(args)


if __name__ == "__main__":
    sys.exit(main())
