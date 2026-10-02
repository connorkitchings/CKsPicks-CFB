"""Matchup data layer v2 builders (contract 2026-10-02/01-matchup-data-layer-v2).

Pure functions from the V5 rating artifacts (the possession observations and the
rating manifest's role tables) to the rows of five Neon tables:

* ``team_game_measurements``  per-game log, faithful to ``possession_observation``
* ``team_possession_stats``   RAW V5 metrics per as-of week (shown on matchups)
* ``team_possession_adjusted`` opponent-adjusted values (never read by matchups)
* ``team_rating_components``  rating decomposition: prior vs per-game evidence

Offense rows in ``possession_observation`` carry the team's own numbers; defense
rows carry the opponent's, so a defense metric is what that defense *allowed*.
Weekly adjusted values are recomputed with the same pure adjuster the ratings
use (``adjust_possession_history``) at each post-week cutoff; for the serving
lineage this reproduces the per-game rating evidence to floating-point precision
(contract Phase 0), which the verifier re-checks on every publish.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.ratings.possession_intended_update import (
    AVAILABILITY_HOURS,
    MEASUREMENT_ID,
    usable_ppp_mask,
)
from cks_picks_cfb.ratings.possession_measurements import adjust_possession_history

ADJUSTMENT_METHOD = "measurement_iterative_4pass_v1"
ROLES = ("offense", "defense")
ADJUSTED_MEASUREMENTS = ("ppp", "epa_per_possession")
STAT_METRICS = (
    "ppp",
    "epa_per_possession",
    "epa_per_play",
    "plays_per_possession",
    "possessions_per_game",
    "non_offense_points_per_game",
)
#: Metrics with no better/worse direction (pace) are not ranked.
UNRANKED_METRICS = {"possessions_per_game"}

GAME_LOG_COLUMNS = (
    "season",
    "game_id",
    "team",
    "unit_role",
    "measurement_id",
    "week",
    "season_type",
    "kickoff_utc",
    "opponent",
    "side",
    "numerator",
    "denominator",
    "raw_value",
    "usable_exposure",
    "exposure_unit",
    "coverage_status",
    "missing_reason",
    "quality_flags",
    "timing_class",
    "rating_usable",
    "opponent_fbs",
    "measurement_manifest_sha256",
    "source_versions",
)
STATS_COLUMNS = (
    "season",
    "as_of_week",
    "team",
    "role",
    "metric",
    "value",
    "numerator",
    "denominator",
    "n",
    "games",
    "games_excluded",
    "excluded",
    "rank",
    "cohort_size",
    "as_of_cutoff",
    "rating_manifest_sha256",
    "measurement_manifest_sha256",
    "source_versions",
)
ADJUSTED_COLUMNS = (
    "season",
    "as_of_week",
    "team",
    "role",
    "measurement_id",
    "raw_value",
    "adjusted_value",
    "opponent_adjustment",
    "adjusted_rank",
    "cohort_size",
    "primary_exposure",
    "games",
    "adjustment_method",
    "as_of_cutoff",
    "rating_manifest_sha256",
    "measurement_manifest_sha256",
)
COMPONENT_COLUMNS = (
    "component_id",
    "v5_snapshot_id",
    "lineage",
    "candidate_id",
    "source_manifest_sha256",
    "snapshot_class",
    "season",
    "as_of_week",
    "game_id",
    "cutoff_utc",
    "rating_team",
    "team",
    "unit_role",
    "rating_mean",
    "rating_variance",
    "prior_mean",
    "prior_variance",
    "prior_weight",
    "prior_contribution",
    "evidence_weight",
    "process_variance",
    "k",
    "usable_exposure",
    "completed_games",
    "evidence",
    "excluded_observations",
    "prior_detail",
    "fallback_reason",
)
#: table -> (columns, primary key columns, jsonb columns)
TABLES: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "team_game_measurements": (
        GAME_LOG_COLUMNS,
        ("season", "game_id", "team", "unit_role", "measurement_id"),
        ("source_versions",),
    ),
    "team_possession_stats": (
        STATS_COLUMNS,
        ("season", "as_of_week", "team", "role", "metric"),
        ("excluded", "source_versions"),
    ),
    "team_possession_adjusted": (
        ADJUSTED_COLUMNS,
        ("season", "as_of_week", "team", "role", "measurement_id"),
        (),
    ),
    "team_rating_components": (
        COMPONENT_COLUMNS,
        ("component_id",),
        ("evidence", "excluded_observations", "prior_detail"),
    ),
}


class MatchupDataError(ValueError):
    """Raised when artifacts violate the contract the builders depend on."""


def upsert_sql(table: str) -> str:
    """Idempotent upsert for a table (components are append-only: DO NOTHING)."""
    columns, keys, jsonb = TABLES[table]
    values = ", ".join(f"%({c})s::jsonb" if c in jsonb else f"%({c})s" for c in columns)
    head = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({values}) "
    if table == "team_rating_components":
        return head + "ON CONFLICT (component_id) DO NOTHING"
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c not in keys)
    return (
        head
        + f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {updates}, updated_at = NOW()"
    )


# --------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------
def resolve_game_names(
    artifact_names: Iterable[str],
    game_names: set[str],
    alias_map: Mapping[str, str],
) -> dict[str, str]:
    """Map artifact team names to the season's game (CFBD) names.

    ``alias_map`` is ``TEAM_LOGO_MAP`` (game name -> artifact name). A blind
    inverse is wrong: Hawai_i has three keys and FIU maps to a name that is
    already a game name. So keep the name if it is a game name; otherwise pick
    the single alias key that is a game name; otherwise keep it unchanged
    (teams outside the season's games, e.g. FCS opponents).
    """
    resolved: dict[str, str] = {}
    for name in sorted(set(artifact_names)):
        if name in game_names:
            resolved[name] = name
            continue
        candidates = sorted(
            key
            for key, value in alias_map.items()
            if value == name and key in game_names
        )
        if len(candidates) > 1:
            raise MatchupDataError(f"ambiguous game name for {name!r}: {candidates}")
        resolved[name] = candidates[0] if candidates else name
    return resolved


# --------------------------------------------------------------------------
# Observations
# --------------------------------------------------------------------------
_OBS_REQUIRED = {
    "season",
    "week",
    "game_id",
    "kickoff_utc",
    "team",
    "opponent",
    "side",
    "measurement_id",
    "unit_role",
    "numerator",
    "denominator",
    "raw_value",
    "usable_exposure",
    "exposure_unit",
    "coverage_status",
    "missing_reason",
    "quality_flags",
    "timing_class",
}


def prepare_observations(
    observations: pd.DataFrame, name_map: Mapping[str, str]
) -> pd.DataFrame:
    """Validate, normalize types and attach game names and availability."""
    if missing := sorted(_OBS_REQUIRED - set(observations.columns)):
        raise MatchupDataError(f"observations lack columns: {missing}")
    if observations.duplicated(
        ["season", "game_id", "team", "unit_role", "measurement_id"]
    ).any():
        raise MatchupDataError("duplicate observation key")
    frame = observations.copy()
    frame["kickoff_utc"] = pd.to_datetime(frame["kickoff_utc"], utc=True)
    frame["available_utc"] = frame["kickoff_utc"] + pd.Timedelta(
        hours=AVAILABILITY_HOURS
    )
    for column in ("numerator", "denominator", "raw_value", "usable_exposure"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["team_game"] = frame["team"].map(lambda n: name_map.get(n, n))
    frame["opponent_game"] = frame["opponent"].map(lambda n: name_map.get(n, n))
    frame["observed"] = frame["coverage_status"].eq("observed") & np.isfinite(
        frame["raw_value"]
    )
    return frame


def build_game_log(
    prepared: pd.DataFrame,
    *,
    fbs_names: set[str],
    measurement_manifest_sha256: str,
    source_versions: Mapping[str, str],
) -> pd.DataFrame:
    """One row per observation, faithful to the artifact (row-for-row)."""
    ppp = prepared["measurement_id"].eq(MEASUREMENT_ID)
    usable = pd.Series(False, index=prepared.index)
    if ppp.any():
        usable.loc[ppp] = usable_ppp_mask(prepared.loc[ppp]).to_numpy()
    out = pd.DataFrame(
        {
            "season": prepared["season"].astype(int),
            "game_id": prepared["game_id"].astype("int64"),
            "team": prepared["team_game"],
            "unit_role": prepared["unit_role"],
            "measurement_id": prepared["measurement_id"],
            "week": prepared["week"].astype(int),
            "season_type": None,
            "kickoff_utc": prepared["kickoff_utc"],
            "opponent": prepared["opponent_game"],
            "side": prepared["side"],
            "numerator": prepared["numerator"],
            "denominator": prepared["denominator"],
            "raw_value": prepared["raw_value"],
            "usable_exposure": prepared["usable_exposure"],
            "exposure_unit": prepared["exposure_unit"],
            "coverage_status": prepared["coverage_status"],
            "missing_reason": prepared["missing_reason"],
            "quality_flags": prepared["quality_flags"],
            "timing_class": prepared["timing_class"],
            "rating_usable": usable,
            "opponent_fbs": prepared["opponent_game"].isin(fbs_names),
            "measurement_manifest_sha256": measurement_manifest_sha256,
            "source_versions": [dict(source_versions)] * len(prepared),
        }
    )
    return out.loc[:, list(GAME_LOG_COLUMNS)].reset_index(drop=True)


# --------------------------------------------------------------------------
# Windows, raw stats, adjusted stats
# --------------------------------------------------------------------------
def _window(
    prepared: pd.DataFrame, as_of_week: int, cutoff: pd.Timestamp
) -> pd.DataFrame:
    """Games before ``as_of_week`` that were available at the post-week cutoff."""
    return prepared[
        prepared["week"].lt(as_of_week) & prepared["available_utc"].le(cutoff)
    ]


def _stat_rows(window: pd.DataFrame) -> pd.DataFrame:
    """Per team and role: value, numerator, denominator, games per stat metric."""
    rows: list[dict[str, Any]] = []
    by_measure = {m: g for m, g in window.groupby("measurement_id")}

    def observed(measure: str) -> pd.DataFrame:
        frame = by_measure.get(measure)
        if frame is None:
            return pd.DataFrame(columns=window.columns)
        if measure == MEASUREMENT_ID:
            return frame[usable_ppp_mask(frame)]
        return frame[frame["observed"] & frame["denominator"].gt(0)]

    def unobserved(measure: str) -> pd.DataFrame:
        frame = by_measure.get(measure)
        if frame is None:
            return pd.DataFrame(columns=window.columns)
        ok = observed(measure).index
        return frame[~frame.index.isin(ok)]

    def emit(
        metric: str, ok: pd.DataFrame, bad: pd.DataFrame, num: str, den: str | None
    ):
        grouped = ok.groupby(["team_game", "unit_role"])
        keys = set(grouped.groups) | {
            (t, r) for t, r in zip(bad["team_game"], bad["unit_role"], strict=True)
        }
        for team, role in sorted(keys):
            sub = (
                grouped.get_group((team, role))
                if (team, role) in grouped.groups
                else ok.iloc[0:0]
            )
            numerator = float(sub[num].sum()) if len(sub) else None
            denominator = float(sub[den].sum()) if den and len(sub) else None
            if den is None:
                value = (numerator / len(sub)) if len(sub) else None
                denominator = float(len(sub)) if len(sub) else None
            else:
                value = (
                    numerator / denominator
                    if denominator and denominator > 0 and numerator is not None
                    else None
                )
            lost = bad[(bad["team_game"] == team) & (bad["unit_role"] == role)]
            rows.append(
                {
                    "team": team,
                    "role": role,
                    "metric": metric,
                    "value": value,
                    "numerator": numerator,
                    "denominator": denominator,
                    "n": denominator or 0.0,
                    "games": int(len(sub)),
                    "games_excluded": int(lost["game_id"].nunique()),
                    "excluded": [
                        {"game_id": int(g), "reason": None if pd.isna(r) else str(r)}
                        for g, r in sorted(
                            zip(lost["game_id"], lost["missing_reason"], strict=True)
                        )
                    ],
                }
            )

    emit("ppp", observed("ppp"), unobserved("ppp"), "numerator", "denominator")
    emit(
        "epa_per_possession",
        observed("epa_per_possession"),
        unobserved("epa_per_possession"),
        "numerator",
        "denominator",
    )
    emit(
        "plays_per_possession",
        observed("plays_per_possession"),
        unobserved("plays_per_possession"),
        "numerator",
        "denominator",
    )
    # EPA per play: eligible EPA over eligible scrimmage plays, same games.
    epa = observed("eligible_epa")
    plays = observed("eligible_scrimmage_plays")
    both = epa.merge(
        plays[["game_id", "team_game", "unit_role", "raw_value"]],
        on=["game_id", "team_game", "unit_role"],
        suffixes=("", "_plays"),
    )
    both = both.assign(numerator=both["raw_value"], denominator=both["raw_value_plays"])
    emit("epa_per_play", both, unobserved("eligible_epa"), "numerator", "denominator")
    # Pace and non-offense points are per-game counts.
    emit(
        "possessions_per_game",
        observed("eligible_possessions").assign(numerator=lambda f: f["raw_value"]),
        unobserved("eligible_possessions"),
        "numerator",
        None,
    )
    emit(
        "non_offense_points_per_game",
        observed("non_offense_points").assign(numerator=lambda f: f["raw_value"]),
        unobserved("non_offense_points"),
        "numerator",
        None,
    )
    return pd.DataFrame.from_records(rows)


def build_possession_stats(
    prepared: pd.DataFrame,
    *,
    season: int,
    as_of_cutoffs: Mapping[int, pd.Timestamp],
    fbs_names: set[str],
    rating_manifest_sha256: str,
    measurement_manifest_sha256: str,
    source_versions: Mapping[str, str],
) -> pd.DataFrame:
    """Raw V5 metrics as of each week (games before the week's slate).

    ``as_of_cutoffs[N]`` is the post-week-(N-1) cutoff. Only FBS-vs-FBS games
    count, matching ``team_season_stats``. Ranks use the direction of the role
    (offense higher is better, defense lower is better) and skip pace.
    """
    frames: list[pd.DataFrame] = []
    in_fbs = prepared["team_game"].isin(fbs_names) & prepared["opponent_game"].isin(
        fbs_names
    )
    population = prepared[in_fbs]
    for week, cutoff in sorted(as_of_cutoffs.items()):
        window = _window(population, week, pd.Timestamp(cutoff))
        if window.empty:
            continue
        stats = _stat_rows(window)
        stats = stats[stats["team"].isin(fbs_names)].copy()
        stats["season"] = season
        stats["as_of_week"] = week
        stats["as_of_cutoff"] = pd.Timestamp(cutoff)
        frames.append(stats)
    if not frames:
        return pd.DataFrame(columns=list(STATS_COLUMNS))
    out = pd.concat(frames, ignore_index=True)
    out["rank"] = np.nan
    out["cohort_size"] = np.nan
    ranked = out[~out["metric"].isin(UNRANKED_METRICS) & out["games"].ge(1)]
    for (_, _, _), idx in ranked.groupby(
        ["as_of_week", "role", "metric"]
    ).groups.items():
        part = out.loc[idx]
        part = part[part["value"].notna()]
        if part.empty:
            continue
        higher = part["role"].iloc[0] == "offense"
        out.loc[part.index, "rank"] = part["value"].rank(
            method="min", ascending=not higher
        )
        out.loc[part.index, "cohort_size"] = len(part)
    out["rating_manifest_sha256"] = rating_manifest_sha256
    out["measurement_manifest_sha256"] = measurement_manifest_sha256
    out["source_versions"] = [dict(source_versions)] * len(out)
    return out.loc[:, list(STATS_COLUMNS)].reset_index(drop=True)


def build_possession_adjusted(
    prepared: pd.DataFrame,
    *,
    season: int,
    as_of_cutoffs: Mapping[int, pd.Timestamp],
    fbs_names: set[str],
    rating_manifest_sha256: str,
    measurement_manifest_sha256: str,
) -> pd.DataFrame:
    """Opponent-adjusted PPP and EPA per possession as of each week.

    The adjuster runs over the artifact's whole population (as the ratings do,
    so FCS opponents still inform opponent context); rows are emitted for
    ``fbs_names`` and ranked among them. Recomputed per cutoff, never carried.
    """
    history_all = prepared[prepared["measurement_id"].isin(ADJUSTED_MEASUREMENTS)]
    history_all = history_all[
        history_all["observed"] & history_all["denominator"].gt(0)
    ]
    frames: list[pd.DataFrame] = []
    for week, cutoff in sorted(as_of_cutoffs.items()):
        window = _window(history_all, week, pd.Timestamp(cutoff))
        if window.empty:
            continue
        raw, adjusted = adjust_possession_history(
            window[
                [
                    "team",
                    "opponent",
                    "unit_role",
                    "measurement_id",
                    "numerator",
                    "denominator",
                ]
            ]
        )
        exposure = window.groupby(["team", "unit_role", "measurement_id"]).agg(
            primary_exposure=("denominator", "sum"), games=("game_id", "nunique")
        )
        names = window.drop_duplicates("team").set_index("team")["team_game"]
        rows = []
        for (team, role, measure), raw_value in raw.items():
            game_team = names.get(team, team)
            if game_team not in fbs_names:
                continue
            adj = adjusted[(team, role, measure)]
            stats = exposure.loc[(team, role, measure)]
            rows.append(
                {
                    "season": season,
                    "as_of_week": week,
                    "team": game_team,
                    "role": role,
                    "measurement_id": measure,
                    "raw_value": raw_value,
                    "adjusted_value": adj,
                    "opponent_adjustment": raw_value - adj,
                    "primary_exposure": float(stats.primary_exposure),
                    "games": int(stats.games),
                    "adjustment_method": ADJUSTMENT_METHOD,
                    "as_of_cutoff": pd.Timestamp(cutoff),
                }
            )
        if rows:
            frames.append(pd.DataFrame.from_records(rows))
    if not frames:
        return pd.DataFrame(columns=list(ADJUSTED_COLUMNS))
    out = pd.concat(frames, ignore_index=True)
    out["adjusted_rank"] = np.nan
    out["cohort_size"] = np.nan
    for _, idx in out.groupby(["as_of_week", "role", "measurement_id"]).groups.items():
        part = out.loc[idx]
        higher = part["role"].iloc[0] == "offense"
        out.loc[part.index, "adjusted_rank"] = part["adjusted_value"].rank(
            method="min", ascending=not higher
        )
        out.loc[part.index, "cohort_size"] = len(part)
    out["rating_manifest_sha256"] = rating_manifest_sha256
    out["measurement_manifest_sha256"] = measurement_manifest_sha256
    return out.loc[:, list(ADJUSTED_COLUMNS)].reset_index(drop=True)


# --------------------------------------------------------------------------
# Rating components (intended-update lineage)
# --------------------------------------------------------------------------
def _json_list(value: Any) -> list[Any]:
    """``source_game_ids`` is stored as a JSON *string*; never iterate it."""
    if isinstance(value, str):
        parsed = json.loads(value)
    elif value is None:
        parsed = []
    else:
        parsed = list(value)
    if not isinstance(parsed, list):
        raise MatchupDataError("expected a JSON list")
    return parsed


def fit_rating_scale(components: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Per-role z-scale recovered from the evidence: z = (adjusted - center)/scale.

    ``adjusted_z`` is exactly linear in ``adjusted_ppp`` per role, so the fit
    recovers the scale the engine used (center, spread, sign) with its max
    residual as a self-check.
    """
    scale: dict[str, dict[str, float]] = {}
    for role in ROLES:
        xs: list[float] = []
        zs: list[float] = []
        for evidence in components.loc[components["unit_role"].eq(role), "evidence"]:
            for item in evidence:
                xs.append(float(item["adjusted_ppp"]))
                zs.append(float(item["adjusted_z"]))
        if len(xs) < 2 or np.ptp(xs) == 0:
            continue
        slope, intercept = np.polyfit(xs, zs, 1)
        residual = float(
            np.max(np.abs(np.array(zs) - (slope * np.array(xs) + intercept)))
        )
        scale[role] = {
            "center": float(-intercept / slope),
            "spread": float(abs(1.0 / slope)),
            "sign": 1.0 if slope > 0 else -1.0,
            "max_residual": residual,
        }
    return scale


def build_rating_components(
    *,
    run_id: str,
    manifest_sha256: str,
    candidate_id: str,
    priors: pd.DataFrame,
    pregame_roles: pd.DataFrame,
    current_roles: pd.DataFrame,
    prepared: pd.DataFrame,
    name_map: Mapping[str, str],
    season: int,
    preseason_cutoff: pd.Timestamp,
) -> pd.DataFrame:
    """Decompose every projected V5 snapshot role into prior and evidence.

    Snapshot ids follow ``publish_v5_intended_update_ratings.py``: preseason
    ``{run}:pregame:{team}:preseason``, pregame ``{run}:pregame:{team}:{game}``,
    current ``{run}:current:post-week-{N-1}:{team}``. ``excluded_observations``
    lists the PPP observations the rating could not use (the explanation never
    names them), from the same availability window as the rating.
    """
    ppp = prepared[prepared["measurement_id"].eq(MEASUREMENT_ID)]
    unusable = ppp[~usable_ppp_mask(ppp)]
    by_key = {
        key: group.sort_values("game_id")
        for key, group in unusable.groupby(["team", "unit_role"])
    }
    rows: list[dict[str, Any]] = []

    def excluded(team: str, role: str, cutoff: pd.Timestamp) -> list[dict[str, Any]]:
        group = by_key.get((team, role))
        if group is None:
            return []
        hit = group[group["available_utc"].le(cutoff)]
        return [
            {
                "game_id": int(r.game_id),
                "week": int(r.week),
                "reason": None if pd.isna(r.missing_reason) else str(r.missing_reason),
            }
            for r in hit.itertuples(index=False)
        ]

    for r in priors.itertuples(index=False):
        team = str(r.team)
        rows.append(
            {
                "component_id": f"{run_id}:pregame:{team}:preseason:{r.unit_role}",
                "v5_snapshot_id": f"{run_id}:pregame:{team}:preseason",
                "lineage": "intended_update",
                "candidate_id": candidate_id,
                "source_manifest_sha256": manifest_sha256,
                "snapshot_class": "preseason",
                "season": season,
                "as_of_week": 0,
                "game_id": None,
                "cutoff_utc": pd.Timestamp(preseason_cutoff),
                "rating_team": team,
                "team": name_map.get(team, team),
                "unit_role": str(r.unit_role),
                "rating_mean": float(r.prior_mean),
                "rating_variance": float(r.prior_variance),
                "prior_mean": float(r.prior_mean),
                "prior_variance": float(r.prior_variance),
                "prior_weight": 1.0,
                "prior_contribution": float(r.prior_mean),
                "evidence_weight": 0.0,
                "process_variance": None,
                "k": None,
                "usable_exposure": 0.0,
                "completed_games": 0,
                "evidence": [],
                "excluded_observations": [],
                "prior_detail": {
                    "prior_source": None
                    if pd.isna(r.prior_source)
                    else str(r.prior_source),
                    "prior_source_season": (
                        None
                        if pd.isna(r.prior_source_season)
                        else float(r.prior_source_season)
                    ),
                    "annual_decay_steps": (
                        None
                        if pd.isna(r.annual_decay_steps)
                        else int(r.annual_decay_steps)
                    ),
                },
                "fallback_reason": None
                if pd.isna(r.fallback_reason)
                else str(r.fallback_reason),
            }
        )

    def decompose(frame: pd.DataFrame, snapshot_class: str) -> None:
        for r in frame.itertuples(index=False):
            team = str(r.team)
            role = str(r.unit_role)
            explanation = json.loads(r.explanation)
            evidence = list(explanation["evidence_contributions"])
            ids = _json_list(r.source_game_ids)
            if sorted(int(x) for x in ids) != sorted(
                int(e["game_id"]) for e in evidence
            ):
                raise MatchupDataError(
                    f"source_game_ids differ from evidence for {team} {role}"
                )
            cutoff = pd.Timestamp(r.cutoff_utc)
            if snapshot_class == "pregame":
                game_id = int(r.game_id)
                snapshot = f"{run_id}:pregame:{team}:{game_id}"
                as_of = int(r.week)
            else:
                game_id = None
                snapshot = f"{run_id}:current:post-week-{int(r.week) - 1}:{team}"
                as_of = int(r.week)
            prior_weight = float(explanation["prior_weight"])
            rows.append(
                {
                    "component_id": f"{snapshot}:{role}",
                    "v5_snapshot_id": snapshot,
                    "lineage": "intended_update",
                    "candidate_id": candidate_id,
                    "source_manifest_sha256": manifest_sha256,
                    "snapshot_class": snapshot_class,
                    "season": season,
                    "as_of_week": as_of,
                    "game_id": game_id,
                    "cutoff_utc": cutoff,
                    "rating_team": team,
                    "team": name_map.get(team, team),
                    "unit_role": role,
                    "rating_mean": float(r.rating_mean),
                    "rating_variance": float(r.rating_variance),
                    "prior_mean": float(r.prior_mean),
                    "prior_variance": float(r.prior_variance),
                    "prior_weight": prior_weight,
                    "prior_contribution": float(explanation["prior_contribution"]),
                    "evidence_weight": 1.0 - prior_weight,
                    "process_variance": None,
                    "k": float(explanation["k"]),
                    "usable_exposure": float(r.usable_exposure),
                    "completed_games": len(evidence),
                    "evidence": evidence,
                    "excluded_observations": excluded(team, role, cutoff),
                    "prior_detail": {},
                    "fallback_reason": None,
                }
            )

    decompose(pregame_roles, "pregame")
    decompose(current_roles, "current")
    out = pd.DataFrame.from_records(rows)
    if out["component_id"].duplicated().any():
        raise MatchupDataError("duplicate component id")
    return out.loc[:, list(COMPONENT_COLUMNS)].reset_index(drop=True)


# --------------------------------------------------------------------------
# Records and payload hash
# --------------------------------------------------------------------------
def _clean(value: Any) -> Any:
    if value is None or value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value


def to_records(table: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    """DB-ready dicts: NaN to None, numpy to Python, JSON columns as text."""
    columns, _, jsonb = TABLES[table]
    records: list[dict[str, Any]] = []
    for row in frame.loc[:, list(columns)].to_dict(orient="records"):
        record = {key: _clean(value) for key, value in row.items()}
        for column in jsonb:
            record[column] = json.dumps(
                row[column], sort_keys=True, default=_json_default
            )
        records.append(record)
    return records


def _json_default(value: Any) -> Any:
    cleaned = _clean(value)
    if cleaned is value:
        raise TypeError(f"not JSON serializable: {type(value)}")
    return cleaned


def payload_sha256(records_by_table: Mapping[str, list[dict[str, Any]]]) -> str:
    """Canonical hash of every row, so production can prove it publishes
    exactly what Preview verified."""
    digest = hashlib.sha256()
    for table in sorted(records_by_table):
        _, keys, _ = TABLES[table]
        ordered = sorted(
            records_by_table[table], key=lambda r: tuple(str(r[k]) for k in keys)
        )
        digest.update(table.encode())
        for record in ordered:
            digest.update(
                json.dumps(record, sort_keys=True, default=_iso).encode("utf-8")
            )
    return digest.hexdigest()


def _iso(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"not serializable: {type(value)}")


@dataclass
class MatchupPayload:
    """All tables for one publish, plus the receipt facts."""

    frames: dict[str, pd.DataFrame]
    rating_scale: dict[str, dict[str, float]] = field(default_factory=dict)

    def records(self) -> dict[str, list[dict[str, Any]]]:
        return {t: to_records(t, f) for t, f in self.frames.items()}

    def row_counts(self) -> dict[str, int]:
        return {t: int(len(f)) for t, f in self.frames.items()}
