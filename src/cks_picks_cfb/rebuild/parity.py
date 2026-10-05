"""Legacy-allowed parity stages proving the new seams change nothing.

``measurements_parity``: the measurement path with the baseline ledger injected must
reproduce the served r9 observations and coverage. ``ratings_parity``: the pure selected
design on the served r9 measurement frames must reproduce the served r9cert states and
priors for ``ppp__rho_0_60__exposure``. Both read only retained, hash-pinned artifacts.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild import common
from cks_picks_cfb.rebuild.comparison import canonical_equal
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput

RECEIPT = "parity.json"
SELECTED_CANDIDATE = "ppp__rho_0_60__exposure"


def _ref(value: dict[str, Any]):
    from cks_picks_cfb.data.lake import PartitionedDatasetRef

    fields = (
        "artifact_kind",
        "dataset",
        "version_id",
        "schema_version",
        "content_sha",
        "records_sha",
        "uri",
        "row_count",
        "partition_keys",
    )
    ref = {name: value[name] for name in fields}
    ref["partition_keys"] = tuple(ref["partition_keys"])
    return PartitionedDatasetRef(**ref)


def partitioned_frame(storage, value: dict[str, Any], *, keep=None) -> pd.DataFrame:
    """Concatenate a retained partitioned dataset, optionally filtering each part."""
    from cks_picks_cfb.data.lake import iter_partitioned_dataset

    frames = []
    for frame in iter_partitioned_dataset(storage, _ref(value)):
        frames.append(frame if keep is None else frame[keep(frame)])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _legacy_population(context: StageContext, storage):
    from cks_picks_cfb.data.data_first_possession_v1 import build_population
    from cks_picks_cfb.data.lake import read_dataset
    from cks_picks_cfb.rebuild import legacy

    pins = {pin.name: pin for pin in context.plan.inputs}
    repair, _ = legacy._repair(
        storage, pins["repair_v2_manifest"].uri, scope="historical"
    )
    population = build_population(
        read_dataset(storage, legacy._ref(repair["output_refs"]["population"])),
        scope="historical",
    )
    return repair, population


def _receipt(context: StageContext, checks: dict[str, Any]) -> StageOutput:
    passed = all(
        v["equal"] if isinstance(v, dict) else bool(v) for v in checks.values()
    )
    body = {"checks": checks, "passed": passed}
    key = f"{context.plan.run_prefix()}{context.stage.name}/{RECEIPT}"

    def artifacts() -> Iterator[tuple[str, bytes]]:
        yield key, json.dumps(body, indent=2, sort_keys=True, default=str).encode()

    return StageOutput(artifacts=artifacts(), metrics={"passed": passed})


def build_measurements_parity(context: StageContext) -> StageOutput:
    from cks_picks_cfb.data.lake import read_dataset
    from cks_picks_cfb.ratings import possession_measurements as pm
    from cks_picks_cfb.rebuild import legacy

    storage = common.preview_storage(context)
    repair, population = _legacy_population(context, storage)
    refs = legacy._sources(storage, repair, scope="historical")
    byplay = legacy._concat_source_frames(
        [read_dataset(storage, refs[s]["byplay"]) for s in sorted(refs)]
    )
    outcomes = legacy._concat_source_frames(
        [read_dataset(storage, refs[s]["game_outcomes"]) for s in sorted(refs)]
    )
    served = json.loads(context.read_input("r9_measurement_manifest"))["output_refs"]
    possessions = partitioned_frame(storage, served["possessions"])
    scoring = partitioned_frame(storage, served["scoring_events"])
    result = pm.build_measurements(
        byplay=byplay,
        population=population,
        outcomes=outcomes,
        possessions=possessions,
        scoring_events=scoring,
    )
    checks: dict[str, Any] = {}
    for name, frame in (
        ("observations", result.observations),
        ("coverage", result.coverage),
    ):
        expected = partitioned_frame(storage, served[name])
        checks[name] = canonical_equal(frame[list(expected.columns)], expected)
    return _receipt(context, checks)


def build_ratings_parity(context: StageContext) -> StageOutput:
    from cks_picks_cfb.ratings.possession_selected_design import compute_selected_design

    storage = common.preview_storage(context)
    _, population = _legacy_population(context, storage)
    measured = json.loads(context.read_input("r9_measurement_manifest"))["output_refs"]
    served = json.loads(context.read_input("r9cert_rating_manifest"))["output_refs"]
    design = compute_selected_design(
        population=population,
        observations=partitioned_frame(storage, measured["observations"]),
        snapshots=partitioned_frame(storage, measured["snapshots"]),
        terminal=partitioned_frame(storage, measured["terminal"]),
    )
    only_selected = lambda frame: frame["candidate_id"].eq(SELECTED_CANDIDATE)  # noqa: E731
    checks: dict[str, Any] = {}
    for name, frame in (
        ("team_states", design.team_states),
        ("rating_states", design.rating_states),
        ("priors", design.priors),
    ):
        expected = partitioned_frame(storage, served[name], keep=only_selected)
        checks[name] = canonical_equal(frame[list(expected.columns)], expected)
    return _receipt(context, checks)


def verify(context: StageContext) -> list[str]:
    key = f"{context.plan.run_prefix()}{context.stage.name}/{RECEIPT}"
    receipt = json.loads(context.read_artifact(context.stage.name, key))
    problems = []
    for name, check in receipt["checks"].items():
        if not (check["equal"] if isinstance(check, dict) else bool(check)):
            problems.append(
                f"{context.stage.name}: {name} does not reproduce the served artifact"
            )
    if not receipt["checks"]:
        problems.append("parity receipt has no checks")
    return problems
