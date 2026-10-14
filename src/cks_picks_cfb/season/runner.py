"""Local immutable preparation checkpoints; cloud readers never publish data."""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.season.inputs import Reader, load_inputs
from cks_picks_cfb.season.manifest import (
    GRADING_POLICY,
    WORKFLOW_VERSION,
    canonical,
    sha,
    utc,
    validate_model,
    validate_revision,
)
from cks_picks_cfb.season.prepare import compute


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(canonical(value))
    os.replace(temporary, path)


def verify_outputs(manifest: dict) -> None:
    for name, ref in manifest["output_refs"].items():
        if sha(Path(ref["uri"]).read_bytes()) != ref["sha256"]:
            raise ValueError(f"prepared output checksum changed: {name}")


def status(output: Path) -> dict:
    path = output / "status.json"
    if not path.exists():
        return {"state": "not_started"}
    record = json.loads(path.read_bytes())
    if record["state"] == "passed":
        manifest_raw = Path(record["manifest_uri"]).read_bytes()
        if sha(manifest_raw) != record["manifest_sha256"]:
            raise ValueError("prepared manifest checksum changed")
        manifest = json.loads(manifest_raw)
        verify_outputs(manifest)
        if (
            sha(Path(manifest["verification_uri"]).read_bytes())
            != manifest["verification_sha256"]
        ):
            raise ValueError("verification checksum changed")
    return record


def _correction_report(
    previous: dict | None, frames: dict, revision: dict, revision_sha: str
) -> dict:
    changes = {}
    if previous:
        verify_outputs(previous)
        for name, keys, values in (
            (
                "predictions",
                ["season", "week", "game_id", "target"],
                ["mean", "variance"],
            ),
            (
                "grades",
                ["season", "week", "game_id", "target"],
                ["point", "side", "result", "benchmark_type"],
            ),
            ("ratings", ["target_week", "team"], ["offense_rating", "defense_rating"]),
        ):
            old = pd.read_parquet(previous["output_refs"][name]["uri"])
            combined = old[keys + values].merge(
                frames[name][keys + values],
                on=keys,
                how="outer",
                suffixes=("_before", "_after"),
                indicator=True,
                validate="one_to_one",
            )
            changed = pd.Series(False, index=combined.index)
            for column in values:
                left, right = combined[column + "_before"], combined[column + "_after"]
                changed |= ~(left.eq(right) | (left.isna() & right.isna()))
            changes[name] = {
                "added": int(combined._merge.eq("right_only").sum()),
                "removed": int(combined._merge.eq("left_only").sum()),
                "changed": int((combined._merge.eq("both") & changed).sum()),
            }
    return {
        "schema_version": "season_correction_report_v1",
        "captured_at": revision["captured_at"],
        "previous_revision_sha256": previous["revision_manifest_sha256"]
        if previous
        else None,
        "revision_manifest_sha256": revision_sha,
        "source_revision_changed": bool(
            previous and previous["revision_manifest_sha256"] != revision_sha
        ),
        "declared_provider_corrections": revision.get("corrections", []),
        "output_changes": changes,
    }


def prepare(
    *,
    model_raw: bytes,
    revision_raw: bytes,
    reader: Reader,
    through_week: int,
    next_week: int | None,
    as_of: str,
    output: Path,
    code_sha: str,
    config: dict | None = None,
    reconstruct_next_week: bool = False,
) -> dict[str, Any]:
    model, revision = json.loads(model_raw), json.loads(revision_raw)
    validate_model(model)
    validate_revision(revision)
    if utc(as_of) > pd.Timestamp.now(tz="UTC"):
        raise ValueError("preparation as-of cannot be in the future")
    if len(code_sha) != 40 or any(c not in "0123456789abcdef" for c in code_sha):
        raise ValueError("preparation requires exact committed code identity")
    config = dict(config or {})
    forbidden = Path(__file__).resolve().parents[3] / "data"
    output = output.resolve()
    if output == forbidden or output.is_relative_to(forbidden):
        raise ValueError("output cannot be repository ./data")
    identity = {
        "model_manifest_sha256": sha(model_raw),
        "revision_manifest_sha256": sha(revision_raw),
        "workflow_version": WORKFLOW_VERSION,
        "grading_policy_sha256": sha(canonical(GRADING_POLICY)),
        "code_sha": code_sha,
        "config_sha": sha(canonical(config)),
        "season": 2026,
        "through_week": through_week,
        "active_week": next_week if next_week is not None else through_week,
        "as_of": as_of,
        "next_week_mode": "reconstructed" if reconstruct_next_week else "live",
    }
    run_id = "season-2026-" + sha(canonical(identity))[:24]
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".prepare.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError(
                "another preparation owns this output directory"
            ) from error
        previous = None
        prior_status_path = output / "status.json"
        if prior_status_path.exists():
            prior_status = json.loads(prior_status_path.read_bytes())
            if prior_status.get("state") == "passed":
                prior_raw = Path(prior_status["manifest_uri"]).read_bytes()
                if sha(prior_raw) != prior_status["manifest_sha256"]:
                    raise ValueError("prior preparation manifest changed")
                previous = json.loads(prior_raw)
        # Re-read and check all source bytes even on a warm retry. No stale cached parent evidence.
        try:
            inputs = load_inputs(
                reader,
                model,
                revision,
                through_week,
                cache_dir=output / "measurement-cache",
                code_sha=code_sha,
            )
        except Exception as error:
            _atomic_json(
                output / "status.json",
                {
                    "state": "failed",
                    "release_id": run_id,
                    "error_category": type(error).__name__,
                },
            )
            raise
        directory = output / run_id
        directory.mkdir(exist_ok=True)
        manifest_path = directory / "run-manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_bytes())
            if manifest["identity"] != identity:
                raise ValueError("checkpoint identity conflict")
            verify_outputs(manifest)
            if (
                sha(Path(manifest["verification_uri"]).read_bytes())
                != manifest["verification_sha256"]
            ):
                raise ValueError("cached verification changed")
            _atomic_json(
                output / "status.json",
                {
                    "state": "passed",
                    "release_id": run_id,
                    "manifest_uri": str(manifest_path),
                    "manifest_sha256": sha(manifest_path.read_bytes()),
                    "resumed": True,
                },
            )
            return manifest
        _atomic_json(
            output / "status.json",
            {"state": "running", "release_id": run_id, "identity": identity},
        )
        try:
            frames = compute(
                inputs,
                revision,
                through_week=through_week,
                next_week=next_week,
                as_of=as_of,
                run_id=run_id,
                model_sha=identity["model_manifest_sha256"],
                revision_sha=identity["revision_manifest_sha256"],
                reconstruct_next_week=reconstruct_next_week,
            )
            refs = {}
            for name, frame in frames.items():
                path = directory / f"{name}.parquet"
                frame.to_parquet(path, index=False)
                refs[name] = {
                    "uri": str(path),
                    "sha256": sha(path.read_bytes()),
                    "rows": len(frame),
                }
            for name, raw_input in (
                ("model_manifest", model_raw),
                ("revision_manifest", revision_raw),
            ):
                path = directory / (name.replace("_", "-") + ".json")
                path.write_bytes(raw_input)
                refs[name] = {"uri": str(path), "sha256": sha(raw_input), "rows": 1}
            correction_path = directory / "correction-report.json"
            _atomic_json(
                correction_path,
                _correction_report(
                    previous, frames, revision, identity["revision_manifest_sha256"]
                ),
            )
            refs["correction_report"] = {
                "uri": str(correction_path),
                "sha256": sha(correction_path.read_bytes()),
                "rows": 1,
            }
            report = {
                "schema_version": "season_verification_v1",
                "state": "passed",
                "identity": identity,
                "checks": {
                    "required_prior_week_data": True,
                    "score_reconciliation": True,
                    "earlier_week_only": True,
                    "fixed_model_no_refit": True,
                    "paired_predictions": True,
                    "checksums_at_read": True,
                },
                "output_refs": refs,
                "historical_games": int(frames["schedule"].week.le(through_week).sum()),
                "graded_targets": int(frames["grades"].result.notna().sum()),
                "ungraded_targets": int(frames["grades"].result.isna().sum()),
            }
            verification_path = directory / "verification.json"
            _atomic_json(verification_path, report)
            manifest = {
                "schema_version": "season_run_v1",
                "release_id": run_id,
                **identity,
                "identity": identity,
                "state": "prepared",
                "model_manifest_ref": refs["model_manifest"],
                "revision_manifest_ref": refs["revision_manifest"],
                "captured_at": revision["captured_at"],
                "evidence_class": "reconstructed",
                "grading_policy": GRADING_POLICY,
                "verification_uri": str(verification_path),
                "verification_sha256": sha(verification_path.read_bytes()),
                "output_refs": refs,
            }
            _atomic_json(manifest_path, manifest)
            _atomic_json(
                output / "status.json",
                {
                    "state": "passed",
                    "release_id": run_id,
                    "manifest_uri": str(manifest_path),
                    "manifest_sha256": sha(manifest_path.read_bytes()),
                    "resumed": False,
                },
            )
            return manifest
        except Exception as error:
            _atomic_json(
                output / "status.json",
                {
                    "state": "failed",
                    "release_id": run_id,
                    "error_category": type(error).__name__,
                },
            )
            raise
