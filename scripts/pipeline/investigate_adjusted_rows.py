#!/usr/bin/env python3
"""Read-only investigation of a pinned Task 4 adjusted-row comparison.

Requires a fresh evidence directory. No rebuild harness, publication or database
mutation is called. A failed investigation retains snapshots and a failure receipt.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import psycopg
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cks_picks_cfb.audit import adjusted_rows as audit  # noqa: E402
from cks_picks_cfb.data import matchup_data as md  # noqa: E402
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload  # noqa: E402
from cks_picks_cfb.data.lake import (  # noqa: E402
    PartitionedDatasetRef,
    iter_partitioned_dataset,
)
from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.ops.v5_release import assert_v5_database_environment  # noqa: E402
from cks_picks_cfb.rebuild.published import open_pinned_run  # noqa: E402
from contracts.teams import TEAM_LOGO_MAP  # noqa: E402

TABLE = "team_possession_adjusted"
HISTORICAL = ROOT / "docs/plans/2026-10-10/adjusted-row-investigation/historical"
SAVED = ROOT / "docs/plans/2026-10-07/stage1-evidence"


class Evidence:
    def __init__(self, path):
        audit.fresh_output(path)
        self.path = path
        self.inputs = {}

    def write(self, name, raw):
        target = self.path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)

    def json(self, name, value):
        self.write(name, audit.canonical(value))

    def frame(self, name, frame):
        self.write(name, frame.to_csv(index=False).encode())

    def local(self, path, expected=None):
        raw = path.read_bytes()
        digest = audit.sha(raw)
        if expected and digest != expected:
            raise ValueError(f"pinned local input changed: {path.name}")
        self.inputs[str(path.relative_to(ROOT))] = digest
        return raw


class ReadTrace:
    """Expose only immutable byte reads; retain every read object and its identity."""

    def __init__(self, storage, evidence):
        self.storage, self.evidence = storage, evidence
        self.cache = {}

    def read_bytes(self, uri):
        if uri not in self.cache:
            raw = self.storage.read_bytes(uri)
            digest = audit.sha(raw)
            self.evidence.inputs[uri] = digest
            path = f"r2/{digest}.bin"
            if not (self.evidence.path / path).exists():
                self.evidence.write(path, raw)
            self.cache[uri] = raw
        return self.cache[uri]


def capture(environment, evidence):
    name = "PREVIEW_DATABASE_URL" if environment == "preview" else "DATABASE_URL"
    url = os.environ.get(name)
    if not url:
        raise ValueError(f"restricted {name} unavailable")
    with psycopg.connect(url, connect_timeout=15) as conn:
        audit.configure_readonly(conn)
        with conn.cursor() as cur:
            assert_v5_database_environment(cur, environment)
            cur.execute(
                "SELECT session_user, current_user, current_database(), "
                "current_setting('transaction_read_only'), "
                "current_setting('transaction_isolation'), transaction_timestamp()"
            )
            identity = cur.fetchone()
            if identity[3:5] != ("on", "repeatable read"):
                raise ValueError("read-only repeatable-read transaction unavailable")
            columns = list(md.ADJUSTED_COLUMNS) + ["updated_at"]
            cur.execute(
                "SELECT "
                + ", ".join(columns)
                + " FROM team_possession_adjusted WHERE season = %s "
                "ORDER BY season, as_of_week, team, role, measurement_id",
                (2026,),
            )
            rows = pd.DataFrame(cur.fetchall(), columns=columns)
            cur.execute(
                "SELECT * FROM matchup_data_publications WHERE season = %s ORDER BY publication_id",
                (2026,),
            )
            publications = [
                dict(zip([c.name for c in cur.description], r, strict=True))
                for r in cur.fetchall()
            ]
            cur.execute(
                "SELECT home_team FROM games WHERE season = %s UNION "
                "SELECT away_team FROM games WHERE season = %s",
                (2026, 2026),
            )
            names = sorted(str(r[0]) for r in cur.fetchall())
            snapshot = {
                "environment": environment,
                "identity": identity,
                "game_names": names,
                "rows": audit.clean(rows.to_dict("records")),
                "publications": publications,
            }
            # Explicitly roll back even this read-only transaction.
            conn.rollback()
    audit.index_rows(rows)
    snapshot["rows_sha256"] = audit.sha(audit.canonical(snapshot["rows"]))
    evidence.json("snapshot.json", snapshot)
    evidence.frame("snapshot.csv", rows)
    return snapshot, rows


def historical(environment, evidence):
    meta = json.loads(
        evidence.local(SAVED / f"matchup-previous-{environment}-meta.json")
    )
    folder = HISTORICAL / environment
    captured = json.loads(evidence.local(folder / "capture-metadata.json"))
    if captured["tables"] != meta["tables"] or captured["environment"] != environment:
        raise ValueError("historical capture metadata does not match saved comparison")
    frames = {}
    for table in (TABLE, "team_game_measurements"):
        raw = evidence.local(
            folder / f"{table}.parquet", meta["tables"][table]["sha256"]
        )
        frames[table] = pd.read_parquet(io.BytesIO(raw))
        if len(frames[table]) != meta["tables"][table]["rows"]:
            raise ValueError("historical snapshot row count differs")
    audit.index_rows(frames[TABLE])
    return captured, frames


def adjusted(prepared, cutoffs, names, rating_sha, measurement_sha):
    return md.build_possession_adjusted(
        prepared,
        season=2026,
        as_of_cutoffs=cutoffs,
        fbs_names=names,
        rating_manifest_sha256=rating_sha,
        measurement_manifest_sha256=measurement_sha,
    )


def run(args, evidence, receipt):
    if os.environ.get("CFB_STORAGE_BACKEND") != "r2":
        raise ValueError("CFB_STORAGE_BACKEND must explicitly be r2")
    plan = yaml.safe_load(evidence.local(args.comparison_plan.resolve()))
    pins = {p["name"]: p for p in plan["inputs"]}
    for pin in plan["inputs"]:
        if pin["kind"] == "git_file":
            evidence.local(ROOT / pin["uri"], pin["sha256"])
    config = get_storage(environment="preview")
    # R2Storage retains bucket and client, not account_id; settings bind identity.
    from cks_picks_cfb.data.storage.base import StorageSettings

    settings = StorageSettings.from_env(environment="preview")
    identity = f"r2:{settings.account_id}:{settings.bucket}"
    if identity != plan["storage_identity"]:
        raise ValueError("Preview R2 identity differs from pinned comparison plan")
    receipt["storage_identity"] = identity
    storage = ReadTrace(config, evidence)
    snapshot, current = capture(args.environment, evidence)
    old_meta, old = historical(args.environment, evidence)
    lock = json.loads(
        evidence.local(
            ROOT / pins["source_lock_2026"]["uri"], pins["source_lock_2026"]["sha256"]
        )
    )
    root_pin = pins["root_manifest"]
    run = open_pinned_run(
        storage, plan["policies"]["published_run_id"], root_pin["sha256"]
    )
    observation = run.frame("states_2026/observations.parquet")
    names = set(old_meta["game_names"])
    all_names = set(observation.team) | set(observation.opponent)
    mapping = audit.verified_names(all_names, names, TEAM_LOGO_MAP)
    prepared = md.prepare_observations(observation, mapping)
    cutoffs = {
        int(w) + 1: pd.Timestamp(c) for w, c in lock["post_week_cutoffs"].items()
    }
    candidate = adjusted(
        prepared,
        cutoffs,
        names,
        run.root["manifest_sha256"],
        run.root["manifest_sha256"],
    )
    evidence.frame("candidate.csv", candidate)
    evidence.json("name-map.json", mapping)
    evidence.frame("corrected-observations.csv", prepared)
    corrected_population = run.frame("states_2026/population.parquet")
    corrected_games = audit.validate_population(prepared, corrected_population)
    evidence.frame("corrected-population.csv", corrected_population)
    comparison = audit.compare(old[TABLE], candidate)
    extras = comparison["only_left"]
    historical_weeks = sorted(int(w) for w in old[TABLE].as_of_week.unique())
    historical_candidate = candidate.loc[candidate.as_of_week.isin(historical_weeks)]
    # Hash-check the signed Task 4 report and compare its exact scope/population.
    task_key = f"rebuild/6a/{plan['run_id']}/root-manifest.json"
    task_raw = storage.read_bytes(task_key)
    task = open_pinned_run(storage, plan["run_id"], audit.sha(task_raw))
    report_raw = task.read(task.run_key("published_comparison/report.json"))
    saved_report = evidence.local(SAVED / "matchup-diff.r2.json")
    if (
        json.loads(report_raw)["tables"][TABLE]
        != json.loads(saved_report)["tables"][TABLE]
    ):
        raise ValueError(
            "saved adjusted comparison differs from immutable Task 4 report"
        )
    report = json.loads(report_raw)["tables"][TABLE]
    if (
        len(candidate) != report["rows_built"]
        or len(extras) != report["population"]["only_published"]
    ):
        raise ValueError("reconstructed historical comparison population differs")
    historical_diff = audit.compare(old[TABLE], historical_candidate)
    if historical_diff["only_right"]:
        raise ValueError("unexpected historical candidate-only keys")
    evidence.json("historical-comparison.json", comparison)
    evidence.frame(
        "historical-field-differences.csv", pd.DataFrame(comparison["differences"])
    )
    # Original observation manifest bound by the saved rows and the pinned source lock.
    original_hashes = set(old[TABLE].measurement_manifest_sha256)
    if len(original_hashes) != 1:
        raise ValueError(
            "multiple original observation parents require explicit tracing"
        )
    parent = next(
        p
        for p in lock["certified_weekly_rating_parents"]
        if p["measurement_manifest_sha256"] in original_hashes
    )
    raw = storage.read_bytes(parent["measurement_manifest_uri"])
    if audit.sha(raw) != parent["measurement_manifest_sha256"]:
        raise ValueError("original measurement manifest changed")
    manifest = json.loads(raw)
    verify_signed_payload(manifest, label="original observation manifest")
    ref_data = dict(manifest["output_refs"]["observations"])
    ref_data["partition_keys"] = tuple(ref_data["partition_keys"])
    legacy = pd.concat(
        iter_partitioned_dataset(storage, PartitionedDatasetRef(**ref_data)),
        ignore_index=True,
    )
    legacy = legacy.loc[legacy.season.eq(2026)]
    legacy_map = audit.verified_names(
        set(legacy.team) | set(legacy.opponent), names, TEAM_LOGO_MAP
    )
    legacy_prepared = md.prepare_observations(legacy, legacy_map)
    population_ref = dict(manifest["output_refs"]["population"])
    population_ref["partition_keys"] = tuple(population_ref["partition_keys"])
    legacy_population = pd.concat(
        iter_partitioned_dataset(storage, PartitionedDatasetRef(**population_ref)),
        ignore_index=True,
    )
    legacy_games = audit.validate_population(legacy_prepared, legacy_population)
    evidence.frame("legacy-population.csv", legacy_population)
    evidence.frame("legacy-observations.csv", legacy_prepared)
    legacy_built = audit.index_rows(
        adjusted(
            legacy_prepared,
            {w: cutoffs[w] for w in historical_weeks},
            names,
            old[TABLE].rating_manifest_sha256.iloc[0],
            next(iter(original_hashes)),
        )
    )
    explanations = [
        audit.explain_extra(row, prepared, legacy_prepared, legacy_built, cutoffs)
        for row in extras
    ]
    old_index, current_index = audit.index_rows(old[TABLE]), audit.index_rows(current)
    populations = {}
    for week in historical_weeks:
        populations[week] = {}
        for label, frame in [("corrected", prepared), ("legacy", legacy_prepared)]:
            window = audit.eligible(frame, week, cutoffs[week])
            window = window.loc[
                window.measurement_id.isin(md.ADJUSTED_MEASUREMENTS)
                & window.observed
                & window.denominator.gt(0)
            ]
            populations[week][label] = {
                "rows": len(window),
                "sha256": audit.sha(audit.canonical(window.to_dict("records"))),
            }
    evidence.json("adjustment-populations.json", populations)
    for explanation in explanations:
        explanation["adjustment_population"] = populations[explanation["as_of_week"]]
        explanation["source_game_population"] = {
            label: [games[(2026, g)] for g in explanation["source_game_ids"]]
            for label, games in [
                ("corrected", corrected_games),
                ("legacy", legacy_games),
            ]
        }
        key = tuple(explanation[k] for k in audit.KEY)
        now = current_index.get(key)
        explanation["current_disposition"] = (
            "absent"
            if now is None
            else (
                "unchanged"
                if all(
                    audit.same(f, old_index[key][f], now[f])
                    for f in md.ADJUSTED_COLUMNS
                )
                else "changed"
            )
        )
        explanation["current_row"] = now
    evidence.json("source-explanations.json", explanations)
    evidence.frame(
        "historical-extras.csv",
        pd.DataFrame(
            [
                {
                    k: v
                    for k, v in e.items()
                    if k
                    not in {
                        "corrected_observations",
                        "legacy_observations",
                        "current_row",
                        "legacy_adjusted_row",
                        "legacy_reconstructed_row",
                        "source_game_population",
                        "adjustment_population",
                    }
                }
                for e in explanations
            ]
        ),
    )
    current_historical = current.loc[current.as_of_week.isin(historical_weeks)]
    drift = audit.compare(old[TABLE], current_historical)
    evidence.json("historical-current-drift.json", drift)
    later = current.loc[~current.as_of_week.isin(historical_weeks)]
    later_candidate = candidate.loc[~candidate.as_of_week.isin(historical_weeks)]
    later_diff = audit.compare(later_candidate, later)
    evidence.json("later-context-comparison.json", later_diff)
    # Retain/verify referenced manifests, distinguishing raw-byte vs signed canonical identity.
    references = []
    for pub in snapshot["publications"]:
        for kind in ("rating", "measurement"):
            uri, expected = pub[f"{kind}_manifest_uri"], pub[f"{kind}_manifest_sha256"]
            blob = storage.read_bytes(uri)
            obj = json.loads(blob)
            verify_signed_payload(obj, label=f"publication {kind} manifest")
            if expected not in {audit.sha(blob), obj.get("manifest_sha256")}:
                raise ValueError("publication lineage reference hash mismatch")
            references.append(
                {
                    "publication_id": pub["publication_id"],
                    "kind": kind,
                    "uri": uri,
                    "declared_sha256": expected,
                    "raw_sha256": audit.sha(blob),
                }
            )
    evidence.json("publication-lineage.json", references)
    later_unexplained = [
        d for d in later_diff["differences"] if d["kind"] != "provenance"
    ]
    later_dispositions = []
    for row in later.to_dict("records"):
        matching = [
            p
            for p in snapshot["publications"]
            if p["environment"] == args.environment
            and row["as_of_week"] in p["as_of_weeks"]
            and row["rating_manifest_sha256"] == p["rating_manifest_sha256"]
            and row["measurement_manifest_sha256"] == p["measurement_manifest_sha256"]
        ]
        if not matching:
            later_unexplained.append(
                {
                    "reason": "later row lacks matching publication",
                    **{k: row[k] for k in audit.KEY},
                }
            )
        later_dispositions.append(
            {
                **{k: row[k] for k in audit.KEY},
                "disposition": "explained_later_state_change"
                if matching
                else "unresolved",
                "publication_ids": [p["publication_id"] for p in matching],
                "reason": "Later scope; population and values compared to pinned candidate; manifest identities bound by verified publication.",
            }
        )
    evidence.frame("later-dispositions.csv", pd.DataFrame(later_dispositions))
    evidence.frame(
        "later-field-differences.csv", pd.DataFrame(later_diff["differences"])
    )
    peer_diff = None
    if args.peer_output:
        peer = json.loads((args.peer_output / "snapshot.json").read_bytes())
        peer_receipt = json.loads((args.peer_output / "receipt.json").read_bytes())
        peer_digest = peer_receipt.pop("receipt_sha256")
        if (
            peer_digest != audit.sha(audit.canonical(peer_receipt))
            or peer_receipt["status"] != "passed"
        ):
            raise ValueError("peer receipt invalid or investigation incomplete")
        if (
            audit.sha((args.peer_output / "snapshot.json").read_bytes())
            != peer_receipt["outputs"]["snapshot.json"]
        ):
            raise ValueError("peer snapshot receipt mismatch")
        if peer["environment"] == args.environment:
            raise ValueError("peer must be the other environment")
        evidence.inputs["peer_snapshot"] = audit.sha(
            (args.peer_output / "snapshot.json").read_bytes()
        )
        peer_diff = audit.compare(pd.DataFrame(peer["rows"]), current)
        evidence.json("environment-drift.json", peer_diff)
    unresolved = sum(e["classification"] == "unresolved" for e in explanations)
    problems = []
    if unresolved:
        problems.append(f"{unresolved} unresolved historical extras")
    if drift["only_left"] or drift["only_right"] or drift["differences"]:
        problems.append("historical current-state drift requires disposition")
    if later_diff["only_left"] or later_diff["only_right"] or later_unexplained:
        problems.append("unexplained later-state drift")
    if peer_diff and (
        peer_diff["only_left"] or peer_diff["only_right"] or peer_diff["differences"]
    ):
        problems.append("unexplained environment drift")
    receipt.update(
        {
            "historical_weeks": historical_weeks,
            "cutoffs": cutoffs,
            "original_extra_keys": [{k: e[k] for k in audit.KEY} for e in explanations],
            "historical_extra_count": len(extras),
            "unresolved_count": unresolved,
            "current_count": len(current),
            "later_count": len(later),
            "historical_current_drift": drift,
            "peer_compared": bool(args.peer_output),
            "problems": problems,
            "status": "passed" if not problems else "blocked",
            "remediation_authorized": False,
        }
    )
    return 1 if problems else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--comparison-plan", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--peer-output",
        type=Path,
        help="Other environment evidence directory for exact drift comparison",
    )
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env", override=False)
    evidence = Evidence(args.output_dir)
    receipt = {
        "kind": "adjusted_rows_investigation_v1",
        "environment": args.environment,
        "started_at": datetime.now(UTC),
        "status": "blocked",
        "problems": [],
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    }
    try:
        code = run(args, evidence, receipt)
    except Exception as exc:
        # Connection errors may contain credentials; retain only safe failure identity.
        receipt["problems"].append(
            {
                "type": type(exc).__name__,
                "message": str(exc)
                if isinstance(exc, ValueError)
                else "Input/read verification failed; partial evidence retained.",
            }
        )
        code = 1
    receipt["finished_at"] = datetime.now(UTC)
    receipt["inputs"] = evidence.inputs
    receipt["code"] = {
        str(p.relative_to(ROOT)): audit.sha(p.read_bytes())
        for p in [
            Path(__file__).resolve(),
            ROOT / "src/cks_picks_cfb/audit/adjusted_rows.py",
            ROOT / "src/cks_picks_cfb/data/matchup_data.py",
            ROOT / "src/cks_picks_cfb/ratings/possession_measurements.py",
            ROOT / "src/cks_picks_cfb/data/lake.py",
            ROOT / "src/cks_picks_cfb/rebuild/published.py",
            ROOT / "contracts/teams.py",
        ]
    }
    receipt["outputs"] = {
        str(p.relative_to(evidence.path)): audit.sha(p.read_bytes())
        for p in sorted(evidence.path.rglob("*"))
        if p.is_file()
    }
    receipt["receipt_sha256"] = audit.sha(audit.canonical(receipt))
    evidence.json("receipt.json", receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "problems": receipt["problems"],
                "output": str(evidence.path),
            }
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
