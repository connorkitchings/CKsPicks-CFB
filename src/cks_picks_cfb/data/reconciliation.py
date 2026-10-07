"""Deterministic cross-source reconciliation for completed games."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Collection, Mapping

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


def stream_points_by_team_game(byplay: pd.DataFrame) -> pd.DataFrame:
    """Each team's final score as the play stream reports it (its highest running score).

    This is the stream-derived team score the reconciliation compares with the certified
    final. A stream that dips and recovers still ends at the right score; one that stops
    short, or never reaches the final, shows up as a mismatch.
    """
    offense = byplay[["game_id", "offense", "offense_score"]].set_axis(
        ["game_id", "team", "score"], axis=1
    )
    defense = byplay[["game_id", "defense", "defense_score"]].set_axis(
        ["game_id", "team", "score"], axis=1
    )
    long = pd.concat([offense, defense], ignore_index=True)
    long["score"] = pd.to_numeric(long["score"], errors="coerce")
    out = long.groupby(["game_id", "team"], as_index=False)["score"].max()
    return out.rename(columns={"score": "stream_points"})


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
    declared_incomplete_game_ids: Collection[int] | None = None,
) -> pd.DataFrame:
    """Classify each completed game without silently choosing a conflicting source."""
    policy = policy or ReconciliationPolicy()
    declared_incomplete_game_ids = {
        int(game_id) for game_id in (declared_incomplete_game_ids or ())
    }
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
        declared_missing_play_capture = (
            aggregate.empty and int(game_id) in declared_incomplete_game_ids
        )
        if not aggregate.empty and (
            len(aggregate) != 2 or actual_teams != expected_teams
        ):
            classification = "blocking_conflict"
            blocking = True
            details["expected_teams"] = sorted(expected_teams)
            details["actual_teams"] = sorted(actual_teams)
        elif aggregate.empty:
            if declared_missing_play_capture:
                classification = "incomplete_source"
                details["declared_missing_play_capture"] = True
            else:
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

        # Stream-derived team scores (``stream_points``) are compared with the certified
        # final and recorded in ``details``. A mismatch is recorded, never blocking: score
        # streams with gaps are known (issue 1) and are handled per allocation, not here.
        if (
            not blocking
            and "stream_points" in aggregate.columns
            and {"home_points", "away_points"}.issubset(game)
        ):
            compared, mismatches = 0, []
            for team, expected in (
                (game["home_team"], game.get("home_points")),
                (game["away_team"], game.get("away_points")),
            ):
                row = aggregate[aggregate["team"] == team]
                if (
                    expected is None
                    or pd.isna(expected)
                    or row.empty
                    or pd.isna(row.iloc[0]["stream_points"])
                ):
                    continue
                compared += 1
                actual = float(row.iloc[0]["stream_points"])
                if actual != float(expected):
                    mismatches.append(
                        {"team": team, "schedule": float(expected), "stream": actual}
                    )
            details["stream_scores_compared"] = compared
            if mismatches:
                details["score_stream_mismatches"] = mismatches

        if not blocking and stats is not None:
            box = stats[stats["game_id"] == game_id]
            details["team_stats_rows"] = len(box)
            if box.empty:
                classification = "incomplete_source"
            elif "team" not in box:
                if declared_missing_play_capture:
                    classification = "blocking_conflict"
                    blocking = True
                    details["team_stats_error"] = "missing_team_column"
                else:
                    classification = "incomplete_source"
            elif set(box["team"].dropna()) != expected_teams:
                if declared_missing_play_capture:
                    classification = "blocking_conflict"
                    blocking = True
                    details["team_stats_expected_teams"] = sorted(expected_teams)
                    details["team_stats_actual_teams"] = sorted(
                        set(box["team"].dropna())
                    )
                else:
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


AVAILABILITY_HOURS = 6


def exclude_games_after_cutoff(
    schedule: pd.DataFrame,
    cutoff: pd.Timestamp | str,
    *,
    kickoff_column: str = "start_date",
    availability_hours: int = AVAILABILITY_HOURS,
) -> tuple[pd.DataFrame, list[int]]:
    """Mark games not yet available at ``cutoff`` as not completed; never drop rows.

    A game is available only when its kickoff plus the availability buffer is at or before
    the cutoff (the same rule the rating states use). A provider that already reports a
    later game as completed must not make the reconciliation demand plays for it: those
    games are outside the point-in-time dataset. Games without a parseable kickoff are left
    untouched. Returns the adjusted schedule and the excluded game ids.
    """
    limit = pd.Timestamp(cutoff)
    if limit.tzinfo is None:
        limit = limit.tz_localize("UTC")
    result = schedule.copy()
    if kickoff_column not in result.columns or "completed" not in result.columns:
        return result, []
    kickoff = pd.to_datetime(result[kickoff_column], utc=True, errors="coerce")
    late = (
        result["completed"].fillna(False).astype(bool)
        & kickoff.notna()
        & (kickoff + pd.Timedelta(hours=availability_hours) > limit)
    )
    id_column = _game_id_column(result)
    excluded = sorted(int(game_id) for game_id in result.loc[late, id_column])
    result["completed"] = result["completed"].fillna(False).astype(bool) & ~late
    return result, excluded


def require_reconciled(results: pd.DataFrame) -> None:
    blocking = results[results["blocking"].fillna(True).astype(bool)]
    if not blocking.empty:
        game_ids = blocking["game_id"].astype(int).tolist()
        raise ReconciliationError(f"Blocking source conflicts for games: {game_ids}")
