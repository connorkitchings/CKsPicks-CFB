"""Deterministic cross-source reconciliation for completed games."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

import pandas as pd


class ReconciliationError(ValueError):
    """Raised when blocking source conflicts would contaminate Gold data."""


@dataclass(frozen=True)
class ReconciliationPolicy:
    version: str = "team_game_reconciliation_v1"
    numeric_tolerances: Mapping[str, float] | None = None

    def tolerances(self) -> dict[str, float]:
        return {
            "yards": 2.0,
            "turnovers": 0.0,
            "plays": 1.0,
            "possessions": 1.0,
            **dict(self.numeric_tolerances or {}),
        }


def _game_id_column(frame: pd.DataFrame) -> str:
    if "game_id" in frame:
        return "game_id"
    if "id" in frame:
        return "id"
    raise ReconciliationError("source is missing game_id")


def reconcile_completed_games(
    schedule: pd.DataFrame,
    team_game: pd.DataFrame,
    team_stats: pd.DataFrame | None = None,
    *,
    policy: ReconciliationPolicy | None = None,
) -> pd.DataFrame:
    """Classify each completed game without silently choosing a conflicting source."""
    policy = policy or ReconciliationPolicy()
    schedule = schedule.copy()
    schedule = schedule.rename(columns={_game_id_column(schedule): "game_id"})
    required = {"season", "game_id", "home_team", "away_team", "completed"}
    if missing := sorted(required - set(schedule.columns)):
        raise ReconciliationError(f"schedule missing columns: {missing}")
    completed = schedule[schedule["completed"].fillna(False).astype(bool)].copy()
    if "status" in completed:
        completed = completed[
            ~completed["status"]
            .fillna("")
            .astype(str)
            .str.casefold()
            .isin({"cancelled", "canceled", "postponed"})
        ]
    team_game = team_game.rename(columns={_game_id_column(team_game): "game_id"}).copy()
    stats = None
    if team_stats is not None and not team_stats.empty:
        stats = team_stats.rename(
            columns={_game_id_column(team_stats): "game_id"}
        ).copy()

    rows: list[dict] = []
    for game in completed.sort_values(["season", "game_id"]).to_dict("records"):
        game_id = game["game_id"]
        aggregate = team_game[team_game["game_id"] == game_id]
        details: dict[str, object] = {
            "policy_version": policy.version,
            "team_game_rows": len(aggregate),
        }
        classification = "exact_match"
        blocking = False
        expected_teams = {game["home_team"], game["away_team"]}
        actual_teams = set(aggregate.get("team", pd.Series(dtype=str)).dropna())
        if len(aggregate) != 2 or actual_teams != expected_teams:
            classification = "blocking_conflict"
            blocking = True
            details["expected_teams"] = sorted(expected_teams)
            details["actual_teams"] = sorted(actual_teams)

        if not blocking and {"home_points", "away_points"}.issubset(game):
            for team, expected in (
                (game["home_team"], game.get("home_points")),
                (game["away_team"], game.get("away_points")),
            ):
                if expected is None:
                    continue
                row = aggregate[aggregate["team"] == team]
                score_column = next(
                    (
                        column
                        for column in ("points", "team_points", "score")
                        if column in row
                    ),
                    None,
                )
                if (
                    score_column
                    and not row.empty
                    and pd.notna(row.iloc[0][score_column])
                ):
                    actual = float(row.iloc[0][score_column])
                    if actual != float(expected):
                        classification = "blocking_conflict"
                        blocking = True
                        details.setdefault("score_conflicts", []).append(
                            {"team": team, "schedule": expected, "aggregate": actual}
                        )

        if not blocking and stats is not None:
            box = stats[stats["game_id"] == game_id]
            details["team_stats_rows"] = len(box)
            if box.empty:
                classification = "incomplete_source"
            elif "team" not in box:
                classification = "incomplete_source"
            elif set(box["team"].dropna()) != expected_teams:
                classification = "incomplete_source"
            elif "team" in box and "team" in aggregate:
                differences = []
                for metric, tolerance in policy.tolerances().items():
                    left = next(
                        (
                            column
                            for column in (metric, f"off_{metric}", f"n_{metric}")
                            if column in aggregate
                        ),
                        None,
                    )
                    right = next(
                        (
                            column
                            for column in (metric, f"team_{metric}")
                            if column in box
                        ),
                        None,
                    )
                    if not left or not right:
                        continue
                    joined = aggregate[["team", left]].merge(
                        box[["team", right]], on="team"
                    )
                    for item in joined.to_dict("records"):
                        if pd.isna(item[left]) or pd.isna(item[right]):
                            continue
                        delta = abs(float(item[left]) - float(item[right]))
                        if delta > tolerance:
                            differences.append(
                                {"team": item["team"], "metric": metric, "delta": delta}
                            )
                if differences:
                    classification = "blocking_conflict"
                    blocking = True
                    details["metric_conflicts"] = differences

        identity = json.dumps(
            {"season": game["season"], "game_id": game_id, "policy": policy.version},
            sort_keys=True,
        )
        rows.append(
            {
                "reconciliation_id": hashlib.sha256(identity.encode()).hexdigest()[:32],
                "season": int(game["season"]),
                "game_id": int(game_id),
                "classification": classification,
                "blocking": blocking,
                "details": json.dumps(details, sort_keys=True),
                "policy_version": policy.version,
            }
        )
    return pd.DataFrame.from_records(rows)


def require_reconciled(results: pd.DataFrame) -> None:
    blocking = results[results["blocking"].fillna(True).astype(bool)]
    if not blocking.empty:
        game_ids = blocking["game_id"].astype(int).tolist()
        raise ReconciliationError(f"Blocking source conflicts for games: {game_ids}")
