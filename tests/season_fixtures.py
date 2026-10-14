"""A small deterministic 2026 season run through the real preparation path.

Four FBS teams play weeks 0-3 (two games a week). Weeks 0-1 are completed with
13 plays and 4 drives per game carrying every column the measurement, team-stats
and possession builders read; Week 2 is the live (active) week and Week 3 is a
later scheduled week. Measurements are NOT supplied, so ``build_measurements``
derives the real observation columns from the plays. ``App State`` is a provider
name whose canonical name differs (``Appalachian State``), so name mapping is
exercised.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.forecast.live import DEVELOPMENT_SEASONS
from cks_picks_cfb.preseason_features import canonical_team
from cks_picks_cfb.season import projection_common as pc
from cks_picks_cfb.season.inputs import load_inputs
from cks_picks_cfb.season.manifest import canonical, sha
from cks_picks_cfb.season.runner import prepare

TEAMS = ("App State", "Bravo", "Charlie", "Delta")
#: week -> [(game_id, home, away, kickoff)]
SCHEDULE = {
    0: [(1, "App State", "Bravo", "12:00"), (2, "Charlie", "Delta", "15:00")],
    1: [(3, "App State", "Charlie", "12:00"), (4, "Bravo", "Delta", "15:00")],
    2: [(5, "App State", "Delta", "12:00"), (6, "Bravo", "Charlie", "15:00")],
    3: [(7, "Delta", "App State", "12:00"), (8, "Charlie", "Bravo", "15:00")],
}
GAME_DAYS = {0: "2026-09-05", 1: "2026-09-12", 2: "2026-09-19", 3: "2026-09-26"}
THROUGH_WEEK, NEXT_WEEK = 1, 2
AS_OF = "2026-09-13T12:00:00Z"
CAPTURED_AT = "2026-09-13T12:00:00Z"
PRE_WEEK_CUTOFFS = {"0": "2026-09-05T10:00:00Z", "1": "2026-09-12T10:00:00Z"}
CODE_SHA = "c" * 40
HOME_POINTS, AWAY_POINTS = 10, 7

# (drive offense side, [(play_type, down, distance, yards, ppa, success, st, points)])
DRIVES = (
    (
        "home",
        [
            ("Rush", 1, 10, 5, 0.2, 1, 0, 0),
            ("Pass Reception", 2, 5, 25, 1.1, 1, 0, 0),
            ("Rushing Touchdown", 1, 10, 10, 1.5, 1, 0, 7),
        ],
    ),
    (
        "away",
        [
            ("Rush", 1, 10, 2, -0.3, 0, 0, 0),
            ("Pass Incompletion", 2, 8, 0, -0.6, 0, 0, 0),
            ("Pass Reception", 3, 8, 4, -0.4, 0, 0, 0),
            ("Punt", 4, 4, 0, 0.0, 0, 1, 0),
        ],
    ),
    (
        "home",
        [
            ("Rush", 1, 10, 3, -0.1, 0, 0, 0),
            ("Pass Reception", 2, 7, 12, 0.8, 1, 0, 0),
            ("Field Goal Good", 4, 3, 0, 0.0, 0, 1, 3),
        ],
    ),
    (
        "away",
        [
            ("Pass Reception", 1, 10, 30, 1.6, 1, 0, 0),
            ("Rush", 1, 10, 6, 0.3, 1, 0, 0),
            ("Passing Touchdown", 2, 4, 14, 1.9, 1, 0, 7),
        ],
    ),
)
#: drive -> start yards to goal and whether it reached a scoring opportunity
DRIVE_STARTS = ((75, 1), (80, 0), (70, 1), (65, 1))


class MemoryReader:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def add(self, name: str, value: Any) -> dict:
        if isinstance(value, pd.DataFrame):
            output = io.BytesIO()
            value.to_parquet(output, index=False)
            raw = output.getvalue()
        else:
            raw = canonical(value)
        self.objects[name] = raw
        return {"uri": name, "sha256": sha(raw)}

    def read_bytes(self, path: str) -> bytes:
        return self.objects[path]


def _games() -> list[tuple[int, int, str, str, str]]:
    return [
        (week, game_id, home, away, f"{GAME_DAYS[week]}T{time}:00Z")
        for week, games in SCHEDULE.items()
        for game_id, home, away, time in games
    ]


def _plays_and_drives() -> tuple[pd.DataFrame, pd.DataFrame]:
    plays, drives = [], []
    for week, game_id, home, away, _ in _games():
        if week > THROUGH_WEEK:
            continue
        score = {home: 0, away: 0}
        bonus = game_id / 10  # distinct values per game
        for drive_number, ((side, rows), (start, opportunity)) in enumerate(
            zip(DRIVES, DRIVE_STARTS, strict=True), start=1
        ):
            offense, defense = (home, away) if side == "home" else (away, home)
            to_goal = start
            drive_points = 0
            for play_number, (
                kind,
                down,
                distance,
                yards,
                ppa,
                ok,
                st,
                pts,
            ) in enumerate(rows, start=1):
                gained = yards + (game_id if yards else 0)
                score[offense] += pts
                drive_points += pts
                plays.append(
                    {
                        "season": 2026,
                        "week": week,
                        "game_id": game_id,
                        "drive_number": drive_number,
                        "play_number": play_number,
                        "offense": offense,
                        "defense": defense,
                        "quarter": drive_number // 3 + 1,
                        "st": st,
                        "penalty": 0,
                        "twopoint": 0,
                        "play_type": kind,
                        "garbage": 0,
                        "ppa": None if st else round(ppa + bonus * (ppa != 0), 4),
                        "success": ok,
                        "yards_gained": gained,
                        "turnover": 0,
                        "down": down,
                        "yards_to_first": distance,
                        "yards_to_goal": to_goal,
                        "offense_score": score[offense],
                        "defense_score": score[defense],
                    }
                )
                to_goal = max(1, to_goal - gained)
            drives.append(
                {
                    "season": 2026,
                    "week": week,
                    "game_id": game_id,
                    "drive_number": drive_number,
                    "offense": offense,
                    "defense": defense,
                    "start_yards_to_goal": start,
                    "had_scoring_opportunity": opportunity,
                    "points": drive_points,
                    "points_on_opps": drive_points if opportunity else 0,
                }
            )
    return pd.DataFrame(plays), pd.DataFrame(drives)


def raw_tables() -> dict[str, pd.DataFrame]:
    """Every revision/model table, before it is pinned; tests may edit copies."""
    games = _games()
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": week,
                "game_id": game_id,
                "kickoff_utc": kickoff,
                "home_team": home,
                "away_team": away,
            }
            for week, game_id, home, away, kickoff in games
        ]
    )
    completed = [g for g in games if g[0] <= THROUGH_WEEK]
    finals = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": game_id,
                "home_points": HOME_POINTS,
                "away_points": AWAY_POINTS,
            }
            for _, game_id, *_ in completed
        ]
    )
    plays, drives = _plays_and_drives()
    venue_games = pd.DataFrame(
        [
            {
                "season": 2026,
                "id": game_id,
                "venue_id": 100 + game_id,
                "venue": f"Stadium {game_id}",
                "neutral_site": game_id == 6,
            }
            for _, game_id, *_ in games
        ]
    )
    venues = pd.DataFrame(
        [
            {
                "id": 100 + game_id,
                "name": f"Stadium {game_id}",
                "city": f"City {game_id}",
                "state": "NC",
                "country_code": "US",
                "timezone": "America/New_York",
            }
            for _, game_id, *_ in games
        ]
    )
    teams = pd.DataFrame(
        [{"team": t, "classification": "fbs"} for t in TEAMS]
        + [{"team": "Echo Tech", "classification": "fcs"}]
    )
    historical = pd.DataFrame(
        [
            {
                "season": s,
                "week": 0,
                "game_id": s,
                "kickoff_utc": f"{s}-09-01T12:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "forecast_eligible": True,
                "schedule_completed": True,
                "outcome_valid": True,
                "measurement_usable": True,
            }
            for s in DEVELOPMENT_SEASONS
        ]
    )
    old_events = pd.DataFrame(
        [
            {
                "season": s,
                "game_id": s,
                "team": "A",
                "period_class": "regulation",
                "scoring_category": "regulation_offense",
                "score_increment": 0.0,
            }
            for s in DEVELOPMENT_SEASONS
        ]
    )
    priors = pd.DataFrame(
        [
            {
                "season": 2026,
                "team": canonical_team(t),
                "unit_role": r,
                "prior_mean": 0.1 * i,
                "prior_variance": 1.0,
                "fallback_reason": "no_prior_season" if t == "Delta" else None,
            }
            for i, t in enumerate(TEAMS)
            for r in ("offense", "defense")
        ]
    )
    terminal = pd.DataFrame(
        [
            {
                "season": 2025,
                "team": canonical_team(t),
                "unit_role": r,
                "measurement_id": "ppp",
                "adjusted_value": 0.8 + i * 0.4,
                "primary_exposure": 8.0,
            }
            for i, t in enumerate(TEAMS)
            for r in ("offense", "defense")
        ]
    )
    return {
        "schedule": schedule,
        "finals": finals,
        "byplay": plays,
        "drives": drives,
        "reconciliation": pd.DataFrame({"game_id": finals.game_id, "blocking": False}),
        "venue_games": venue_games,
        "venues": venues,
        "teams": teams,
        "priors": priors,
        "terminal": terminal,
        "historical_population": historical,
        "historical_events": old_events,
    }


MODEL_INPUTS = ("priors", "terminal", "historical_population", "historical_events")


def build_season(
    output: Path,
    edit: Callable[[dict[str, pd.DataFrame]], None] | None = None,
) -> dict[str, Any]:
    """Prepare the season and return the ``build_football`` keyword arguments.

    ``edit`` may change (or delete) any raw table before it is pinned.
    """
    tables = raw_tables()
    if edit is not None:
        edit(tables)
    reader = MemoryReader()
    bundle = json.loads(
        (
            Path(__file__).resolve().parents[1] / "conf/rebuild/bundle_b2_w5_v1.json"
        ).read_bytes()
    )
    model = {
        "schema_version": "season_model_v1",
        "model_id": "v5-intended-update-2026-v1",
        "design": "ppp__rho_0_60__exposure",
        "development_seasons": list(DEVELOPMENT_SEASONS),
        "inputs": {"bridge": reader.add("bridge", bundle)}
        | {name: reader.add(name, tables[name]) for name in MODEL_INPUTS},
    }
    revision = {
        "schema_version": "season_revision_v1",
        "season": 2026,
        "revision_id": "fixture-r1",
        "captured_at": CAPTURED_AT,
        "pre_week_cutoffs": dict(PRE_WEEK_CUTOFFS),
        "inputs": {
            name: reader.add(name, table)
            for name, table in tables.items()
            if name not in MODEL_INPUTS
        },
    }
    manifest = prepare(
        model_raw=canonical(model),
        revision_raw=canonical(revision),
        reader=reader,
        through_week=THROUGH_WEEK,
        next_week=NEXT_WEEK,
        as_of=AS_OF,
        output=output,
        code_sha=CODE_SHA,
    )
    inputs = load_inputs(
        reader,
        model,
        revision,
        THROUGH_WEEK,
        cache_dir=output / "measurement-cache",
        code_sha=CODE_SHA,
    )
    refs = manifest["output_refs"]
    frames = {
        name: pd.read_parquet(refs[name]["uri"])
        for name in refs
        if refs[name]["uri"].endswith(".parquet")
    }
    output_shas = {name: ref["sha256"] for name, ref in refs.items()}
    identity = manifest["identity"]
    return {
        "frames": frames,
        "inputs": inputs,
        "revision": revision,
        "identity": {**identity, "run_id": manifest["release_id"]},
        "ratings_id": pc.rating_identity(
            model_sha=identity["model_manifest_sha256"],
            revision_sha=identity["revision_manifest_sha256"],
            workflow=identity["workflow_version"],
            output_shas=output_shas,
        ),
        "measurement_id": pc.measurement_identity(
            revision_sha=identity["revision_manifest_sha256"],
            output_shas=output_shas,
        ),
    }
