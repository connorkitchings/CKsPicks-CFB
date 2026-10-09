"""Load, verify, gate and publish the matchup data layer (contract
2026-10-02/01-matchup-data-layer-v2).

Everything is bound to one rating manifest, the one the site serves. The
loaders re-verify manifest signatures, the independent verifier, every child
checksum and the measurement parent SHA; the gates reconcile the built rows to
the artifacts, to each other and to ``v5_rating_snapshots``; and the writer is a
single transaction that refuses to leave stale rows behind (the pipeline role
cannot DELETE).
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data import matchup_data as md
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.lake import PartitionedDatasetRef, iter_partitioned_dataset
from cks_picks_cfb.ratings.possession_intended_update import (
    CANDIDATE_ID,
    MEASUREMENT_ID,
    usable_ppp_mask,
)

INTENDED_UPDATE_SCHEMA = "v5_intended_update_2026_rating_manifest_v1"
INTENDED_UPDATE_VERIFIER_SCHEMA = "v5_intended_update_2026_rating_verification_v1"
BRIDGE_VERIFIER_SCHEMA = "v5_matchup_bridge_verification_v1"
TOL = 1e-9


class PublishError(RuntimeError):
    """A manifest, checksum, binding or gate check failed; nothing was written."""


@dataclass(frozen=True)
class GateResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Artifacts:
    lineage: str
    run_id: str
    candidate_id: str
    rating_manifest: dict[str, Any]
    rating_sha256: str
    rating_uri: str
    measurement_manifest: dict[str, Any]
    measurement_sha256: str
    measurement_uri: str
    observations: pd.DataFrame
    observations_records_sha: str
    observations_version_id: str
    priors: pd.DataFrame
    pregame_roles: pd.DataFrame
    current_roles: pd.DataFrame
    post_week_cutoffs: dict[int, pd.Timestamp]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_signed(storage: Any, uri: str, label: str) -> tuple[dict[str, Any], str]:
    raw = storage.read_bytes(uri)
    payload = json.loads(raw)
    verify_signed_payload(payload, label=label)
    return payload, _sha(raw)


def _load_child(storage: Any, ref: Mapping[str, Any], label: str) -> pd.DataFrame:
    raw = storage.read_bytes(str(ref["uri"]))
    if _sha(raw) != ref["raw_sha256"]:
        raise PublishError(f"{label} checksum changed")
    frame = pd.read_parquet(io.BytesIO(raw))
    if len(frame) != int(ref["rows"]):
        raise PublishError(f"{label} row count changed")
    return frame


def load_intended_update_artifacts(
    storage: Any, rating_manifest_uri: str, measurement_manifest_uri: str, season: int
) -> Artifacts:
    """Verified inputs of the repaired intended-update lineage."""
    rating, rating_sha = _read_signed(storage, rating_manifest_uri, "rating manifest")
    if (
        rating.get("schema_version") != INTENDED_UPDATE_SCHEMA
        or rating.get("state") != "frozen"
        or rating.get("candidate_id") != CANDIDATE_ID
    ):
        raise PublishError(
            "rating manifest is not the reviewed intended-update lineage"
        )
    verifier_uri = (
        f"{rating_manifest_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
    )
    verifier, _ = _read_signed(storage, verifier_uri, "rating verifier")
    if (
        verifier.get("schema_version") != INTENDED_UPDATE_VERIFIER_SCHEMA
        or verifier.get("state") != "verified"
        or verifier.get("rating_manifest_raw_sha256") != rating_sha
    ):
        raise PublishError("rating manifest lacks a matching independent verifier")

    measurement, measurement_sha = _read_signed(
        storage, measurement_manifest_uri, "measurement manifest"
    )
    parent = (rating.get("parents") or {}).get("measurement_manifest_sha256")
    if measurement_sha != parent:
        raise PublishError(
            "measurement manifest is not the rating manifest's parent "
            f"({measurement_sha[:12]} != {str(parent)[:12]})"
        )

    refs = rating["output_refs"]
    observation_ref = measurement["output_refs"]["observations"]
    ref = PartitionedDatasetRef(
        artifact_kind=observation_ref["artifact_kind"],
        dataset=observation_ref["dataset"],
        version_id=observation_ref["version_id"],
        schema_version=observation_ref["schema_version"],
        content_sha=observation_ref["content_sha"],
        records_sha=observation_ref["records_sha"],
        uri=observation_ref["uri"],
        row_count=observation_ref["row_count"],
        partition_keys=tuple(observation_ref["partition_keys"]),
    )
    observations = pd.concat(
        [p for p in iter_partitioned_dataset(storage, ref) if len(p)],
        ignore_index=True,
    )
    observations = observations[observations["season"].eq(season)].reset_index(
        drop=True
    )
    if observations.empty:
        raise PublishError(f"no {season} observations in the measurement parent")
    return Artifacts(
        lineage="intended_update",
        run_id=str(rating["identity"]["run_id"]),
        candidate_id=str(rating["candidate_id"]),
        rating_manifest=rating,
        rating_sha256=rating_sha,
        rating_uri=rating_manifest_uri,
        measurement_manifest=measurement,
        measurement_sha256=measurement_sha,
        measurement_uri=measurement_manifest_uri,
        observations=observations,
        observations_records_sha=ref.records_sha,
        observations_version_id=ref.version_id,
        priors=_load_child(storage, refs["priors"], "priors"),
        pregame_roles=_load_child(storage, refs["pregame_roles"], "pregame_roles"),
        current_roles=_load_child(storage, refs["current_roles"], "current_roles"),
        post_week_cutoffs={
            int(k): pd.Timestamp(v) for k, v in rating["post_week_cutoffs"].items()
        },
    )


@dataclass
class BuiltPayload:
    payload: md.MatchupPayload
    prepared: pd.DataFrame
    name_map: dict[str, str]
    as_of_cutoffs: dict[int, pd.Timestamp]
    weeks: list[int]
    source_versions: dict[str, str]


SIX_A_NAMESPACE = "rebuild/6a/"
SIX_A_STATES_OBSERVATIONS = "states_2026/observations.parquet"


def _read_6a_root(storage: Any, run_id: str, root_sha256: str) -> tuple[dict, str]:
    """The pinned published 6A root manifest, by raw sha256 (mirrors
    ``rebuild.published.open_pinned_run`` with ``PublishError`` failures)."""
    uri = f"{SIX_A_NAMESPACE}{run_id}/root-manifest.json"
    raw = storage.read_bytes(uri)
    if _sha(raw) != root_sha256:
        raise PublishError(f"6A root manifest {run_id} changed")
    root = json.loads(raw)
    verify_signed_payload(root, label="6A root manifest")
    if root.get("kind") != "rebuild_root_v1" or root.get("run_id") != run_id:
        raise PublishError(f"{run_id}: not the published 6A root it was pinned as")
    return root, uri


def _read_6a_frame(
    storage: Any, root: dict, prefix: str, relative: str
) -> tuple[bytes, str]:
    """A 6A run object, checked against the signed root's recorded hash."""
    key = prefix + relative
    expected = (root.get("objects") or {}).get(key)
    if expected is None:
        raise PublishError(f"{key} is not in the published 6A root manifest")
    raw = storage.read_bytes(key)
    if _sha(raw) != expected:
        raise PublishError(f"published 6A object changed: {key}")
    return raw, _sha(raw)


def load_6a_bridged_artifacts(
    storage: Any,
    rating_manifest_uri: str,
    six_a_run_id: str,
    six_a_root_sha256: str,
    season: int,
) -> Artifacts:
    """Verified inputs pairing a frozen intended-update rating manifest with the
    published 6A rebuild it names as its measurement parent.

    The rating side is checked exactly like ``load_intended_update_artifacts``
    (schema, frozen state, candidate, independent verifier, child checksums for
    priors and both roles frames). The measurement side resolves the pinned 6A
    root manifest — whose raw sha must equal the rating parent — and reads the
    2026 observations states through its hash-checked object map. Component
    snapshot ids therefore name the rating run, so the database gates reconcile
    them against the projected ``v5_rating_snapshots`` rows.
    """
    rating, rating_sha = _read_signed(storage, rating_manifest_uri, "rating manifest")
    if (
        rating.get("schema_version") != INTENDED_UPDATE_SCHEMA
        or rating.get("state") != "frozen"
        or rating.get("candidate_id") != CANDIDATE_ID
    ):
        raise PublishError(
            "rating manifest is not the reviewed intended-update lineage"
        )
    verifier_uri = (
        f"{rating_manifest_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
    )
    verifier, _ = _read_signed(storage, verifier_uri, "rating verifier")
    if (
        verifier.get("schema_version") != INTENDED_UPDATE_VERIFIER_SCHEMA
        or verifier.get("state") != "verified"
        or verifier.get("rating_manifest_raw_sha256") != rating_sha
    ):
        raise PublishError("rating manifest lacks a matching independent verifier")
    parent = (rating.get("parents") or {}).get("measurement_manifest_sha256")
    if parent != six_a_root_sha256:
        raise PublishError(
            "rating manifest measurement parent is not the pinned 6A root "
            f"({str(parent)[:12]} != {six_a_root_sha256[:12]})"
        )
    refs = rating["output_refs"]
    priors = _load_child(storage, refs["priors"], "priors")
    pregame_roles = _load_child(storage, refs["pregame_roles"], "pregame roles")
    current_roles = _load_child(storage, refs["current_roles"], "current roles")
    root, root_uri = _read_6a_root(storage, six_a_run_id, six_a_root_sha256)
    prefix = f"{root.get('namespace', SIX_A_NAMESPACE)}{six_a_run_id}/"
    obs_raw, obs_sha = _read_6a_frame(storage, root, prefix, SIX_A_STATES_OBSERVATIONS)
    observations = pd.read_parquet(io.BytesIO(obs_raw))
    observations = observations[observations["season"].eq(season)].reset_index(
        drop=True
    )
    if observations.empty:
        raise PublishError(f"no {season} observations in the published 6A run")
    return Artifacts(
        lineage="intended_update",
        run_id=str(rating["identity"]["run_id"]),
        candidate_id=str(rating["candidate_id"]),
        rating_manifest=rating,
        rating_sha256=rating_sha,
        rating_uri=rating_manifest_uri,
        measurement_manifest=root,
        measurement_sha256=six_a_root_sha256,
        measurement_uri=root_uri,
        observations=observations,
        observations_records_sha=obs_sha,
        observations_version_id=f"6a:{six_a_run_id}",
        priors=priors,
        pregame_roles=pregame_roles,
        current_roles=current_roles,
        post_week_cutoffs={
            int(k): pd.Timestamp(v) for k, v in rating["post_week_cutoffs"].items()
        },
    )


def build_payload(
    artifacts: Artifacts,
    *,
    season: int,
    game_names: set[str],
    alias_map: Mapping[str, str],
    weeks: list[int] | None = None,
) -> BuiltPayload:
    """All four data tables for the requested as-of weeks (default: all)."""
    names = set(artifacts.observations["team"]) | set(
        artifacts.observations["opponent"]
    )
    names |= set(artifacts.pregame_roles["team"]) | set(artifacts.current_roles["team"])
    names |= set(artifacts.priors["team"])
    name_map = md.resolve_game_names(names, game_names, alias_map)
    prepared = md.prepare_observations(artifacts.observations, name_map)
    available = {int(k) + 1: c for k, c in artifacts.post_week_cutoffs.items()}
    as_of_cutoffs = {w: c for w, c in available.items() if weeks is None or w in weeks}
    source_versions = {
        "observations": artifacts.observations_version_id,
        "rating_run": artifacts.run_id,
    }
    fbs = set(game_names)
    log = md.build_game_log(
        prepared,
        fbs_names=fbs,
        measurement_manifest_sha256=artifacts.measurement_sha256,
        source_versions=source_versions,
    )
    stats = md.build_possession_stats(
        prepared,
        season=season,
        as_of_cutoffs=as_of_cutoffs,
        fbs_names=fbs,
        rating_manifest_sha256=artifacts.rating_sha256,
        measurement_manifest_sha256=artifacts.measurement_sha256,
        source_versions=source_versions,
    )
    adjusted = md.build_possession_adjusted(
        prepared,
        season=season,
        as_of_cutoffs=as_of_cutoffs,
        fbs_names=fbs,
        rating_manifest_sha256=artifacts.rating_sha256,
        measurement_manifest_sha256=artifacts.measurement_sha256,
    )
    components = md.build_rating_components(
        run_id=artifacts.run_id,
        manifest_sha256=artifacts.rating_sha256,
        candidate_id=artifacts.candidate_id,
        priors=artifacts.priors,
        pregame_roles=artifacts.pregame_roles,
        current_roles=artifacts.current_roles,
        prepared=prepared,
        name_map=name_map,
        season=season,
        preseason_cutoff=pd.Timestamp("2026-08-20T00:00:00Z"),
    )
    if weeks is not None:
        components = components[components["as_of_week"].isin(weeks)].reset_index(
            drop=True
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
    return BuiltPayload(
        payload=payload,
        prepared=prepared,
        name_map=name_map,
        as_of_cutoffs=as_of_cutoffs,
        weeks=sorted(set(as_of_cutoffs) | set(components["as_of_week"])),
        source_versions=source_versions,
    )


# --------------------------------------------------------------------------
# Gates (database-free)
# --------------------------------------------------------------------------
def run_static_gates(built: BuiltPayload, game_names: set[str]) -> list[GateResult]:
    frames = built.payload.frames
    log, stats = frames["team_game_measurements"], frames["team_possession_stats"]
    adjusted, comps = (
        frames["team_possession_adjusted"],
        frames["team_rating_components"],
    )
    prepared = built.prepared
    results: list[GateResult] = []

    def gate(name: str, bad: list[str]) -> None:
        results.append(
            GateResult(
                name,
                not bad,
                "; ".join(bad[:5])
                + (f" (+{len(bad) - 5} more)" if len(bad) > 5 else ""),
            )
        )

    # Game log is row-for-row with the artifact.
    gate(
        "game log is row-for-row with possession_observation",
        [] if len(log) == len(prepared) else [f"{len(log)} != {len(prepared)}"],
    )

    # 2. decomposition identities (intended-update components only)
    bad = []
    for r in comps[comps["lineage"].eq("intended_update")].itertuples(index=False):
        contribution = sum(float(e["contribution"]) for e in r.evidence)
        if abs(r.rating_mean - (r.prior_contribution + contribution)) > TOL:
            bad.append(f"sum {r.component_id}")
        if r.snapshot_class != "preseason":
            if abs(r.prior_weight - r.rating_variance / r.prior_variance) > TOL:
                bad.append(f"prior_weight {r.component_id}")
            if r.k and abs(
                1 / r.rating_variance - (1 / r.prior_variance + r.usable_exposure / r.k)
            ) > TOL * max(1.0, 1 / r.rating_variance):
                bad.append(f"precision {r.component_id}")
            if (
                abs(r.usable_exposure - sum(float(e["exposure"]) for e in r.evidence))
                > TOL
            ):
                bad.append(f"exposure {r.component_id}")
    gate("rating = prior + evidence; weights and precision reconcile", bad)

    # 3. evidence matches the game log; evidence + excluded = window observations
    ppp = prepared[prepared["measurement_id"].eq(MEASUREMENT_ID)]
    by_team_role = {k: g for k, g in ppp.groupby(["team", "unit_role"])}
    usable = ppp[usable_ppp_mask(ppp)].set_index(["game_id", "team", "unit_role"])
    bad = []
    for r in comps[comps["snapshot_class"].ne("preseason")].itertuples(index=False):
        seen = set()
        for e in r.evidence:
            key = (int(e["game_id"]), r.rating_team, r.unit_role)
            seen.add(int(e["game_id"]))
            if key not in usable.index:
                bad.append(f"evidence not usable in log {r.component_id} {key[0]}")
                continue
            row = usable.loc[key]
            if (
                abs(float(e["raw_ppp"]) - float(row["raw_value"])) > TOL
                or abs(float(e["exposure"]) - float(row["denominator"])) > TOL
            ):
                bad.append(f"evidence values {r.component_id} {key[0]}")
        lost = {int(x["game_id"]) for x in r.excluded_observations}
        group = by_team_role.get((r.rating_team, r.unit_role))
        window = (
            set()
            if group is None
            else set(
                group[group["available_utc"].le(pd.Timestamp(r.cutoff_utc))][
                    "game_id"
                ].astype(int)
            )
        )
        if seen | lost != window or seen & lost:
            bad.append(f"window {r.component_id}")
    gate("evidence + excluded games = PPP observations in the window", bad)

    # 4/5. stats and adjusted agree with the current-class evidence
    cur = comps[comps["snapshot_class"].eq("current")]
    bad_stats, bad_adj = [], []
    stat_ppp = stats[stats["metric"].eq("ppp")].set_index(
        ["as_of_week", "team", "role"]
    )
    adj_ppp = adjusted[adjusted["measurement_id"].eq("ppp")].set_index(
        ["as_of_week", "team", "role"]
    )
    for r in cur.itertuples(index=False):
        key = (int(r.as_of_week), r.team, r.unit_role)
        if key not in stat_ppp.index:
            continue  # week has no stats (outside --weeks)
        row = stat_ppp.loc[key]
        total = sum(float(e["exposure"]) for e in r.evidence)
        if row["games"] != len(r.evidence):
            bad_stats.append(f"games {key}")
        if total > 0:
            value = (
                sum(float(e["raw_ppp"]) * float(e["exposure"]) for e in r.evidence)
                / total
            )
            if abs(row["value"] - value) > TOL:
                bad_stats.append(f"value {key}")
            adj_value = (
                sum(float(e["adjusted_ppp"]) * float(e["exposure"]) for e in r.evidence)
                / total
            )
            if (
                key not in adj_ppp.index
                or abs(adj_ppp.loc[key]["adjusted_value"] - adj_value) > TOL
            ):
                bad_adj.append(f"adjusted {key}")
    gate("raw PPP games/value equal the rating evidence", bad_stats)
    gate(
        "recomputed adjusted PPP equals the exposure-weighted rating evidence", bad_adj
    )

    # 7. a team's non-offense points equal the opponent's defense row
    nonoff = log[
        log["measurement_id"].eq("non_offense_points")
        & log["coverage_status"].eq("observed")
    ]
    offense = nonoff[nonoff["unit_role"].eq("offense")].set_index(["game_id", "team"])[
        "raw_value"
    ]
    defense = nonoff[nonoff["unit_role"].eq("defense")].set_index(
        ["game_id", "opponent"]
    )["raw_value"]
    shared = offense.index.intersection(defense.index)
    diff = (offense.loc[shared] - defense.loc[shared]).abs()
    gate(
        "non-offense points: offense row = opponent's defense row",
        [str(i) for i in diff[diff > TOL].index.tolist()],
    )

    # 8. every stored team is a game team (stats and adjusted are FBS-only)
    stray = sorted(
        (set(stats["team"]) | set(adjusted["team"]) | set(comps["team"])) - game_names
    )
    gate("every stats/adjusted/component team is a game team", stray)
    return results


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
def selected_rating_source(cur: Any, season: int) -> str | None:
    """The site's rating source: latest selected run's rating manifest SHA."""
    cur.execute(
        "SELECT pr.rating_manifest_sha256 FROM site_week_selections s "
        "JOIN prediction_runs pr ON s.run_id = pr.run_id WHERE s.season = %s "
        "ORDER BY s.week DESC LIMIT 1",
        (season,),
    )
    row = cur.fetchone()
    return None if row is None else row[0]


def season_game_names(cur: Any, season: int) -> set[str]:
    cur.execute(
        "SELECT home_team FROM games WHERE season = %s "
        "UNION SELECT away_team FROM games WHERE season = %s",
        (season, season),
    )
    return {str(r[0]) for r in cur.fetchall()}


def run_db_gates(
    cur: Any, built: BuiltPayload, artifacts: Artifacts, season: int
) -> list[GateResult]:
    results: list[GateResult] = []
    selected = selected_rating_source(cur, season)
    results.append(
        GateResult(
            "rating manifest is the site's selected source",
            selected == artifacts.rating_sha256,
            f"selected={str(selected)[:12]} manifest={artifacts.rating_sha256[:12]}",
        )
    )
    comps = built.payload.frames["team_rating_components"]
    ids = sorted(set(comps["v5_snapshot_id"].dropna()))
    cur.execute(
        "SELECT snapshot_id, offense_rating, offense_variance, defense_rating, "
        "defense_variance FROM v5_rating_snapshots WHERE snapshot_id = ANY(%s)",
        (ids,),
    )
    snapshots = {r[0]: r[1:] for r in cur.fetchall()}
    missing = [i for i in ids if i not in snapshots]
    results.append(
        GateResult(
            "every component's v5 snapshot is projected",
            not missing,
            f"{len(missing)} missing, e.g. {missing[:2]}",
        )
    )
    bad = []
    for r in comps.itertuples(index=False):
        snap = snapshots.get(r.v5_snapshot_id)
        if snap is None:
            continue
        mean, variance = (
            (snap[0], snap[1]) if r.unit_role == "offense" else (snap[2], snap[3])
        )
        if (
            abs(mean - r.rating_mean) > 1e-12
            or abs(variance - r.rating_variance) > 1e-12
        ):
            bad.append(r.component_id)
    results.append(
        GateResult(
            "component rating/variance equal v5_rating_snapshots",
            not bad,
            "; ".join(bad[:5]),
        )
    )
    # 6. games agree with the Silver-based team stats where those exist
    stats = built.payload.frames["team_possession_stats"]
    cur.execute(
        "SELECT as_of_week, team, MAX(games) FROM team_season_stats "
        "WHERE season = %s GROUP BY 1, 2",
        (season,),
    )
    silver = {(int(w), t): int(g) for w, t, g in cur.fetchall()}
    totals = stats[stats["metric"].eq("epa_per_play") & stats["role"].eq("offense")]
    bad = [
        f"{r.as_of_week} {r.team}: v5 {r.games + r.games_excluded} vs silver {silver[(r.as_of_week, r.team)]}"
        for r in totals.itertuples(index=False)
        if (r.as_of_week, r.team) in silver
        and r.games + r.games_excluded != silver[(r.as_of_week, r.team)]
    ]
    results.append(
        GateResult(
            "per-team games equal team_season_stats.games",
            not bad,
            "; ".join(bad[:5])
            + ("" if silver else " (no Silver-based rows to compare)"),
        )
    )
    return results


def missing_tables(cur: Any) -> list[str]:
    """Matchup tables not yet migrated (0021) in the target database."""
    missing = []
    for table in sorted(md.TABLES) + ["matchup_data_publications"]:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
        if not cur.fetchone()[0]:
            missing.append(table)
    return missing


def stale_keys(cur: Any, built: BuiltPayload, season: int) -> dict[str, list[tuple]]:
    """Database keys in the publish scope that the new payload no longer has."""
    frames = built.payload.frames
    weeks = sorted(built.as_of_cutoffs)
    scopes = {
        "team_game_measurements": (
            "SELECT game_id, team, unit_role, measurement_id FROM team_game_measurements WHERE season = %s",
            (season,),
            ("game_id", "team", "unit_role", "measurement_id"),
        ),
        "team_possession_stats": (
            "SELECT as_of_week, team, role, metric FROM team_possession_stats "
            "WHERE season = %s AND as_of_week = ANY(%s)",
            (season, weeks),
            ("as_of_week", "team", "role", "metric"),
        ),
        "team_possession_adjusted": (
            "SELECT as_of_week, team, role, measurement_id FROM team_possession_adjusted "
            "WHERE season = %s AND as_of_week = ANY(%s)",
            (season, weeks),
            ("as_of_week", "team", "role", "measurement_id"),
        ),
    }
    stale: dict[str, list[tuple]] = {}
    for table, (query, params, key_columns) in scopes.items():
        cur.execute(query, params)
        existing = {tuple(r) for r in cur.fetchall()}
        frame = frames[table]
        new = {
            tuple(int(v) if isinstance(v, (np.integer,)) else v for v in row)
            for row in frame[list(key_columns)].itertuples(index=False, name=None)
        }
        extra = sorted(existing - new, key=str)
        if extra:
            stale[table] = extra
    return stale


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        if a is None or b is None:
            return a is b
        return abs(float(a) - float(b)) <= 1e-12 * max(1.0, abs(float(a)))
    return a == b


def check_component_conflicts(cur: Any, components: pd.DataFrame) -> list[str]:
    """Existing component rows must equal what this payload would insert."""
    ids = components["component_id"].tolist()
    cur.execute(
        "SELECT component_id, rating_mean, rating_variance, usable_exposure, "
        "evidence::text, excluded_observations::text FROM team_rating_components "
        "WHERE component_id = ANY(%s)",
        (ids,),
    )
    existing = {r[0]: r[1:] for r in cur.fetchall()}
    conflicts = []
    for r in components.itertuples(index=False):
        row = existing.get(r.component_id)
        if row is None:
            continue
        if not (
            _same(row[0], r.rating_mean)
            and _same(row[1], r.rating_variance)
            and _same(row[2], r.usable_exposure)
            and json.loads(row[3])
            == json.loads(json.dumps(r.evidence, default=md._json_default))
            and json.loads(row[4])
            == json.loads(json.dumps(r.excluded_observations, default=md._json_default))
        ):
            conflicts.append(r.component_id)
    return conflicts


def write_payload(
    cur: Any,
    built: BuiltPayload,
    artifacts: Artifacts,
    *,
    season: int,
    environment: str,
    code_sha: str | None,
    payload_sha: str,
    log_game_ids: set[int] | None = None,
) -> dict[str, int]:
    """Upsert every table and the receipt in the caller's transaction.

    When ``log_game_ids`` is given, the per-game log write is restricted to
    those games; the gates always evaluate the full payload. This lets a
    later-week publication add its own games' log rows without overwriting the
    provenance of rows an earlier lineage published (table keys are
    lineage-unaware, so an unrestricted upsert would restamp them).
    """
    counts: dict[str, int] = {}
    records = built.payload.records()
    if log_game_ids is not None:
        log = built.payload.frames["team_game_measurements"]
        scoped = log[log["game_id"].astype(int).isin(log_game_ids)].reset_index(
            drop=True
        )
        records = dict(records)
        records["team_game_measurements"] = md.to_records(
            "team_game_measurements", scoped
        )
    for table in (
        "team_game_measurements",
        "team_possession_stats",
        "team_possession_adjusted",
        "team_rating_components",
    ):
        rows = records[table]
        if rows:
            cur.executemany(md.upsert_sql(table), rows)
        counts[table] = len(rows)
    publication_id = f"{season}:{artifacts.lineage}:{artifacts.rating_sha256[:12]}:{payload_sha[:12]}"
    cur.execute(
        "INSERT INTO matchup_data_publications (publication_id, season, lineage, "
        "rating_manifest_sha256, rating_manifest_uri, measurement_manifest_sha256, "
        "measurement_manifest_uri, observations_records_sha, as_of_weeks, rating_scale, "
        "row_counts, payload_sha256, code_sha, environment) VALUES "
        "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s) "
        "ON CONFLICT (publication_id) DO NOTHING",
        (
            publication_id,
            season,
            artifacts.lineage,
            artifacts.rating_sha256,
            artifacts.rating_uri,
            artifacts.measurement_sha256,
            artifacts.measurement_uri,
            artifacts.observations_records_sha,
            built.weeks,
            json.dumps(built.payload.rating_scale, sort_keys=True),
            json.dumps(counts, sort_keys=True),
            payload_sha,
            code_sha,
            environment,
        ),
    )
    return counts


def _equal(actual: Any, want: Any) -> bool:
    if actual is None or want is None:
        return actual is None and want is None
    if hasattr(want, "isoformat"):
        return pd.Timestamp(actual).tz_convert("UTC") == pd.Timestamp(want).tz_convert(
            "UTC"
        )
    if isinstance(want, bool):
        return bool(actual) == want
    if isinstance(want, (int, float)):
        return _same(float(actual), float(want))
    return str(actual) == str(want)


def compare_db_to_payload(cur: Any, built: BuiltPayload, season: int) -> list[str]:
    """Read-only: every payload row must exist in Neon with equal values."""
    mismatches: list[str] = []
    for table, (columns, keys, jsonb) in md.TABLES.items():
        frame = built.payload.frames[table]
        select = ", ".join(f"{c}::text" if c in jsonb else c for c in columns)
        if table == "team_rating_components":
            where, param = "component_id = ANY(%s)", frame["component_id"].tolist()
        else:
            where, param = "season = %s", season
        cur.execute(f"SELECT {select} FROM {table} WHERE {where}", (param,))
        db_rows = {
            tuple(str(r[columns.index(k)]) for k in keys): r for r in cur.fetchall()
        }
        for record in md.to_records(table, frame):
            key = tuple(str(record[k]) for k in keys)
            row = db_rows.get(key)
            if row is None:
                mismatches.append(f"{table}: missing {key}")
                continue
            for column, actual in zip(columns, row, strict=True):
                want = record[column]
                same = (
                    json.loads(actual) == json.loads(want)
                    if column in jsonb
                    else _equal(actual, want)
                )
                if not same:
                    mismatches.append(f"{table}: {column} differs {key}")
                    break
    return mismatches


def bridge_verifier_uri(rating_manifest_uri: str) -> str:
    """Canonical R2 location of a bridge verifier for its rating manifest."""
    return f"{rating_manifest_uri.rsplit('/', 1)[0]}/verification/bridge-verifier-manifest.json"


def build_bridge_verifier_manifest(
    artifacts: Artifacts,
    built: BuiltPayload,
    payload_sha: str,
    static_gates: list[GateResult],
    db_gates: list[GateResult],
    code_sha: str | None,
) -> dict[str, Any]:
    """Signed gate-receipt for a 6A-bridged matchup payload.

    Records every input hash plus the rebuilt payload hash and both gate
    outcomes. All gates must have passed; anything failing refuses here so an
    unsigned or partial attestation can never be written.
    """
    failed = [g.name for g in static_gates + db_gates if not g.ok]
    if failed:
        raise PublishError(f"bridge verifier refused: gates failed: {failed}")
    refs = artifacts.rating_manifest["output_refs"]
    manifest = {
        "schema_version": BRIDGE_VERIFIER_SCHEMA,
        "state": "verified",
        "rating_manifest_uri": artifacts.rating_uri,
        "rating_manifest_raw_sha256": artifacts.rating_sha256,
        "six_a_run_id": artifacts.observations_version_id.removeprefix("6a:"),
        "six_a_root_raw_sha256": artifacts.measurement_sha256,
        "six_a_root_uri": artifacts.measurement_uri,
        "observations_bytes_sha256": artifacts.observations_records_sha,
        "priors_raw_sha256": refs["priors"]["raw_sha256"],
        "pregame_roles_raw_sha256": refs["pregame_roles"]["raw_sha256"],
        "current_roles_raw_sha256": refs["current_roles"]["raw_sha256"],
        "as_of_weeks": built.weeks,
        "row_counts": built.payload.row_counts(),
        "payload_sha256": payload_sha,
        "static_gates": [asdict(g) for g in static_gates],
        "db_gates": [asdict(g) for g in db_gates],
        "code_sha": code_sha,
    }
    return sign_bridge_verifier(manifest)


def sign_bridge_verifier(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Sign a bridge verifier manifest with the repository payload scheme."""
    from cks_picks_cfb.data.data_first_phase2d import signed_payload

    return signed_payload(dict(manifest))


def assert_bridge_verifier(
    storage: Any,
    verifier_uri: str,
    rating_sha256: str,
    root_sha256: str,
    payload_sha: str,
) -> dict[str, Any]:
    """The publisher's pre-write check: a signed bridge verifier attesting this
    exact rating root, 6A root and rebuilt payload must exist."""
    try:
        raw = storage.read_bytes(verifier_uri)
    except Exception as exc:  # noqa: BLE001
        raise PublishError(f"bridge verifier missing at {verifier_uri}: {exc}")
    verifier = json.loads(raw)
    try:
        verify_signed_payload(verifier, label="bridge verifier")
    except Exception as exc:  # noqa: BLE001
        raise PublishError(f"bridge verifier is not signed: {exc}")
    if (
        verifier.get("schema_version") != BRIDGE_VERIFIER_SCHEMA
        or verifier.get("state") != "verified"
    ):
        raise PublishError("bridge verifier is not a verified attestation")
    if verifier.get("rating_manifest_raw_sha256") != rating_sha256:
        raise PublishError("bridge verifier attests a different rating manifest")
    if verifier.get("six_a_root_raw_sha256") != root_sha256:
        raise PublishError("bridge verifier attests a different 6A root")
    if verifier.get("payload_sha256") != payload_sha:
        raise PublishError(
            "bridge verifier payload differs from this build; rebuild it"
        )
    return verifier


def parse_weeks(spec: str | None) -> list[int] | None:
    """``None`` (all), ``"5"``, ``"1-5"`` or ``"0,2,4-5"``."""
    if not spec:
        return None
    weeks: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = (int(x) for x in part.split("-", 1))
            if lo > hi:
                raise PublishError(f"bad week range: {part}")
            weeks.update(range(lo, hi + 1))
        elif part:
            weeks.add(int(part))
    return sorted(weeks)


def prepare_run(
    storage: Any,
    cur: Any,
    *,
    season: int,
    lineage: str,
    rating_manifest_uri: str,
    measurement_manifest_uri: str | None,
    weeks: list[int] | None,
    alias_map: Mapping[str, str],
    six_a_run_id: str | None = None,
    six_a_root_sha256: str | None = None,
) -> tuple[Artifacts, BuiltPayload, set[str], str]:
    """Load verified artifacts, build every table, return the payload hash."""
    if lineage != "intended_update":
        raise PublishError(f"lineage {lineage!r} is not implemented yet")
    bridged = six_a_run_id is not None or six_a_root_sha256 is not None
    if bridged and (not six_a_run_id or not six_a_root_sha256):
        raise PublishError("6A run id and root sha256 are required together")
    if bridged:
        artifacts = load_6a_bridged_artifacts(
            storage,
            rating_manifest_uri,
            six_a_run_id or "",
            six_a_root_sha256 or "",
            season,
        )
    else:
        if not measurement_manifest_uri:
            raise PublishError("a measurement manifest URI is required")
        artifacts = load_intended_update_artifacts(
            storage, rating_manifest_uri, measurement_manifest_uri, season
        )
    game_names = season_game_names(cur, season)
    if not game_names:
        raise PublishError(f"no {season} games in the target database")
    built = build_payload(
        artifacts,
        season=season,
        game_names=game_names,
        alias_map=alias_map,
        weeks=weeks,
    )
    return artifacts, built, game_names, md.payload_sha256(built.payload.records())
