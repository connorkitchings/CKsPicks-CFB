"""Stage 1: reproduce the Step 5 baseline, candidate and admitted ledgers exactly.

This is the only stage allowed to touch the legacy repair-v2 parent. It reuses the 5C
reproduction primitives and asserts byte identity with the pinned decision files.
"""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput

OUT = "rebuild/6a/{run_id}/baseline/"
EXPECTED = {
    "baseline_events": 86937,
    "candidate_events": 82416,
    "admitted_events": 85457,
    "decisions": {
        "admitted": 1416,
        "reverted_contradicted": 28,
        "reverted_unverified": 1749,
    },
}
DECISIONS = "admission_decisions.csv"
REPORT = "admission_report.json"
GATE = "gate.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evaluate_gate(
    *,
    counts: Mapping[str, Any],
    decisions_bytes: bytes,
    report_bytes: bytes,
    pinned: Mapping[str, str],
    verifier_ok: bool,
    v1_problem_count: int,
) -> dict[str, Any]:
    """Pure gate: every check recorded, pass only if all hold."""
    checks = {
        "baseline_events": counts["baseline_events"] == EXPECTED["baseline_events"],
        "candidate_events": counts["candidate_events"] == EXPECTED["candidate_events"],
        "admitted_events": counts["admitted_events"] == EXPECTED["admitted_events"],
        "decision_counts": dict(counts["decisions"]) == EXPECTED["decisions"],
        "decisions_csv_bytes": _sha(decisions_bytes)
        == pinned["admission_decisions_csv"],
        "report_json_bytes": _sha(report_bytes) == pinned["admission_report_json"],
        "independent_verifier": bool(verifier_ok),
        "v1_contract_problems_zero": v1_problem_count == 0,
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "actual": {
            "counts": dict(counts),
            "decisions_csv_sha256": _sha(decisions_bytes),
            "report_json_sha256": _sha(report_bytes),
        },
        "expected": {**EXPECTED, **{k: v for k, v in pinned.items()}},
    }


def _json_diff(left: Any, right: Any, path: str = "") -> list[str]:
    """Locate differences between the recomputed and pinned report for diagnosis."""
    if type(left) is not type(right):
        return [f"{path}: type {type(left).__name__} != {type(right).__name__}"]
    if isinstance(left, dict):
        out: list[str] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                out.append(f"{path}/{key}: present on one side only")
            else:
                out.extend(_json_diff(left[key], right[key], f"{path}/{key}"))
        return out
    if isinstance(left, list):
        if len(left) != len(right):
            return [f"{path}: length {len(left)} != {len(right)}"]
        return [
            d
            for i, (a, b) in enumerate(zip(left, right))
            for d in _json_diff(a, b, f"{path}[{i}]")
        ]
    return [] if left == right else [f"{path}: {left!r} != {right!r}"]


def _fetch_cfbd_bundles(context: StageContext, remote_read, target: Path) -> None:
    """Materialize the pinned CFBD bundles from Preview R2, hash-verified, in a tempdir."""
    manifest_bytes = context.read_input("cfbd_drives_manifest")
    records = [
        json.loads(line)
        for line in manifest_bytes.decode().splitlines()
        if line.strip()
    ]
    raw = target / "raw"
    raw.mkdir(parents=True)
    for record in records:
        data = remote_read(f"raw/cfbd/drives/{record['file']}")
        if _sha(data) != record["sha256"]:
            raise GateError(f"CFBD bundle hash mismatch: {record['file']}")
        (raw / record["file"]).write_bytes(data)
    (target / "manifest.jsonl").write_bytes(manifest_bytes)


def reproduce(context: StageContext) -> StageOutput:
    from dotenv import load_dotenv

    load_dotenv()
    from cks_picks_cfb.data.data_first_possession_v1 import build_population
    from cks_picks_cfb.data.lake import read_dataset
    from cks_picks_cfb.data.storage import get_storage
    from cks_picks_cfb.data.storage.base import StorageSettings
    from cks_picks_cfb.metrics import contracts as gold
    from cks_picks_cfb.metrics.ledger import scoring_events_to_v1
    from cks_picks_cfb.ratings import admission as adm
    from cks_picks_cfb.ratings import possession_measurements as pm
    from cks_picks_cfb.ratings import possession_verification as verifier
    from cks_picks_cfb.ratings import score_envelope_r1 as r1
    from scripts.analysis import build_admitted_ledger_5c as legacy
    from scripts.research.run_data_first_possession_measurements import (
        _concat_source_frames,
        _ref,
        _repair,
        _sources,
    )

    settings = StorageSettings.from_env(environment="preview")
    identity = f"r2:{settings.account_id}:{settings.bucket}"
    if identity != context.plan.storage_identity:
        raise GateError(f"storage identity {identity} differs from the plan")
    pins = {pin.name: pin for pin in context.plan.inputs}
    repair_uri = pins["repair_v2_manifest"].uri
    storage = get_storage(environment="preview")

    repair, _ = _repair(storage, repair_uri, scope="historical")
    population = build_population(
        read_dataset(storage, _ref(repair["output_refs"]["population"])),
        scope="historical",
    )
    refs = _sources(storage, repair, scope="historical")
    byplay = _concat_source_frames(
        [read_dataset(storage, refs[s]["byplay"]) for s in sorted(refs)]
    )
    outcomes = _concat_source_frames(
        [read_dataset(storage, refs[s]["game_outcomes"]) for s in sorted(refs)]
    )
    possessions, base_events = pm.build_possession_ledger(
        byplay=byplay, population=population, outcomes=outcomes, scope="historical"
    )
    canonical = pm._canonicalize_byplay_teams(byplay)
    finals = legacy._finals(population, outcomes)
    candidate_plays, _ = r1.apply_r1(canonical, finals)
    _, cand_events = pm.build_possession_ledger(
        byplay=candidate_plays,
        population=population,
        outcomes=outcomes,
        scope="historical",
    )
    members: dict[str, list[str]] = {}
    groups = r1.changed_groups(base_events, cand_events, members_out=members)
    status = pd.read_csv(io.BytesIO(context.read_input("corroboration_group_status")))
    if set(status["group_id"]) != set(groups["group_id"]):
        raise GateError("pinned gate decisions do not match the recomputed groups")
    decisions = adm.build_decisions(status, members)
    admitted = adm.build_admitted_events(base_events, cand_events, decisions, members)
    counts = {
        "baseline_events": len(base_events),
        "candidate_events": len(cand_events),
        "admitted_events": len(admitted),
        "decisions": {
            k: int(v) for k, v in decisions["decision"].value_counts().items()
        },
    }

    with tempfile.TemporaryDirectory(prefix="6a-cfbd-") as tmp:
        _fetch_cfbd_bundles(context, _remote_reader(), Path(tmp))
        evidence = legacy._evidence_ids(Path(tmp), decisions)
    group_map = {
        (int(r.game_id), str(r.team), str(r.source_event_id)): r.allocation_group_id
        for r in admitted.dropna(subset=["allocation_group_id"]).itertuples()
    }
    v1 = scoring_events_to_v1(
        admitted,
        canonical.copy(),
        finals=finals,
        source_versions={"repair_manifest": repair_uri},
        rule_version="baseline_v1",
        groups=group_map,
        admitted_evidence=evidence,
        admitted_rule_version=adm.RULE_VERSION,
    )
    v1_problems = gold.scoring_ledger_problems(v1)
    by = decisions.assign(
        points=decisions["net_points"].where(decisions["net_points"] > 0, 0.0)
    )
    delta = {
        "by_decision": counts["decisions"],
        "by_season": {
            str(k): {d: int(v) for d, v in g["decision"].value_counts().items()}
            for k, g in by.groupby("season")
        },
        "by_primary_cause": {
            str(k): {d: int(v) for d, v in g["decision"].value_counts().items()}
            for k, g in by.groupby("primary_cause")
        },
        "points_recovered": {
            d: float(g["points"].sum()) for d, g in by.groupby("decision")
        },
        "net_points_by_decision": {
            d: float(g["net_points"].sum()) for d, g in by.groupby("decision")
        },
        "baseline_events": len(base_events),
        "admitted_events": len(admitted),
        "materiality": legacy._materiality(base_events, admitted, possessions),
    }
    verdict = verifier.verify_admitted_ledger(
        byplay=byplay,
        population=population,
        outcomes=outcomes,
        baseline_events=base_events,
        admitted_events=admitted,
        decisions=decisions,
        expected_admitted_groups=EXPECTED["decisions"]["admitted"],
    )
    report = {
        "delta": delta,
        "v1_contract_problems": v1_problems[:20],
        "v1_contract_problem_count": len(v1_problems),
        "verifier": verdict,
    }
    decisions_bytes = decisions.to_csv(index=False).encode()
    report_bytes = json.dumps(report, indent=2, sort_keys=True, default=str).encode()
    gate = evaluate_gate(
        counts=counts,
        decisions_bytes=decisions_bytes,
        report_bytes=report_bytes,
        pinned=context.plan.decisions,
        verifier_ok=bool(verdict["ok"]),
        v1_problem_count=len(v1_problems),
    )
    pinned_report = json.loads(context.read_input("admission_report"))
    gate["report_diff_vs_pinned"] = _json_diff(json.loads(report_bytes), pinned_report)[
        :50
    ]
    buffer = io.BytesIO()
    admitted.to_parquet(buffer)
    prefix = OUT.format(run_id=context.plan.run_id)

    def artifacts() -> Iterator[tuple[str, bytes]]:
        yield prefix + DECISIONS, decisions_bytes
        yield prefix + REPORT, report_bytes
        yield prefix + "admitted_events.parquet", buffer.getvalue()
        yield prefix + GATE, json.dumps(gate, indent=2, sort_keys=True).encode()

    return StageOutput(
        artifacts=artifacts(), metrics={"gate_passed": gate["passed"], **counts}
    )


def _remote_reader():
    import os

    from cks_picks_cfb.rebuild.targets import R2ObjectStore

    return R2ObjectStore(
        bucket=os.environ["CFB_R2_PREVIEW_BUCKET"],
        account_id=os.environ["CFB_R2_PREVIEW_ACCOUNT_ID"],
        access_key=os.environ["CFB_R2_PREVIEW_ACCESS_KEY"],
        secret_key=os.environ["CFB_R2_PREVIEW_SECRET_KEY"],
        endpoint=os.environ.get("CFB_R2_PREVIEW_ENDPOINT"),
    ).read


def verify(context: StageContext) -> list[str]:
    """Re-derive the gate from the staged bytes, independent of the build's verdict."""
    prefix = OUT.format(run_id=context.plan.run_id)
    stage = context.stage.name
    read = lambda name: context.read_artifact(stage, prefix + name)  # noqa: E731
    problems: list[str] = []
    decisions_bytes, report_bytes = read(DECISIONS), read(REPORT)
    gate = json.loads(read(GATE))
    frame = pd.read_csv(io.BytesIO(decisions_bytes))
    counts = {k: int(v) for k, v in frame["decision"].value_counts().items()}
    if counts != EXPECTED["decisions"]:
        problems.append(f"decision counts {counts} != {EXPECTED['decisions']}")
    for name, data in (
        ("admission_decisions_csv", decisions_bytes),
        ("admission_report_json", report_bytes),
    ):
        if _sha(data) != context.plan.decisions[name]:
            problems.append(f"{name} bytes differ from the pinned Step 5 file")
    admitted = pd.read_parquet(io.BytesIO(read("admitted_events.parquet")))
    if len(admitted) != EXPECTED["admitted_events"]:
        problems.append(
            f"admitted events {len(admitted)} != {EXPECTED['admitted_events']}"
        )
    report = json.loads(report_bytes)
    if not (report.get("verifier") or {}).get("ok"):
        problems.append("independent verifier did not pass")
    if report.get("v1_contract_problem_count"):
        problems.append("v1 contract problems present")
    if not gate.get("passed"):
        failed = [k for k, ok in gate["checks"].items() if not ok]
        problems.append(f"build gate failed: {failed}")
    return problems
