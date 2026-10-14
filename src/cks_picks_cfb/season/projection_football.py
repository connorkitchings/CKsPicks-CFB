"""Football-data projection builder (owner: P2).

Builds venue, rating, stat, measurement and publication tables of the Step 2
payload, following the authoritative spec in
:mod:`cks_picks_cfb.season.projection_common`. Every value is computed from the
prepared frames, the season inputs and the revision; nothing reads serving state.

Team names: rating tables (``v5_rating_snapshots``, ``team_rating_components.
rating_team``) use canonical names; Silver-derived tables (``team_season_stats``)
and the matchup tables use provider (game) names, as the legacy publishers did.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from cks_picks_cfb.data import matchup_data as md
from cks_picks_cfb.data.game_venues import build_game_venue_rows, require_venue_cities
from cks_picks_cfb.data.team_stats import build_team_season_stats
from cks_picks_cfb.preseason_features import TEAM_LOGO_MAP
from cks_picks_cfb.ratings.possession_intended_update import CANDIDATE_ID
from cks_picks_cfb.season.manifest import utc
from cks_picks_cfb.season.projection_common import (
    canonical_bytes,
    clean_rows,
    sha256_hex,
)

FOOTBALL_KEYS = (
    "game_venues",
    "v5_rating_snapshots",
    "team_season_stats",
    "matchup_data_publications",
    "team_game_measurements",
    "team_possession_stats",
    "team_possession_adjusted",
    "team_rating_components",
)

SEASON = 2026
LINEAGE = "intended_update"

VENUE_COLUMNS = (
    "game_id",
    "venue_id",
    "venue_name",
    "city",
    "state",
    "country_code",
    "timezone",
    "neutral_site",
    "source",
    "updated_at",
)
SNAPSHOT_COLUMNS = (
    "snapshot_id",
    "source_run_id",
    "source_manifest_sha256",
    "team",
    "season",
    "week",
    "game_id",
    "snapshot_class",
    "cutoff_utc",
    "offense_rating",
    "offense_variance",
    "defense_rating",
    "defense_variance",
    "overall_rating",
    "overall_variance",
    "fallback_reason",
    "created_at",
)
TEAM_STATS_COLUMNS = (
    "season",
    "as_of_week",
    "team",
    "role",
    "metric",
    "value",
    "n",
    "games",
    "rank",
    "cohort_size",
    "source_versions",
    "updated_at",
)
PUBLICATION_COLUMNS = (
    "publication_id",
    "season",
    "lineage",
    "rating_manifest_sha256",
    "rating_manifest_uri",
    "measurement_manifest_sha256",
    "measurement_manifest_uri",
    "observations_records_sha",
    "as_of_weeks",
    "rating_scale",
    "row_counts",
    "payload_sha256",
    "code_sha",
    "published_at",
)
#: Matchup tables: the legacy builder columns plus the audit timestamp.
MATCHUP_COLUMNS = {
    "team_game_measurements": (*md.GAME_LOG_COLUMNS, "updated_at"),
    "team_possession_stats": (*md.STATS_COLUMNS, "updated_at"),
    "team_possession_adjusted": (*md.ADJUSTED_COLUMNS, "updated_at"),
    "team_rating_components": (*md.COMPONENT_COLUMNS, "created_at"),
}
#: table -> natural key (``release.PROJECTION_KEYS``) used for row order.
ROW_KEYS = {
    "game_venues": ("game_id",),
    "v5_rating_snapshots": ("snapshot_id",),
    "team_season_stats": ("season", "as_of_week", "team", "role", "metric"),
    "matchup_data_publications": ("publication_id",),
    "team_game_measurements": md.TABLES["team_game_measurements"][1],
    "team_possession_stats": md.TABLES["team_possession_stats"][1],
    "team_possession_adjusted": md.TABLES["team_possession_adjusted"][1],
    "team_rating_components": ("component_id",),
}
#: INTEGER/BIGINT columns per table (migration 0025); builders may yield floats.
INTEGER_COLUMNS = {
    "game_venues": ("game_id", "venue_id"),
    "v5_rating_snapshots": ("season", "week", "game_id"),
    "team_season_stats": ("season", "as_of_week", "n", "games", "rank", "cohort_size"),
    "matchup_data_publications": ("season",),
    "team_game_measurements": ("season", "game_id", "week"),
    "team_possession_stats": (
        "season",
        "as_of_week",
        "games",
        "games_excluded",
        "rank",
        "cohort_size",
    ),
    "team_possession_adjusted": (
        "season",
        "as_of_week",
        "adjusted_rank",
        "cohort_size",
        "games",
    ),
    "team_rating_components": ("season", "as_of_week", "game_id", "completed_games"),
}
#: team_season_stats provenance name -> revision input name.
TEAM_STATS_SOURCES = {
    "byplay": "byplay",
    "drives": "drives",
    "games": "schedule",
    "game_outcomes": "finals",
    "teams": "teams",
}
#: Optional prior columns ``md.build_rating_components`` reads.
PRIOR_DETAIL_COLUMNS = (
    "prior_source",
    "prior_source_season",
    "annual_decay_steps",
    "fallback_reason",
)


class FootballProjectionError(ValueError):
    """The inputs cannot produce the football tables of a season release."""


def build_football(
    *,
    frames: Mapping[str, pd.DataFrame],
    inputs: Any,
    revision: Mapping[str, Any],
    identity: Mapping[str, str],
    ratings_id: str,
    measurement_id: str,
) -> dict[str, list[dict]]:
    """Return ``{key: rows}`` for exactly :data:`FOOTBALL_KEYS`.

    Arguments are as for ``projection_serving.build_serving_core``.
    """
    tables, _ = _build(
        frames=frames,
        inputs=inputs,
        revision=revision,
        identity=identity,
        ratings_id=ratings_id,
        measurement_id=measurement_id,
    )
    return tables


def football_report(
    *,
    frames: Mapping[str, pd.DataFrame],
    inputs: Any,
    revision: Mapping[str, Any],
    identity: Mapping[str, str],
    ratings_id: str,
    measurement_id: str,
) -> dict[str, Any]:
    """Coverage facts of the same build: venue coverage and team-stats reports."""
    _, report = _build(
        frames=frames,
        inputs=inputs,
        revision=revision,
        identity=identity,
        ratings_id=ratings_id,
        measurement_id=measurement_id,
    )
    return report


def run_id_of(identity: Mapping[str, Any]) -> str:
    """The run id: ``identity['run_id']`` or, for a bare prepare identity, the
    id ``runner.prepare`` derives from it."""
    if identity.get("run_id"):
        return str(identity["run_id"])
    return f"season-{SEASON}-" + sha256_hex(canonical_bytes(dict(identity)))[:24]


def _build(
    *,
    frames: Mapping[str, pd.DataFrame],
    inputs: Any,
    revision: Mapping[str, Any],
    identity: Mapping[str, Any],
    ratings_id: str,
    measurement_id: str,
) -> tuple[dict[str, list[dict]], dict[str, Any]]:
    for name, value in (("ratings_id", ratings_id), ("measurement_id", measurement_id)):
        if len(str(value)) != 64:
            raise FootballProjectionError(f"{name} must be a sha256 hex digest")
    run_id = run_id_of(identity)
    active_week = int(identity["active_week"])
    captured_at = utc(revision["captured_at"])
    fbs = _fbs_teams(inputs.teams)
    venues, venue_report = _game_venues(inputs, active_week, captured_at)
    stats, stats_report = _team_season_stats(
        inputs, revision, fbs, active_week, captured_at
    )
    matchup = _matchup_tables(
        frames=frames,
        inputs=inputs,
        fbs=fbs,
        run_id=run_id,
        ratings_id=ratings_id,
        measurement_id=measurement_id,
        code_sha=identity.get("code_sha"),
        revision=revision,
        captured_at=captured_at,
    )
    tables = {
        "game_venues": venues,
        "v5_rating_snapshots": _snapshots(
            frames, inputs, run_id, ratings_id, captured_at
        ),
        "team_season_stats": stats,
        **matchup,
    }
    rows = {
        key: _sorted(key, clean_rows(_integers(key, tables[key]), _columns(key)))
        for key in FOOTBALL_KEYS
    }
    return rows, {"game_venues": venue_report, "team_season_stats": stats_report}


def _columns(key: str) -> tuple[str, ...]:
    return {
        "game_venues": VENUE_COLUMNS,
        "v5_rating_snapshots": SNAPSHOT_COLUMNS,
        "team_season_stats": TEAM_STATS_COLUMNS,
        "matchup_data_publications": PUBLICATION_COLUMNS,
        **MATCHUP_COLUMNS,
    }[key]


def _integers(key: str, frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column in INTEGER_COLUMNS[key]:
        frame[column] = pd.to_numeric(frame[column]).astype("Int64")
    return frame


def _sorted(key: str, rows: list[dict]) -> list[dict]:
    names = ROW_KEYS[key]
    return sorted(rows, key=lambda row: tuple(row[name] for name in names))


def _fbs_teams(teams: pd.DataFrame | None) -> set[str]:
    """Provider names of FBS teams; FBS membership requires the pinned teams input."""
    if teams is None or teams.empty:
        raise FootballProjectionError(
            "the revision lacks the pinned 'teams' input; FBS membership for team "
            "stats and matchup data requires it (no schedule-name fallback)"
        )
    name = next((c for c in ("team", "school") if c in teams.columns), None)
    if name is None or "classification" not in teams.columns:
        raise FootballProjectionError(
            "pinned teams input needs team/school and classification columns"
        )
    fbs = teams.loc[teams.classification.astype(str).str.lower().eq("fbs"), name]
    if fbs.empty:
        raise FootballProjectionError("pinned teams input lists no FBS team")
    return set(fbs.astype(str))


def _provider_schedule(inputs: Any) -> pd.DataFrame:
    """The full season schedule with provider team names (Silver naming)."""
    schedule = inputs.schedule.copy()
    for side in ("home_team", "away_team"):
        schedule[side] = schedule[side + "_provider"]
    return schedule


# --------------------------------------------------------------------------
# game_venues
# --------------------------------------------------------------------------
def _game_venues(
    inputs: Any, active_week: int, captured_at: pd.Timestamp
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """One row per scheduled game Silver knows; cities required through the
    active week, missing later-week cities are reported, not blocking."""
    if inputs.venue_games is None or inputs.venues is None:
        return pd.DataFrame(columns=list(VENUE_COLUMNS)), {
            "state": "missing_inputs",
            "rows": 0,
        }
    schedule = inputs.schedule
    rows, report = build_game_venue_rows(
        inputs.venue_games, inputs.venues, schedule.game_id.astype(int)
    )
    required = sorted(
        int(g) for g in schedule.loc[schedule.week.le(active_week), "game_id"]
    )
    report |= require_venue_cities(rows, required)
    report["later_missing_city_game_ids"] = sorted(
        int(row["game_id"])
        for row in rows
        if not row["city"] and int(row["game_id"]) not in set(required)
    )
    frame = pd.DataFrame.from_records(rows, columns=list(VENUE_COLUMNS[:-2]))
    frame["source"] = "cfbd"
    frame["updated_at"] = captured_at
    return frame, {"state": "built", **report}


# --------------------------------------------------------------------------
# v5_rating_snapshots
# --------------------------------------------------------------------------
_RATING_VALUES = (
    "offense_rating",
    "offense_variance",
    "defense_rating",
    "defense_variance",
    "overall_rating",
    "overall_variance",
)


def _prior_fallbacks(priors: pd.DataFrame) -> dict[str, str]:
    """Team -> ``;``-joined distinct prior fallback reasons (legacy rule)."""
    if "fallback_reason" not in priors.columns:
        return {}
    selected = priors[priors.season.eq(SEASON) & priors.fallback_reason.notna()]
    return {
        str(team): ";".join(sorted({str(v) for v in group.fallback_reason if str(v)}))
        for team, group in selected.groupby("team")
    }


def _snapshots(
    frames: Mapping[str, pd.DataFrame],
    inputs: Any,
    run_id: str,
    ratings_id: str,
    captured_at: pd.Timestamp,
) -> pd.DataFrame:
    pregame = frames["ratings"].copy()
    current = frames["current_ratings"].copy()
    fallbacks = _prior_fallbacks(inputs.priors)
    week = pregame.target_week.astype(int)
    pregame["week"] = week
    pregame["snapshot_class"] = "pregame"
    pregame["snapshot_id"] = [
        f"{run_id}:pregame:{team}:" + ("preseason" if w == 0 else f"week-{w}")
        for team, w in zip(pregame.team, week, strict=True)
    ]
    pregame["fallback_reason"] = [
        fallbacks.get(str(team)) if w == 0 else None
        for team, w in zip(pregame.team, week, strict=True)
    ]
    post_week = current.post_week.astype(int)
    current["week"] = post_week
    current["snapshot_class"] = "current"
    current["snapshot_id"] = [
        f"{run_id}:current:post-week-{n}:{team}"
        for team, n in zip(current.team, post_week, strict=True)
    ]
    current["fallback_reason"] = None
    out = pd.concat([pregame, current], ignore_index=True)
    if out.snapshot_id.duplicated().any():
        raise FootballProjectionError("duplicate rating snapshot id")
    # Prepared pregame states carry the sentinel game_id 0; snapshots have none.
    out["game_id"] = None
    out["season"] = SEASON
    out["source_run_id"] = run_id
    out["source_manifest_sha256"] = ratings_id
    out["created_at"] = captured_at
    for column in _RATING_VALUES:
        out[column] = out[column].astype(float)
    return out


# --------------------------------------------------------------------------
# team_season_stats
# --------------------------------------------------------------------------
def _team_season_stats(
    inputs: Any,
    revision: Mapping[str, Any],
    fbs: set[str],
    active_week: int,
    captured_at: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    refs = revision["inputs"]
    versions = {
        name: refs[source]["sha256"] for name, source in TEAM_STATS_SOURCES.items()
    }
    games = _provider_schedule(inputs)
    outcomes = inputs.finals.assign(completed=True)
    parts, reports = [], {}
    for week in range(1, active_week + 1):
        result = build_team_season_stats(
            byplay=inputs.byplay,
            drives=inputs.drives,
            games=games,
            outcomes=outcomes,
            fbs_teams=fbs,
            season=SEASON,
            as_of_week=week,
        )
        parts.append(result.frame)
        reports[str(week)] = result.report
    columns = list(TEAM_STATS_COLUMNS[:-2])
    frame = pd.concat(
        [part for part in parts if not part.empty] or [pd.DataFrame(columns=columns)],
        ignore_index=True,
    )
    frame["source_versions"] = [dict(versions)] * len(frame)
    frame["updated_at"] = captured_at
    return frame, reports


# --------------------------------------------------------------------------
# matchup data tables and their publication receipt
# --------------------------------------------------------------------------
def _component_priors(priors: pd.DataFrame, teams: set[str]) -> pd.DataFrame:
    selected = priors[priors.season.eq(SEASON) & priors.team.isin(teams)].copy()
    for column in PRIOR_DETAIL_COLUMNS:
        if column not in selected.columns:
            selected[column] = None
    return selected.sort_values(["team", "unit_role"], kind="mergesort")


def _records_sha(observations: pd.DataFrame) -> str:
    keys = ["season", "game_id", "team", "unit_role", "measurement_id"]
    ordered = observations.sort_values(keys, kind="mergesort")
    columns = sorted(ordered.columns)
    return sha256_hex(canonical_bytes(clean_rows(ordered, columns)))


def _matchup_tables(
    *,
    frames: Mapping[str, pd.DataFrame],
    inputs: Any,
    fbs: set[str],
    run_id: str,
    ratings_id: str,
    measurement_id: str,
    code_sha: str | None,
    revision: Mapping[str, Any],
    captured_at: pd.Timestamp,
) -> dict[str, pd.DataFrame]:
    observations = frames["measurements"]
    schedule = inputs.schedule
    game_names = set(schedule.home_team_provider) | set(schedule.away_team_provider)
    rating_roles = frames["rating_roles"]
    pregame_roles = rating_roles[rating_roles.target_week.astype(int).ge(1)].copy()
    pregame_roles["game_id"] = None
    current_roles = frames["current_rating_roles"]
    teams = set(schedule.home_team) | set(schedule.away_team)
    priors = _component_priors(inputs.priors, teams)
    names = (
        set(observations.team)
        | set(observations.opponent)
        | set(pregame_roles.team)
        | set(current_roles.team)
        | set(priors.team)
    )
    name_map = md.resolve_game_names(names, game_names, TEAM_LOGO_MAP)
    prepared = md.prepare_observations(observations, name_map)
    post_cutoffs = frames["current_ratings"].drop_duplicates("post_week")
    as_of_cutoffs = {
        int(n) + 1: pd.Timestamp(cutoff)
        for n, cutoff in zip(
            post_cutoffs.post_week, post_cutoffs.cutoff_utc, strict=True
        )
    }
    source_versions = {"observations": measurement_id, "rating_run": run_id}
    log = md.build_game_log(
        prepared,
        fbs_names=fbs,
        measurement_manifest_sha256=measurement_id,
        source_versions=source_versions,
    )
    stats = md.build_possession_stats(
        prepared,
        season=SEASON,
        as_of_cutoffs=as_of_cutoffs,
        fbs_names=fbs,
        rating_manifest_sha256=ratings_id,
        measurement_manifest_sha256=measurement_id,
        source_versions=source_versions,
    )
    adjusted = md.build_possession_adjusted(
        prepared,
        season=SEASON,
        as_of_cutoffs=as_of_cutoffs,
        fbs_names=fbs,
        rating_manifest_sha256=ratings_id,
        measurement_manifest_sha256=measurement_id,
    )
    components = md.build_rating_components(
        run_id=run_id,
        manifest_sha256=ratings_id,
        candidate_id=CANDIDATE_ID,
        priors=priors,
        pregame_roles=pregame_roles,
        current_roles=current_roles,
        prepared=prepared,
        name_map=name_map,
        season=SEASON,
        preseason_cutoff=utc(revision["pre_week_cutoffs"]["0"]),
    )
    payload = md.MatchupPayload(
        frames={
            "team_game_measurements": log,
            "team_possession_stats": stats,
            "team_possession_adjusted": adjusted,
            "team_rating_components": components,
        },
        rating_scale=md.fit_rating_scale(components),
    )
    payload_sha = md.payload_sha256(payload.records())
    publication = {
        "publication_id": f"{SEASON}:{LINEAGE}:{ratings_id[:12]}:{payload_sha[:12]}",
        "season": SEASON,
        "lineage": LINEAGE,
        "rating_manifest_sha256": ratings_id,
        "rating_manifest_uri": f"season-run:{run_id}#ratings",
        "measurement_manifest_sha256": measurement_id,
        "measurement_manifest_uri": f"season-run:{run_id}#measurements",
        "observations_records_sha": _records_sha(observations),
        "as_of_weeks": sorted(
            set(as_of_cutoffs) | {int(w) for w in components.as_of_week}
        ),
        "rating_scale": payload.rating_scale,
        "row_counts": payload.row_counts(),
        "payload_sha256": payload_sha,
        "code_sha": code_sha,
        "published_at": captured_at,
    }
    stamp = {"team_rating_components": "created_at"}
    tables = {
        table: frame.assign(**{stamp.get(table, "updated_at"): captured_at})
        for table, frame in payload.frames.items()
    }
    tables["matchup_data_publications"] = pd.DataFrame([publication])
    return tables
