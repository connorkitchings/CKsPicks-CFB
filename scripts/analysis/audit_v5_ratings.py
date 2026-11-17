#!/usr/bin/env python3
"""Read-only evidence collection for the 2026 V5 ratings audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.rows import dict_row

from cks_picks_cfb.data.storage import ReadOnlyStorage, get_storage
from cks_picks_cfb.preseason_features import canonical_team
from cks_picks_cfb.ratings.possession_measurements import build_measurements
from cks_picks_cfb.season.inputs import frame, score_reconciliation_problems
from cks_picks_cfb.season.manifest import sha, validate_model, validate_revision

ROOT = Path(__file__).resolve().parents[2]
TABLES = (
    "games",
    "predictions",
    "v5_rating_snapshots",
    "team_possession_stats",
    "team_game_measurements",
    "matchup_data_publications",
    "team_possession_adjusted",
    "team_rating_components",
    "site_week_selections",
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-manifest", type=Path, required=True)
    parser.add_argument("--revision-manifest", type=Path, required=True)
    parser.add_argument("--score-exceptions-git-ref", required=True)
    parser.add_argument("--run-manifest", type=Path, action="append", default=[])
    parser.add_argument("--environment", choices=["production"], required=True)
    parser.add_argument("--last-pregame-week", type=int, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.last_pregame_week != 9:
        parser.error("this historical audit requires --last-pregame-week 9")
    outputs = {args.report.resolve(), args.evidence.resolve()}
    if len(outputs) != 2:
        parser.error("report and evidence paths must differ")
    if outputs & {
        path.resolve()
        for path in [args.model_manifest, args.revision_manifest, *args.run_manifest]
    }:
        parser.error("report and evidence cannot overwrite input manifests")
    return args


def require_environment():
    names = (
        "CFB_R2_BUCKET",
        "CFB_R2_ACCOUNT_ID",
        "CFB_R2_ACCESS_KEY",
        "CFB_R2_SECRET_KEY",
        "DATABASE_URL",
    )
    if os.environ.get("CFB_STORAGE_BACKEND") != "r2":
        raise ValueError("CFB_STORAGE_BACKEND must explicitly equal r2")
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise ValueError(
            "missing required environment variables: " + ", ".join(missing)
        )


def read_json(path):
    raw = path.read_bytes()
    return json.loads(raw), sha(raw)


def historical_exceptions(revision, ref):
    entry = revision["score_reconciliation_exceptions"]
    if not __import__("re").fullmatch(r"[0-9a-fA-F]{40}", ref):
        raise ValueError("score exception git ref must be a full commit hash")
    raw = subprocess.run(
        ["git", "show", f"{ref}:{entry['uri']}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ).stdout
    if sha(raw) != entry["sha256"]:
        raise ValueError("historical score exceptions checksum mismatch")
    values = json.loads(raw)
    from cks_picks_cfb.preseason_features import canonical_team

    result = {}
    for value in values:
        key = (int(value["game_id"]), canonical_team(value["team"]))
        if key in result or not value["reason"]:
            raise ValueError("invalid duplicate or empty score exception")
        result[key] = value["reason"]
    return result


def capture_database(model_sha, revision_sha):
    """Read the active pointer, baseline and scoped rows from one MVCC snapshot."""
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            active = conn.execute(
                "SELECT * FROM season_releases WHERE environment = %s AND season = %s AND status = %s",
                ("production", 2026, "active"),
            ).fetchall()
            baseline = conn.execute(
                "SELECT * FROM season_releases WHERE environment = %s AND season = %s AND model_manifest_sha256 = %s AND revision_manifest_sha256 = %s ORDER BY activated_at DESC NULLS LAST",
                ("production", 2026, model_sha, revision_sha),
            ).fetchall()
            if len(active) != 1:
                raise ValueError("expected exactly one active production release")
            # Multiple releases may reuse the same revision; preserve all matching records.
            releases = {row["release_id"]: row for row in [*baseline, *active]}
            for release in releases.values():
                release["tables"] = {}
                for table in TABLES:
                    release["tables"][table] = conn.execute(
                        f"SELECT * FROM season_release_{table} WHERE release_id = %s",
                        (release["release_id"],),
                    ).fetchall()
            for release in releases.values():
                release["selected_source"] = conn.execute(
                    "SELECT pr.rating_manifest_sha256 FROM season_release_site_week_selections s JOIN prediction_runs pr ON pr.run_id = s.run_id WHERE s.release_id = %s AND s.season = %s AND pr.evidence_class IN ('pending', 'replay', 'live') ORDER BY s.week DESC LIMIT 1",
                    (release["release_id"], 2026),
                ).fetchone()
            return {
                "active_id": active[0]["release_id"],
                "baseline_ids": [r["release_id"] for r in baseline],
                "releases": releases,
            }


def prepared_manifests(paths, snapshot):
    by_sha = {r["run_manifest_sha256"]: r for r in snapshot["releases"].values()}
    results = {}
    for path in paths:
        manifest, digest = read_json(path)
        release = by_sha.get(digest)
        if release is None:
            raise ValueError(
                "provided run manifest does not match a captured release checksum"
            )
        outputs = {}
        for name, ref in manifest.get("output_refs", {}).items():
            # Logical season-run URIs are identifiers, not object store keys.
            uri = ref.get("uri", "")
            artifact = Path(uri)
            if not artifact.is_absolute():
                artifact = path.parent / artifact
            if not artifact.is_file():
                artifact = path.parent / Path(uri).name
            if not artifact.is_file():
                outputs[name] = {"status": "unavailable", "sha256": ref.get("sha256")}
                continue
            raw = artifact.read_bytes()
            if sha(raw) != ref.get("sha256"):
                raise ValueError(f"prepared output checksum mismatch: {name}")
            outputs[name] = {
                "status": "verified",
                "sha256": ref["sha256"],
                "path": str(artifact),
            }
        results[release["release_id"]] = {"sha256": digest, "outputs": outputs}
    return results


def serving_comparisons(release, prepared):
    """Run the actual UI period helper over the captured, source-qualified rows."""
    tables = release["tables"]
    source_row = release.get("selected_source")
    source = source_row["rating_manifest_sha256"] if source_row else None
    snapshots = [
        row
        for row in tables["v5_rating_snapshots"]
        if row["source_manifest_sha256"] == source
    ]
    periods = sorted(
        {
            r["cutoff_utc"].isoformat()
            for r in snapshots
            if r["snapshot_class"] == "current"
        }
    )
    games = [r for r in tables["games"] if r["week"] <= 9]
    script = """import {periodBeforeKickoff} from './web/src/lib/rating-periods.ts';
let s=''; for await (const c of process.stdin) s+=c;
const x=JSON.parse(s), p=x.periods.map(t=>({id:t,cutoffUtc:new Date(t)}));
console.log(JSON.stringify(x.kickoffs.map(t=>periodBeforeKickoff(p,new Date(t))?.id ?? null)));"""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT,
        input=json.dumps(
            {
                "periods": periods,
                "kickoffs": [g["start_date"].isoformat() for g in games],
            }
        ),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    chosen = json.loads(proc.stdout)
    forecasts = {r["game_id"]: r for r in tables["predictions"]}
    selected = {
        (r["team"], r["cutoff_utc"].isoformat()): r
        for r in snapshots
        if r["snapshot_class"] == "current"
    }
    preseason = {
        r["team"]: r for r in snapshots if r["snapshot_id"].endswith(":preseason")
    }
    pregame = {
        (r["team"], r["week"]): r for r in snapshots if r["snapshot_class"] == "pregame"
    }
    feature_rows = {}
    features = (prepared or {}).get("outputs", {}).get("features", {})
    if features.get("status") == "verified":
        feature_frame = pd.read_parquet(features["path"])
        if feature_frame.duplicated("game_id").any():
            raise ValueError("duplicate original feature game")
        feature_rows = {
            int(row["game_id"]): row for row in feature_frame.to_dict("records")
        }
    rating_rows = {}
    original_ratings = (prepared or {}).get("outputs", {}).get("ratings", {})
    if original_ratings.get("status") == "verified":
        original_frame = pd.read_parquet(original_ratings["path"])
        if original_frame.duplicated(["target_week", "team"]).any():
            raise ValueError("duplicate original rating state")
        rating_rows = {
            (str(r["team"]), int(r["target_week"])): r
            for r in original_frame.to_dict("records")
        }
    rows = []
    for game, period in zip(games, chosen, strict=True):
        item = {
            "game_id": game["game_id"],
            "week": game["week"],
            "kickoff": game["start_date"],
            "forecast": game["game_id"] in forecasts,
            "period_cutoff": period,
            "source_sha256": source,
            "teams": {},
            "forecast_heads": {
                head: bool(
                    forecasts.get(game["game_id"], {}).get("predicted_" + head)
                    is not None
                )
                for head in ("spread", "total")
            },
        }
        for side in ("home", "away"):
            team = canonical_team(game[f"{side}_team"])
            current = selected.get((team, period)) if period else None
            served = current or preseason.get(team)
            original = pregame.get((team, game["week"]))
            fields = {}
            for role in ("offense", "defense"):
                name = role + "_rating"
                a = served[name] if served else None
                b = original[name] if original else None
                original_state = rating_rows.get((team, game["week"]))
                original_value = original_state[name] if original_state else None
                fields[name] = {
                    "original_pregame": original_value,
                    "original_vs_projection": b - original_value
                    if original_value is not None and b is not None
                    else None,
                    "served": a,
                    "projected_pregame": b,
                    "difference": a - b if a is not None and b is not None else None,
                }
            item["teams"][side] = {
                "team": team,
                "source": "current"
                if current
                else "preseason"
                if served
                else "unavailable",
                "fields": fields,
            }
        feature = feature_rows.get(game["game_id"])
        if feature is None:
            item["original_features"] = {
                "status": "unavailable",
                "reason": "Original prepared feature row unavailable",
            }
        else:
            comparisons = {}
            for side in ("home", "away"):
                for role in ("offense", "defense"):
                    name = f"{side}_{role}"
                    served = item["teams"][side]["fields"][role + "_rating"]["served"]
                    original_value = feature[name]
                    projected = item["teams"][side]["fields"][role + "_rating"][
                        "projected_pregame"
                    ]
                    comparisons[name] = {
                        "projected_pregame": projected,
                        "projected_difference": projected - original_value
                        if projected is not None
                        else None,
                        "original": original_value,
                        "served": served,
                        "difference": served - original_value
                        if served is not None
                        else None,
                    }
            status = (
                "agreement"
                if all(
                    x["difference"] is not None
                    and abs(x["difference"]) <= 1e-10
                    and x["projected_difference"] is not None
                    and abs(x["projected_difference"]) <= 1e-10
                    for x in comparisons.values()
                )
                else "discrepancy"
            )
            item["original_features"] = {
                "status": status,
                "sha256": features["sha256"],
                "forecast_heads_present": item["forecast_heads"],
                "fields": comparisons,
            }
        differences = [
            field["difference"]
            for side in item["teams"].values()
            for field in side["fields"].values()
        ]
        item["serving_vs_projected_pregame"] = (
            "unavailable"
            if any(x is None for x in differences)
            else "discrepancy"
            if any(abs(x) > 1e-10 for x in differences)
            else "agreement"
        )
        original_differences = [
            field["original_vs_projection"]
            for side in item["teams"].values()
            for field in side["fields"].values()
        ]
        item["original_ratings"] = {
            "status": "unavailable"
            if any(value is None for value in original_differences)
            else "discrepancy"
            if any(abs(value) > 1e-10 for value in original_differences)
            else "agreement",
            "sha256": original_ratings.get("sha256"),
        }
        rows.append(item)
    statuses = [
        status
        for row in rows
        if row["forecast"]
        for status in (
            row["serving_vs_projected_pregame"],
            row["original_features"]["status"],
            row["original_ratings"]["status"],
        )
    ]
    status = (
        "discrepancy"
        if "discrepancy" in statuses
        else "unavailable"
        if not source or "unavailable" in statuses
        else "agreement"
    )
    return {
        "status": status,
        "selected_source_sha256": source,
        "period_helper_sha256": sha(
            (ROOT / "web/src/lib/rating-periods.ts").read_bytes()
        ),
        "games": rows,
        "games_without_forecasts": [r["game_id"] for r in rows if not r["forecast"]],
    }


def clean_json(value):
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def json_default(value):
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"cannot serialize {type(value).__name__}")


def main(argv=None):
    args = parse_args(argv)
    require_environment()
    model, model_sha = read_json(args.model_manifest)
    revision, revision_sha = read_json(args.revision_manifest)
    validate_model(model)
    validate_revision(revision)
    exceptions = historical_exceptions(revision, args.score_exceptions_git_ref)
    store = ReadOnlyStorage(get_storage(environment="production"))
    snapshot = capture_database(model_sha, revision_sha)
    prepared = prepared_manifests(args.run_manifest, snapshot)
    outputs = {args.report.resolve(), args.evidence.resolve()}
    artifact_paths = {
        Path(info["path"]).resolve()
        for item in prepared.values()
        for info in item["outputs"].values()
        if "path" in info
    }
    if outputs & artifact_paths:
        raise ValueError("output cannot overwrite a prepared artifact")
    refs = revision["inputs"]
    schedule = frame(store, refs["schedule"])
    if "cancelled" in schedule:
        schedule = schedule[~schedule.cancelled.astype(bool)].copy()
    for column in ("home_team", "away_team"):
        schedule[column] = schedule[column].map(canonical_team)
    completed = schedule[schedule.week.le(8)].copy()
    ids = set(completed.game_id.astype(int))
    finals = frame(store, refs["finals"])
    finals = finals[finals.game_id.isin(ids)].copy()
    byplay = frame(store, refs["byplay"])
    byplay = byplay[byplay.game_id.isin(ids)].copy()
    reconciliation = frame(store, refs["reconciliation"])
    selected = reconciliation[reconciliation.game_id.isin(ids)]
    if (
        set(selected.game_id.astype(int)) != ids
        or selected.blocking.fillna(True).astype(bool).any()
    ):
        raise ValueError("source stream reconciliation is incomplete")
    population = completed.assign(
        forecast_eligible=True,
        schedule_completed=True,
        outcome_valid=True,
        measurement_usable=True,
    )
    measurement_result = build_measurements(
        byplay=byplay,
        population=population,
        outcomes=finals,
        scope="season_2026",
        play_identity=revision.get("play_identity", "byplay_v1"),
    )
    observations = measurement_result.observations
    for column in ("team", "opponent"):
        observations[column] = observations[column].map(canonical_team)
    events = measurement_result.scoring_events.copy()
    events["team"] = events["team"].map(canonical_team)
    score_problems = score_reconciliation_problems(
        completed, finals, events, exceptions
    )
    team_data = frame(store, refs["teams"])
    name_col = next(
        (name for name in ("team", "school") if name in team_data.columns), None
    )
    if not name_col or "classification" not in team_data.columns:
        raise ValueError("pinned teams lack FBS classification")
    fbs = set(
        team_data.loc[
            team_data.classification.astype(str).str.lower().eq("fbs"), name_col
        ].map(canonical_team)
    )
    if not fbs:
        raise ValueError("pinned teams contain no FBS members")
    priors = frame(store, model["inputs"]["priors"])
    terminal = frame(store, model["inputs"]["terminal"])
    from cks_picks_cfb.audit.v5_ratings import (
        audit_generation,
        audit_graph_sensitivity,
        audit_source_quarantine,
    )

    generation_results = {}
    baseline = (
        snapshot["releases"].get(snapshot["baseline_ids"][0])
        if snapshot["baseline_ids"]
        else None
    )

    def provenance(release):
        if not release:
            return None, None
        row = release.get("selected_source")
        rating = row.get("rating_manifest_sha256") if row else None
        hashes = {
            r["measurement_manifest_sha256"]
            for r in release["tables"]["matchup_data_publications"]
            if r["rating_manifest_sha256"] == rating
        }
        return rating, next(iter(hashes)) if len(hashes) == 1 else None

    baseline_rating_sha, baseline_measurement_sha = provenance(baseline)
    baseline_adjusted = (
        pd.DataFrame(baseline["tables"]["team_possession_adjusted"])
        if baseline
        else pd.DataFrame()
    )
    baseline_components = (
        pd.DataFrame(baseline["tables"]["team_rating_components"])
        if baseline
        else pd.DataFrame()
    )
    for kind, cutoffs in (
        ("pregame", revision["pre_week_cutoffs"]),
        ("post_week", revision["post_week_cutoffs"]),
    ):
        for key, cutoff in sorted(cutoffs.items(), key=lambda item: int(item[0])):
            week = int(key)
            if (kind == "pregame" and week > 9) or (kind == "post_week" and week > 8):
                continue
            components = None
            if not baseline_components.empty:
                snapshot_class = (
                    "preseason"
                    if kind == "pregame" and week == 0
                    else "pregame"
                    if kind == "pregame"
                    else "current"
                )
                as_of = week if kind == "pregame" else week + 1
                components = baseline_components[
                    (baseline_components.snapshot_class == snapshot_class)
                    & (baseline_components.as_of_week == as_of)
                ].copy()
                components["team"] = components["rating_team"]
            adjusted = None
            if kind == "post_week" and not baseline_adjusted.empty:
                adjusted = baseline_adjusted[
                    (baseline_adjusted.as_of_week == week + 1)
                    & (baseline_adjusted.measurement_id == "ppp")
                ].copy()
                adjusted["team"] = adjusted["team"].map(canonical_team)
            generation_results[f"{kind}_{week}"] = audit_generation(
                observations,
                priors,
                terminal,
                week=week if kind == "pregame" else week + 1,
                cutoff=pd.Timestamp(cutoff),
                components=components,
                adjusted=adjusted,
                expected_rating_source=baseline_rating_sha,
                expected_measurement_source=baseline_measurement_sha,
                fbs_teams=fbs,
            )
    for generation_name, result in generation_results.items():
        related = {"Georgia", "Florida"}
        for edge in result["edges"]:
            if edge["team"] in {"Georgia", "Florida"}:
                related.add(edge["opponent"])
        result["passes"] = [row for row in result["passes"] if row["team"] in related]
        result["edges"] = [row for row in result["edges"] if row["team"] in related]
        result["populations"] = [
            r for r in result["populations"] if r["team"] in {"Georgia", "Florida"}
        ]
        if generation_name != "pregame_9":
            result["passes"] = []
            result["edges"] = []
            result.pop("scale_cohorts", None)
        result["states"] = [
            row for row in result["states"] if row["team"] in {"Georgia", "Florida"}
        ]
    excluded = generation_results["pregame_9"]["exclusions"]
    excluded_ids = sorted({int(row["game_id"]) for row in excluded})

    def records(table):
        return json.loads(table.to_json(orient="records", date_format="iso"))

    score_ledger = []
    for game_id in excluded_ids:
        game = completed[completed.game_id.eq(game_id)]
        game_events = events[events.game_id.eq(game_id)]
        game_observations = observations[
            observations.game_id.eq(game_id) & observations.measurement_id.eq("ppp")
        ]
        score_ledger.append(
            {
                "game_id": game_id,
                "schedule": records(game),
                "finals": records(finals[finals.game_id.eq(game_id)]),
                "score_events": records(game_events),
                "possessions": records(
                    measurement_result.possessions[
                        measurement_result.possessions.game_id.eq(game_id)
                    ]
                ),
                "ppp_role_observations": records(game_observations),
                "source_reconciliation": records(
                    selected[selected.game_id.eq(game_id)]
                ),
                "exceptions": [
                    {"team": team, "reason": reason}
                    for (gid, team), reason in exceptions.items()
                    if gid == game_id
                ],
            }
        )
    quarantine_annotations = audit_source_quarantine(
        observations,
        events,
        finals.merge(
            completed[["game_id", "home_team", "away_team"]],
            on="game_id",
            validate="one_to_one",
        ),
        exceptions,
        through_week=8,
    )
    sensitivity = audit_graph_sensitivity(
        observations,
        priors,
        terminal,
        week=9,
        cutoff=pd.Timestamp(revision["pre_week_cutoffs"]["9"]),
        sec_teams={
            "Alabama",
            "Arkansas",
            "Auburn",
            "Florida",
            "Georgia",
            "Kentucky",
            "LSU",
            "Mississippi State",
            "Missouri",
            "Oklahoma",
            "Ole Miss",
            "South Carolina",
            "Tennessee",
            "Texas",
            "Texas A&M",
            "Vanderbilt",
        },
    )
    active_release = snapshot["releases"][snapshot["active_id"]]
    active_math = {
        "status": "unavailable",
        "reason": "Active model manifest differs from the pinned model",
    }
    if active_release["model_manifest_sha256"] == model_sha:
        active_observations = pd.DataFrame(
            active_release["tables"]["team_game_measurements"]
        )
        active_components = pd.DataFrame(
            active_release["tables"]["team_rating_components"]
        )
        active_adjusted = pd.DataFrame(
            active_release["tables"]["team_possession_adjusted"]
        )
        for col in ("team", "opponent"):
            active_observations[col] = active_observations[col].map(canonical_team)
        active_results = {}
        active_rating_sha, active_measurement_sha = provenance(active_release)
        for (kind, as_of, cutoff), group in active_components.groupby(
            ["snapshot_class", "as_of_week", "cutoff_utc"]
        ):
            if as_of > 9 or kind not in {"preseason", "pregame", "current"}:
                continue
            group = group.copy()
            group["team"] = group["rating_team"]
            adjusted = None
            if kind == "current":
                adjusted = active_adjusted[
                    (active_adjusted.as_of_week == as_of)
                    & (active_adjusted.measurement_id == "ppp")
                ].copy()
                adjusted["team"] = adjusted["team"].map(canonical_team)
            value = audit_generation(
                active_observations,
                priors,
                terminal,
                week=int(as_of),
                cutoff=cutoff,
                components=group,
                adjusted=adjusted,
                expected_rating_source=active_rating_sha,
                expected_measurement_source=active_measurement_sha,
                fbs_teams=fbs,
            )
            related = {"Georgia", "Florida"}
            for edge in value["edges"]:
                if edge["team"] in {"Georgia", "Florida"}:
                    related.add(edge["opponent"])
            value["passes"] = [r for r in value["passes"] if r["team"] in related]
            value["edges"] = [r for r in value["edges"] if r["team"] in related]
            value["populations"] = [
                r for r in value["populations"] if r["team"] in {"Georgia", "Florida"}
            ]
            if kind != "pregame" or as_of != 9:
                value["passes"] = []
                value["edges"] = []
            value.pop("scale_cohorts", None)
            value["states"] = [
                r for r in value["states"] if r["team"] in {"Georgia", "Florida"}
            ]
            active_results[f"{kind}_{as_of}_{pd.Timestamp(cutoff).isoformat()}"] = value
        active_math = {
            "status": "computed",
            "observations_source": "captured active release team_game_measurements projection",
            "generations": active_results,
        }
    active_source = {
        "status": "unavailable",
        "reason": "Matching active revision manifest not found in checkout",
    }
    active_revision_path = next(
        (
            path
            for path in (ROOT / "conf/season/2026").glob("revision_manifest*.json")
            if sha(path.read_bytes()) == active_release["revision_manifest_sha256"]
        ),
        None,
    )
    if active_revision_path:
        active_revision, _ = read_json(active_revision_path)
        validate_revision(active_revision)
        active_refs = active_revision["inputs"]
        active_schedule = frame(store, active_refs["schedule"])
        if "cancelled" in active_schedule:
            active_schedule = active_schedule[
                ~active_schedule.cancelled.astype(bool)
            ].copy()
        for col in ("home_team", "away_team"):
            active_schedule[col] = active_schedule[col].map(canonical_team)
        active_completed = active_schedule[active_schedule.week.le(8)].copy()
        active_ids = set(active_completed.game_id.astype(int))
        active_finals = frame(store, active_refs["finals"])
        active_finals = active_finals[active_finals.game_id.isin(active_ids)]
        active_byplay = frame(store, active_refs["byplay"])
        active_byplay = active_byplay[active_byplay.game_id.isin(active_ids)]
        active_population = active_completed.assign(
            forecast_eligible=True,
            schedule_completed=True,
            outcome_valid=True,
            measurement_usable=True,
        )
        active_measurement = build_measurements(
            byplay=active_byplay,
            population=active_population,
            outcomes=active_finals,
            scope="season_2026",
            play_identity=active_revision.get("play_identity", "byplay_v1"),
        )
        raw = active_measurement.observations
        raw = raw[raw.measurement_id.eq("ppp")].copy()
        for col in ("team", "opponent"):
            raw[col] = raw[col].map(canonical_team)
        projected = pd.DataFrame(active_release["tables"]["team_game_measurements"])
        projected = projected[
            projected.measurement_id.eq("ppp") & projected.week.le(8)
        ].copy()
        for col in ("team", "opponent"):
            projected[col] = projected[col].map(canonical_team)
        keys = ["game_id", "team", "unit_role"]
        joined = raw.merge(
            projected,
            on=keys,
            how="outer",
            suffixes=("_source", "_projection"),
            indicator=True,
        )
        differences = []
        for row in joined.to_dict("records"):
            key = {name: row[name] for name in keys}
            if row["_merge"] != "both":
                differences.append({**key, "reason": row["_merge"]})
                continue
            for col in (
                "opponent",
                "week",
                "coverage_status",
                "missing_reason",
                "numerator",
                "denominator",
                "raw_value",
            ):
                a, b = row[col + "_source"], row[col + "_projection"]
                if pd.isna(a) and pd.isna(b):
                    continue
                if (pd.isna(a) or pd.isna(b)) or (
                    abs(a - b) > 1e-10
                    if isinstance(a, (int, float)) and isinstance(b, (int, float))
                    else a != b
                ):
                    differences.append(
                        {**key, "field": col, "source": a, "projection": b}
                    )
        active_source = {
            "status": "discrepancy" if differences else "agreement",
            "revision_manifest_sha256": active_release["revision_manifest_sha256"],
            "rows": len(joined),
            "differences": differences,
            "scope": "Weeks 0-8 only; independent rebuild from active revision's checksum-verified byplay and finals",
        }
    population_comparisons = []
    if baseline:
        for week in range(1, 10):
            calculated = generation_results[f"post_week_{week - 1}"]["populations"]
            source = baseline["tables"]["team_possession_stats"]
            for item in calculated:
                if (
                    item["team"] not in {"Georgia", "Florida"}
                    or item["cohort"] != "fbs_vs_fbs"
                ):
                    continue
                matches = [
                    r
                    for r in source
                    if r["as_of_week"] == week
                    and r["metric"] == "ppp"
                    and canonical_team(r["team"]) == item["team"]
                    and r["role"] == item["role"]
                ]
                differences = {}
                if len(matches) == 1:
                    row = matches[0]
                    for expected, actual in (
                        ("points", "numerator"),
                        ("possessions", "denominator"),
                        ("ppp", "value"),
                        ("games", "games"),
                        ("rank", "rank"),
                        ("cohort_size", "cohort_size"),
                    ):
                        a, b = item[expected], row[actual]
                        if a is None or b is None or abs(a - b) > 1e-10:
                            differences[expected] = {"recomputed": a, "projection": b}
                population_comparisons.append(
                    {
                        "week": week,
                        "team": item["team"],
                        "role": item["role"],
                        "status": "unavailable"
                        if len(matches) != 1
                        else "discrepancy"
                        if differences
                        else "agreement",
                        "differences": differences,
                    }
                )
    checks = {
        "historical_inputs": {
            "status": "agreement" if not score_problems else "discrepancy",
            "score_reconciliation_problems": score_problems,
            "detail": "Pinned input bytes and historical exception digest verified; this does not certify provider source quality.",
        },
        "baseline_release": {
            "status": "agreement" if snapshot["baseline_ids"] else "unavailable",
            "count": len(snapshot["baseline_ids"]),
        },
        "original_artifacts": {
            "status": "unavailable",
            "detail": "Forecast features and original pregame states are compared only when their prepared artifact bytes are verified.",
        },
        "serving_lineage": {
            "status": "unavailable",
            "detail": "Source-qualified serving selections and original artifact comparisons are recorded per game.",
        },
        "source_certification": {
            "status": "unavailable",
            "detail": "Pinned source ledgers and score reconciliation are recorded for quarantined games. Provider source accuracy cannot be independently certified by the reconstruction itself.",
        },
    }
    release_scopes = {}
    for label, release_id in (
        ("baseline", snapshot["baseline_ids"][0] if snapshot["baseline_ids"] else None),
        ("active", snapshot["active_id"]),
    ):
        if release_id is None:
            release_scopes[label] = {"status": "unavailable"}
            continue
        release = snapshot["releases"][release_id]
        artifact = prepared.get(release_id)
        release_scopes[label] = {
            "model_manifest_sha256": release["model_manifest_sha256"],
            "revision_manifest_sha256": release["revision_manifest_sha256"],
            "run_manifest_sha256": release["run_manifest_sha256"],
            "code_sha": release["code_sha"],
            "prepared_artifacts": {
                name: {key: value for key, value in info.items() if key != "path"}
                for name, info in (artifact or {}).get("outputs", {}).items()
            },
            "serving": serving_comparisons(release, artifact),
        }

    def combine_status(statuses):
        return (
            "discrepancy"
            if "discrepancy" in statuses
            else "unavailable"
            if not statuses or "unavailable" in statuses
            else "agreement"
        )

    serving_statuses = [
        scope.get("serving", {}).get("status", "unavailable")
        for scope in release_scopes.values()
    ]
    feature_statuses = [
        game[key]["status"]
        for scope in release_scopes.values()
        for game in scope.get("serving", {}).get("games", [])
        if game["forecast"]
        for key in ("original_features", "original_ratings")
    ]
    checks["original_artifacts"]["status"] = (
        combine_status(feature_statuses)
        if len(feature_statuses)
        and all("serving" in scope for scope in release_scopes.values())
        else "unavailable"
    )
    checks["serving_lineage"]["status"] = combine_status(serving_statuses)
    overall = (
        "discrepancy"
        if any(value["status"] == "discrepancy" for value in checks.values())
        else "incomplete"
        if any(value["status"] == "unavailable" for value in checks.values())
        else "agreement"
    )
    evidence = {
        "status": overall,
        "input_hashes": {
            "model_manifest": model_sha,
            "revision_manifest": revision_sha,
            "score_exceptions": revision["score_reconciliation_exceptions"]["sha256"],
            "audit_script": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "audit_math_module": sha(
                (ROOT / "src/cks_picks_cfb/audit/v5_ratings.py").read_bytes()
            ),
        },
        "checks": checks,
        "score_exceptions": [
            {"game_id": g, "team": t, "reason": reason}
            for (g, t), reason in sorted(exceptions.items())
        ],
        "generations": generation_results,
        "graph_sensitivity": sensitivity,
        "fbs_membership_note": "FBS membership comes from the 2026 revision teams input; historical terminal composition reflects 2026 membership, not verified 2025 division membership.",
        "quarantine_source_ledgers": score_ledger,
        "quarantine_annotations": quarantine_annotations,
        "baseline_population_comparisons": population_comparisons,
        "active_math": active_math,
        "active_source_comparison": active_source,
        "release_scopes": release_scopes,
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    evidence_text = (
        json.dumps(
            clean_json(evidence),
            default=json_default,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    )
    lines = [
        "# V5 offense and defense ratings audit",
        "",
        f"Status: {overall}. Unavailable evidence is not verification.",
        "",
        "## Checks",
        "",
    ]
    for name, result in checks.items():
        lines.append(f"- **{name}**: {result['status']}. {result.get('detail', '')}")
    current = generation_results["pregame_9"]
    lines += [
        "",
        "## Georgia and Florida before Week 9",
        "",
        "The full usable population and the FBS-vs-FBS cohort are separately measured. Defensive ranks use lower points allowed per possession as better.",
        "",
    ]
    for role in ("offense", "defense"):
        lines += [f"### {role.title()}", ""]
        for team in ("Georgia", "Florida"):
            state = next(
                (
                    r
                    for r in current["states"]
                    if r["team"] == team and r["unit_role"] == role
                ),
                None,
            )
            populations = [
                r
                for r in current["populations"]
                if r["team"] == team and r["role"] == role
            ]
            if state:
                lines.append(
                    f"- **{team}**: rating {state['rating_mean']:.6f}; prior contribution {state['prior_contribution']:.6f}; usable exposure {state['usable_exposure']:.1f}; adjusted game-weight identity {state['adjusted_identity']['status']}."
                )
            for pop in populations:
                if pop["ppp"] is not None:
                    lines.append(
                        f"  - {pop['cohort']}: {pop['games']} games, {pop['points']:.0f} points, {pop['possessions']:.0f} possessions, PPP {pop['ppp']:.6f}, rank {pop['rank']} of {pop['cohort_size']}."
                    )
        lines.append("")
    lines += [
        "## Quarantine and source evidence",
        "",
        f"{len(excluded)} team-game-role observations are unusable across {len(excluded_ids)} games before Week 9. The JSON retains all four role observations, scoring events, possession ledgers, source reconciliation, and exception membership for each affected game. Graph-sensitivity scenarios are diagnostic and do not change the release.",
        "",
        "## Generations",
        "",
        f"Computed {len(generation_results)} historical pregame and post-week generations. Detailed role, pass and exclusion ledgers are in the JSON evidence.",
        "",
        "## Limitations",
        "",
        "The independently reconstructed arithmetic is not a source-data certification. Original prepared features and serving lineage need separate verification.",
        "",
    ]
    for path, content in (
        (args.evidence, evidence_text),
        (args.report, "\n".join(lines)),
    ):
        with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, encoding="utf-8", delete=False
        ) as output:
            temporary = Path(output.name)
            try:
                output.write(content)
                output.flush()
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        # Driver and SDK messages can contain connection URLs or credentials.
        print(
            f"Audit failed ({type(error).__name__}); check configuration and input integrity.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
