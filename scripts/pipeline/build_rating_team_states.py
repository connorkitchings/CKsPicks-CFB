#!/usr/bin/env python3
"""Build isolated Phase 2 team states from corrected Phase 1 refs in Preview."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import register_dataset_version
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
    require_dataset,
)
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.state_audit import build_team_state_audit
from cks_picks_cfb.ratings.state_contracts import (
    MEASUREMENT_STATE_DATASET,
    TEAM_STATE_DATASET,
    load_team_state_config,
    validate_measurement_state_frame,
    validate_team_state_frame,
)
from cks_picks_cfb.ratings.states import build_team_states

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "conf/ratings/team_state_baseline_v1.yaml"
RELEVANT = (
    "src/cks_picks_cfb/ratings",
    "src/cks_picks_cfb/data/schema_contracts.py",
    "scripts/pipeline/build_rating_team_states.py",
    "conf/ratings/team_state_baseline_v1.yaml",
)


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _require_commit(expected: str | None, *, config_path: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    sha = expected or result.stdout.strip()
    if not sha:
        raise ValueError("Team-state artifacts require a Git commit SHA")
    relevant = (*RELEVANT[:-1], config_path)
    for path in relevant:
        if subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        ).returncode:
            raise ValueError(f"Team-state artifact path is not committed: {path}")
    if subprocess.run(
        ["git", "diff", "--quiet", sha, "--", *relevant], cwd=REPO_ROOT, check=False
    ).returncode:
        raise ValueError("Team-state artifact paths differ from the recorded commit")
    return sha


def _verify_v2_phase1_pins(
    config,
    phase1: dict,
    refs: tuple[DatasetRef, ...],
    report_uri: str,
    report_bytes: bytes,
) -> None:
    if not config.is_v2:
        return
    pins = config.raw_config["phase1"]
    if (
        report_uri != pins["report_uri"]
        or hashlib.sha256(report_bytes).hexdigest() != pins["report_sha256"]
    ):
        raise ValueError("Phase 2 v2 Phase 1 audit pin mismatch")
    labels = ("observations", "snapshots", "terminal_snapshots")
    for label, ref in zip(labels, refs, strict=True):
        expected = pins[label]
        if (
            ref.version_id != expected["version_id"]
            or ref.content_sha != expected["content_sha"]
            or ref.schema_version != expected["schema_version"]
        ):
            raise ValueError(f"Phase 2 v2 Phase 1 {label} pin mismatch")
    lineage = phase1.get("lineage", {})
    for label, ref in zip(labels, refs, strict=True):
        expected = lineage[
            "terminal_snapshots_ref"
            if label == "terminal_snapshots"
            else f"{label}_ref"
        ]
        if (
            expected.get("version_id") != ref.version_id
            or expected.get("content_sha") != ref.content_sha
        ):
            raise ValueError(f"Phase 2 v2 audit lineage mismatch for {label}")


def _write_immutable(storage, uri: str, data: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != data:
            raise FileExistsError(f"Immutable artifact exists: {uri}")
        return
    storage.write_bytes(data, uri)


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=["preview", "production"], required=True
    )
    parser.add_argument("--state-config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--observations-ref-uri", required=True)
    parser.add_argument("--snapshots-ref-uri", required=True)
    parser.add_argument("--terminal-snapshots-ref-uri", required=True)
    parser.add_argument("--phase1-report-uri", required=True)
    parser.add_argument("--measurement-states-ref-uri", required=True)
    parser.add_argument("--team-states-ref-uri", required=True)
    parser.add_argument("--report-uri", required=True)
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--register-catalog", action="store_true")
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError(
            "Rating team-state research builds are permitted only in preview"
        )
    config = load_team_state_config(args.state_config)
    prefix = f"{config.research_prefix}/{config.design_id}/"
    if any(
        not uri.startswith(prefix)
        for uri in (
            args.measurement_states_ref_uri,
            args.team_states_ref_uri,
            args.report_uri,
        )
    ):
        raise ValueError("Team-state outputs must live under the state research prefix")
    storage = get_storage(environment="preview")
    phase1_bytes = storage.read_bytes(args.phase1_report_uri)
    phase1 = json.loads(phase1_bytes.decode())
    if (
        not phase1.get("all_checks_passed")
        or phase1.get("report_schema_version") != "rating_measurement_audit_v2"
    ):
        raise ValueError("Phase 2 requires a passing Phase 1 v2 audit")
    observations_ref, snapshots_ref, terminal_ref = (
        _ref(storage, args.observations_ref_uri),
        _ref(storage, args.snapshots_ref_uri),
        _ref(storage, args.terminal_snapshots_ref_uri),
    )
    _verify_v2_phase1_pins(
        config,
        phase1,
        (observations_ref, snapshots_ref, terminal_ref),
        args.phase1_report_uri,
        phase1_bytes,
    )
    require_dataset(observations_ref, "rating_measurement_observations")
    require_dataset(snapshots_ref, "rating_adjusted_measurement_snapshots")
    require_dataset(terminal_ref, "rating_adjusted_measurement_terminal_snapshots")
    expected_refs = phase1.get("lineage", {})
    for key, actual in (
        ("observations_ref", observations_ref),
        ("snapshots_ref", snapshots_ref),
        ("terminal_snapshots_ref", terminal_ref),
    ):
        expected = expected_refs.get(key, {})
        if (
            expected.get("version_id") != actual.version_id
            or expected.get("content_sha") != actual.content_sha
        ):
            raise ValueError(f"Phase 1 audit ref mismatch for {key}")
    code_sha = _require_commit(
        args.expected_code_sha,
        config_path=str(Path(args.state_config).resolve().relative_to(REPO_ROOT)),
    )
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )
    pregame_snapshots = read_dataset(storage, snapshots_ref)
    measurement_states, team_states, audit_seed = build_team_states(
        pregame_snapshots=pregame_snapshots,
        terminal_snapshots=read_dataset(storage, terminal_ref),
        config=config,
        code_sha=code_sha,
        config_sha=config.design_id,
        parent_measurement_refs=";".join(
            (
                observations_ref.content_sha,
                snapshots_ref.content_sha,
                terminal_ref.content_sha,
            )
        ),
    )
    validate_measurement_state_frame(measurement_states, config)
    validate_team_state_frame(team_states, config)
    preliminary = build_team_state_audit(
        measurement_states=measurement_states,
        team_states=team_states,
        measurement_refs={
            "phase1_report_uri": args.phase1_report_uri,
            "observations_ref": asdict(observations_ref),
            "snapshots_ref": asdict(snapshots_ref),
            "terminal_ref": asdict(terminal_ref),
        },
        state_design_id=config.design_id,
        config=config,
        pregame_snapshots=pregame_snapshots,
    )
    preliminary.update(audit_seed)
    if not preliminary["all_checks_passed"]:
        _write_immutable(
            storage,
            args.report_uri,
            json.dumps(preliminary, indent=2, sort_keys=True, default=str).encode(),
        )
        raise ValueError("Phase 2 audit failed; only diagnostic report was published")
    measurement_ref, measurement_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=MEASUREMENT_STATE_DATASET,
            parent_refs=(observations_ref, snapshots_ref, terminal_ref),
            code_sha=code_sha,
            config_sha=config.design_id,
            as_of=cutoff,
            schema_version=config.measurement_state_schema_version,
            tier="gold",
        ),
        records=measurement_states.to_dict("records"),
        partitions={"seasons": audit_seed["seasons"]},
        validation={
            "nonempty": not measurement_states.empty,
            "state_contract_valid": True,
        },
    )
    team_ref, team_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=TEAM_STATE_DATASET,
            parent_refs=(measurement_ref,),
            code_sha=code_sha,
            config_sha=config.design_id,
            as_of=cutoff,
            schema_version=config.team_state_schema_version,
            tier="gold",
        ),
        records=team_states.to_dict("records"),
        partitions={"seasons": audit_seed["seasons"]},
        validation={"nonempty": not team_states.empty, "state_contract_valid": True},
    )
    report = build_team_state_audit(
        measurement_states=measurement_states,
        team_states=team_states,
        measurement_refs={
            "phase1_report_uri": args.phase1_report_uri,
            "observations_ref": asdict(observations_ref),
            "snapshots_ref": asdict(snapshots_ref),
            "terminal_ref": asdict(terminal_ref),
            "measurement_state_ref": asdict(measurement_ref),
            "team_state_ref": asdict(team_ref),
        },
        state_design_id=config.design_id,
        config=config,
        pregame_snapshots=pregame_snapshots,
    )
    report.update(audit_seed)
    payload = json.dumps(report, indent=2, sort_keys=True, default=str).encode()
    _write_immutable(storage, args.report_uri, payload)
    if not report["all_checks_passed"]:
        raise ValueError(
            "Phase 2 audit failed; successful artifact refs were not published"
        )
    _write_immutable(
        storage,
        args.measurement_states_ref_uri,
        json.dumps(asdict(measurement_ref), sort_keys=True).encode(),
    )
    _write_immutable(
        storage,
        args.team_states_ref_uri,
        json.dumps(asdict(team_ref), sort_keys=True).encode(),
    )
    if args.register_catalog:
        conn_url = resolve_runtime_target("preview").database_url
        register_dataset_version(conn_url, measurement_ref, measurement_manifest)
        register_dataset_version(conn_url, team_ref, team_manifest)
    print(
        json.dumps(
            {
                "status": "built",
                "measurement_states_ref": asdict(measurement_ref),
                "team_states_ref": asdict(team_ref),
                "report_sha256": hashlib.sha256(payload).hexdigest(),
            },
            sort_keys=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
