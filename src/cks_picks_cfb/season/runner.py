"""Local immutable preparation checkpoints; cloud readers never publish data.

``output/status.json`` reports the latest attempt (running, failed or passed);
``output/last-passed.json`` keeps the pointer to the last PASSED run manifest and
is never overwritten by a failed attempt. Content (manifest, verification report,
payload) never depends on the environment.
"""

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
from cks_picks_cfb.season.projection import build_projections
from cks_picks_cfb.season.verification import (
    VerificationError,
    assemble_report,
    derive_prepare_checks,
    failed_checks,
    lineage_identities,
    run_id_for,
)

ENVIRONMENTS = (None, "preview", "production")


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(canonical(value))
    os.replace(temporary, path)


def verify_outputs(manifest: dict) -> None:
    for name, ref in manifest["output_refs"].items():
        if sha(Path(ref["uri"]).read_bytes()) != ref["sha256"]:
            raise ValueError(f"prepared output checksum changed: {name}")


def _verified_manifest(pointer: dict) -> dict:
    """The run manifest a passed pointer names, with every checksum re-verified."""
    manifest_raw = Path(pointer["manifest_uri"]).read_bytes()
    if sha(manifest_raw) != pointer["manifest_sha256"]:
        raise ValueError("prepared manifest checksum changed")
    manifest = json.loads(manifest_raw)
    verify_outputs(manifest)
    if (
        sha(Path(manifest["verification_uri"]).read_bytes())
        != manifest["verification_sha256"]
    ):
        raise ValueError("verification checksum changed")
    return manifest


def _last_passed(output: Path) -> dict | None:
    """Last passed pointer; a legacy passed ``status.json`` counts as one."""
    for name in ("last-passed.json", "status.json"):
        path = output / name
        if path.exists():
            record = json.loads(path.read_bytes())
            if record.get("state") == "passed":
                return record
    return None


def status(output: Path) -> dict:
    path = output / "status.json"
    if not path.exists():
        return {"state": "not_started"}
    record = json.loads(path.read_bytes())
    if record["state"] == "passed":
        _verified_manifest(record)
        return record
    last = _last_passed(output)
    if last is not None:
        _verified_manifest(last)
        record["last_passed"] = last
    return record


def _passed(output: Path, run_id: str, manifest_path: Path, resumed: bool) -> None:
    record = {
        "state": "passed",
        "release_id": run_id,
        "manifest_uri": str(manifest_path),
        "manifest_sha256": sha(manifest_path.read_bytes()),
        "resumed": resumed,
    }
    _atomic_json(output / "last-passed.json", record)
    _atomic_json(output / "status.json", record)


def _write_ref(directory: Path, name: str, raw: bytes, rows: int) -> dict:
    path = directory / name
    path.write_bytes(raw)
    return _ref(directory, path, rows)


def _ref(directory: Path, path: Path, rows: int) -> dict:
    """Local ``uri`` (read by status/staging) plus an environment-free logical one."""
    return {
        "uri": str(path),
        "logical_uri": f"season-run:{directory.name}/{path.name}",
        "sha256": sha(path.read_bytes()),
        "rows": rows,
    }


def _reread(refs: dict) -> list[str]:
    """Names of outputs whose bytes, read back from disk, match their sha256."""
    return sorted(
        name
        for name, ref in refs.items()
        if sha(Path(ref["uri"]).read_bytes()) == ref["sha256"]
    )


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
    environment: str | None = None,
) -> dict[str, Any]:
    """Prepare and verify one run; raise (status ``failed``) unless every check passes.

    ``environment`` is validated only: it never enters the run identity, manifest,
    verification report or payload, so Preview and Production prepare identical bytes.
    """
    if environment not in ENVIRONMENTS:
        raise ValueError("environment must be preview or production")
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
    run_id = run_id_for(identity)
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".prepare.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError(
                "another preparation owns this output directory"
            ) from error
        last = _last_passed(output)
        previous = None
        if last is not None:
            # Preserve a legacy passed status.json before this attempt overwrites it.
            _atomic_json(output / "last-passed.json", last)
            prior_raw = Path(last["manifest_uri"]).read_bytes()
            if sha(prior_raw) != last["manifest_sha256"]:
                raise ValueError("prior preparation manifest changed")
            previous = json.loads(prior_raw)

        def fail(error: Exception, **detail: Any) -> None:
            # status.json reports this attempt; last-passed.json is left intact.
            _atomic_json(
                output / "status.json",
                {
                    "state": "failed",
                    "release_id": run_id,
                    "error_category": type(error).__name__,
                    **detail,
                },
            )

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
            fail(error)
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
            _passed(output, run_id, manifest_path, resumed=True)
            return manifest
        _atomic_json(
            output / "status.json",
            {"state": "running", "release_id": run_id, "identity": identity},
        )
        failed: list[str] = []
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
                refs[name] = _ref(directory, path, len(frame))
            for name, raw_input in (
                ("model_manifest", model_raw),
                ("revision_manifest", revision_raw),
            ):
                file_name = name.replace("_", "-") + ".json"
                refs[name] = _write_ref(directory, file_name, raw_input, 1)
            correction = _correction_report(
                previous, frames, revision, identity["revision_manifest_sha256"]
            )
            refs["correction_report"] = _write_ref(
                directory, "correction-report.json", canonical(correction), 1
            )
            payload = build_projections(
                frames,
                inputs,
                revision,
                {"identity": identity, "output_refs": refs},
            )
            # The payload is bound into output_refs BEFORE verification is computed.
            refs["serving_projections"] = _write_ref(
                directory,
                "serving-projections.json",
                canonical(payload),
                sum(map(len, payload.values())),
            )
            context = {"identity": identity, "output_refs": refs}
            report = assemble_report(
                payload,
                context,
                derive_prepare_checks(
                    frames,
                    inputs=inputs,
                    model=model,
                    identity=identity,
                    output_refs=refs,
                    verified_outputs=_reread(refs),
                ),
            )
            failed_report = directory / "verification-failed.json"
            if report["state"] != "passed":
                failed = failed_checks(report)
                _atomic_json(failed_report, report)
                raise VerificationError(
                    "season verification failed: " + ", ".join(failed)
                )
            failed_report.unlink(missing_ok=True)
            verification_path = directory / "verification.json"
            _atomic_json(verification_path, report)
            manifest = {
                "schema_version": "season_run_v1",
                "release_id": run_id,
                **identity,
                "identity": identity,
                "identities": lineage_identities(identity, refs),
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
            _passed(output, run_id, manifest_path, resumed=False)
            return manifest
        except Exception as error:
            fail(error, failed_checks=failed)
            raise
