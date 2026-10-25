#!/usr/bin/env python3
"""Stop gate: completed-week schedule and finals must not change during a rollover.

The incremental close/open path refreshes the season schedule and rebuilds
``games``/``game_outcomes`` Silver from the fresh capture. Before anything
derives from them, this gate compares every completed week below the just-
closed week against the previous certified revision. Any difference stops the
run and names the affected games; the affected history then needs an explicitly
approved repair, never a silent rewrite.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.silver import SILVER_CONTRACTS
from cks_picks_cfb.data.storage import get_storage


def _ref_from_file(path: str) -> DatasetRef:
    """A controller ref JSON file holding a full DatasetRef."""
    with open(path) as handle:
        return DatasetRef(**json.load(handle))


def _ref_from_input(dataset: str, entry: dict[str, Any]) -> DatasetRef:
    """A revision-manifest input (``uri`` plus ``sha256``)."""
    version = entry["uri"].split("version=", 1)[1].split("/", 1)[0]
    return DatasetRef(
        dataset=dataset,
        version_id=version,
        schema_version=SILVER_CONTRACTS[dataset].schema_version,
        content_sha=entry["sha256"],
        uri=entry["uri"],
    )


def _completed_week_ids(games: pd.DataFrame, through_week: int) -> set[Any]:
    return set(games.loc[games["week"] <= through_week, "game_id"])


def _value_differences(
    label: str,
    new: pd.DataFrame,
    previous: pd.DataFrame,
    game_ids: list[Any],
) -> list[str]:
    problems: list[str] = []
    new_index = new.set_index("game_id")
    previous_index = previous.set_index("game_id")
    shared_columns = [
        column for column in new_index.columns if column in previous_index.columns
    ]
    new_frame = new_index.loc[game_ids, shared_columns].astype(str)
    previous_frame = previous_index.loc[game_ids, shared_columns].astype(str)
    differing = new_frame.ne(previous_frame)
    for game_id in differing.index[differing.any(axis=1)]:
        columns = sorted(differing.columns[differing.loc[game_id]])
        problems.append(f"{label}: game {game_id} changed columns {columns}")
    return problems


def compare_completed_weeks(
    new_games: pd.DataFrame,
    previous_games: pd.DataFrame,
    new_outcomes: pd.DataFrame,
    previous_outcomes: pd.DataFrame,
    *,
    through_week: int,
) -> list[str]:
    """Return one message per completed-week row that differs, in game order."""
    problems: list[str] = []
    new_ids = _completed_week_ids(new_games, through_week)
    previous_ids = _completed_week_ids(previous_games, through_week)
    for game_id in sorted(previous_ids - new_ids, key=str):
        problems.append(
            f"games: game {game_id} is missing from the new completed-week scope"
        )
    for game_id in sorted(new_ids - previous_ids, key=str):
        problems.append(f"games: game {game_id} is new in the completed-week scope")
    shared_ids = sorted(new_ids & previous_ids, key=str)
    problems.extend(
        _value_differences(
            "games",
            new_games[new_games["week"] <= through_week],
            previous_games[previous_games["week"] <= through_week],
            shared_ids,
        )
    )
    outcomes = new_outcomes[new_outcomes["game_id"].isin(new_ids)]
    previous = previous_outcomes[previous_outcomes["game_id"].isin(previous_ids)]
    outcome_ids = sorted(set(outcomes["game_id"]) & set(previous["game_id"]), key=str)
    for game_id in sorted(set(previous["game_id"]) - set(outcomes["game_id"]), key=str):
        problems.append(f"game_outcomes: game {game_id} lost its certified finals row")
    problems.extend(
        _value_differences("game_outcomes", outcomes, previous, outcome_ids)
    )
    return problems


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-games-ref", required=True)
    parser.add_argument("--new-outcomes-ref", required=True)
    parser.add_argument("--previous-games", required=True)
    parser.add_argument("--previous-outcomes", required=True)
    parser.add_argument("--through-week", type=int, required=True)
    parser.add_argument("--environment", choices=("preview", "production"))
    args = parser.parse_args()
    storage = get_storage(environment=args.environment)
    problems = compare_completed_weeks(
        read_dataset(storage, _ref_from_file(args.new_games_ref)),
        read_dataset(
            storage, _ref_from_input("games", json.loads(args.previous_games))
        ),
        read_dataset(storage, _ref_from_file(args.new_outcomes_ref)),
        read_dataset(
            storage,
            _ref_from_input("game_outcomes", json.loads(args.previous_outcomes)),
        ),
        through_week=args.through_week,
    )
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(
            f"Completed-week history changed in {len(problems)} place(s); "
            "stop the rollover and route the affected games to an approved repair.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print(
        f"Completed weeks 0..{args.through_week} match the previous certified revision."
    )


if __name__ == "__main__":
    main()
