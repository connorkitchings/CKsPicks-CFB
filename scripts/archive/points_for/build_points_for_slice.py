#!/usr/bin/env python3
"""Build a points-for modeling slice from cached data.

This utility joins raw game scores with opponent-adjusted weekly features
and enforces a minimum number of prior FBS games per team. It is intended
to bootstrap experimentation with the points-for modeling initiative.
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable

DEFAULT_MIN_GAMES = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a training slice for the points-for model."
    )
    parser.add_argument(
        "--season",
        type=int,
        required=True,
        help="Target season (e.g., 2023).",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Root directory for data. Defaults to CFB_DATA_ROOT env or ./data.",
    )
    parser.add_argument(
        "--min-games",
        type=float,
        default=DEFAULT_MIN_GAMES,
        help="Minimum number of prior FBS games for both teams (default: 2).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/prototypes/points_for_training_slice.csv"),
        help="Destination CSV file.",
    )
    parser.add_argument(
        "--adjustment-iteration",
        type=int,
        default=4,
        help=(
            "Opponent-adjustment iteration depth to read from team_week_adj caches "
            "(default: 4). Use -1 to fall back to the legacy layout."
        ),
    )
    return parser.parse_args()


def resolve_data_root(data_root: Path | None) -> Path:
    if data_root is not None:
        return data_root
    env_root = os.getenv("CFB_DATA_ROOT")
    if env_root:
        return Path(env_root)
    return Path.cwd() / "data"


def load_raw_games(raw_root: Path, season: int) -> list[dict[str, str]]:
    games_path = raw_root / "games" / f"year={season}" / "data.csv"
    if not games_path.is_file():
        raise FileNotFoundError(f"Raw games not found: {games_path}")
    with games_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader if row.get("season") == str(season)]


def load_week_features(
    processed_root: Path,
    season: int,
    week: int,
    iteration: int | None,
) -> Dict[str, dict[str, str]]:
    candidate_paths: list[Path] = []
    if iteration is not None:
        candidate_paths.append(
            processed_root
            / "team_week_adj"
            / f"iteration={iteration}"
            / f"year={season}"
            / f"week={week}"
            / "data.csv"
        )
    candidate_paths.append(
        processed_root
        / "team_week_adj"
        / f"year={season}"
        / f"week={week}"
        / "data.csv"
    )

    for features_path in candidate_paths:
        if features_path.is_file():
            with features_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return {row["team"]: row for row in reader if row.get("team")}
    return {}


def determine_feature_columns(feature_map: Dict[str, dict[str, str]]) -> list[str]:
    if not feature_map:
        return []
    sample = next(iter(feature_map.values()))
    columns = [c for c in sample.keys() if c.startswith("adj_")]
    if "games_played" in sample:
        columns.insert(0, "games_played")
    return columns


def build_slice(
    raw_games: Iterable[dict[str, str]],
    processed_root: Path,
    season: int,
    min_games: float,
    iteration: int | None,
) -> tuple[list[dict[str, str]], dict[int, int], list[tuple], list[tuple]]:
    rows: list[dict[str, str]] = []
    kept_weeks: dict[int, int] = defaultdict(int)
    missing_features: list[tuple] = []
    insufficient_history: list[tuple] = []

    cache: dict[int, Dict[str, dict[str, str]]] = {}
    columns_cache: dict[int, list[str]] = {}

    for game in raw_games:
        week_raw = game.get("week")
        if not week_raw:
            continue
        try:
            week = int(float(week_raw))
        except ValueError:
            continue

        if week not in cache:
            feature_map = load_week_features(processed_root, season, week, iteration)
            cache[week] = feature_map
            columns_cache[week] = determine_feature_columns(feature_map)

        feature_map = cache[week]
        if not feature_map:
            continue

        home_team = game.get("home_team")
        away_team = game.get("away_team")
        home_feat = feature_map.get(home_team or "")
        away_feat = feature_map.get(away_team or "")
        if not home_feat or not away_feat:
            missing_features.append((week, game.get("id"), home_team, away_team))
            continue

        try:
            home_gp = float(home_feat.get("games_played", "0") or 0)
            away_gp = float(away_feat.get("games_played", "0") or 0)
        except ValueError:
            missing_features.append((week, game.get("id"), home_team, away_team))
            continue
        if home_gp < min_games or away_gp < min_games:
            insufficient_history.append(
                (week, game.get("id"), home_team, away_team, home_gp, away_gp)
            )
            continue

        columns = columns_cache.get(week, [])
        row = {
            "season": game.get("season"),
            "week": str(week),
            "game_id": game.get("id"),
            "home_team": home_team,
            "away_team": away_team,
            "home_points": game.get("home_points"),
            "away_points": game.get("away_points"),
        }
        for column in columns:
            row[f"home_{column}"] = home_feat.get(column)
            row[f"away_{column}"] = away_feat.get(column)
        rows.append(row)
        kept_weeks[week] += 1

    return rows, kept_weeks, missing_features, insufficient_history


def write_rows(rows: list[dict[str, str]], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with destination.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    data_root = resolve_data_root(args.data_root)
    raw_root = data_root / "raw"
    processed_root = data_root / "processed"
    iteration_value = args.adjustment_iteration
    iteration = (
        None if iteration_value is not None and iteration_value < 0 else iteration_value
    )

    raw_games = load_raw_games(raw_root, args.season)
    rows, kept_weeks, missing, insufficient = build_slice(
        raw_games=raw_games,
        processed_root=processed_root,
        season=args.season,
        min_games=args.min_games,
        iteration=iteration,
    )
    write_rows(rows, args.output)

    print(f"Total raw games: {len(raw_games)}")
    print(f"Rows written: {len(rows)} -> {args.output}")
    print("Weeks retained:", sorted(kept_weeks.items()))
    print(f"Missing features: {len(missing)}")
    if missing:
        for entry in missing[:5]:
            print("  MISSING:", entry)
    print(f"Insufficient history (<{args.min_games} games): {len(insufficient)}")
    if insufficient:
        for entry in insufficient[:5]:
            print("  HISTORY:", entry)


if __name__ == "__main__":
    main()
