"""Stage 4: compare the rebuilt ledgers and population with the Step 5 evidence.

Legacy-allowed (it reads the Step 5 repair population for parity). Rebuilds the baseline
and R1 candidate ledgers on the corrected Silver, then requires zero drift: the recomputed
decision file must equal the pinned Step 5 file byte for byte, the admitted ledger must
equal the stage-1 admitted ledger record for record, the population must match the legacy
population, and the 2025 punt-flag change must not alter any possession or scoring event.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Iterator, Mapping
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild import baseline, common, eligibility
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput

PREFIX = "rebuild/6a/{run_id}/comparison/"
RECEIPT = "comparison.json"
FILES = {
    "decisions": "decisions.csv",
    "possessions": "possessions.parquet",
    "baseline_events": "baseline_events.parquet",
    "candidate_events": "candidate_events.parquet",
    "admitted_events": "admitted_events.parquet",
}
#: Population columns that legitimately carry rebuilt labels (reported, not gated).
LABEL_COLUMNS = ("missing_measurement_sources", "reconciliation_classification")


def _parquet(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer)
    return buffer.getvalue()


def canonical_equal(left: pd.DataFrame, right: pd.DataFrame) -> dict[str, Any]:
    """Record-for-record comparison after a parquet round trip and a total sort."""
    a = pd.read_parquet(io.BytesIO(_parquet(left)))
    b = pd.read_parquet(io.BytesIO(_parquet(right)))
    if sorted(a.columns) != sorted(b.columns):
        return {
            "equal": False,
            "reason": "columns differ",
            "only_left": sorted(set(a.columns) - set(b.columns)),
            "only_right": sorted(set(b.columns) - set(a.columns)),
        }
    columns = sorted(a.columns)
    a = a[columns].sort_values(columns, kind="mergesort").reset_index(drop=True)
    b = b[columns].sort_values(columns, kind="mergesort").reset_index(drop=True)
    if len(a) != len(b):
        return {"equal": False, "reason": f"rows {len(a)} != {len(b)}"}
    differing = {
        column: int(
            (~((a[column] == b[column]) | (a[column].isna() & b[column].isna()))).sum()
        )
        for column in columns
    }
    differing = {k: v for k, v in differing.items() if v}
    return {"equal": not differing, "rows": len(a), "differing_columns": differing}


#: Possession columns the documented punt-return fix may change (play bookkeeping only).
PUNT_BOOKKEEPING = ("eligible_play_count", "ineligible_play_count", "mixed_eligibility")
POSSESSION_KEYS = ["season", "game_id", "drive_number", "offense"]


def keyed_differences(
    new: pd.DataFrame, old: pd.DataFrame, keys: list[str]
) -> dict[str, Any]:
    """Identity-aligned comparison; never depends on a sort over changed columns."""
    a = new.set_index(keys).sort_index()
    b = old.set_index(keys).sort_index()
    if not a.index.equals(b.index):
        return {"same_keys": False, "differing_columns": {}}
    differing = {}
    for column in sorted(set(a.columns) & set(b.columns)):
        x, y = a[column], b[column]
        count = int((~((x == y) | (x.isna() & y.isna()))).sum())
        if count:
            differing[column] = count
    return {
        "same_keys": True,
        "rows": int(len(a)),
        "differing_columns": differing,
        "only_new_columns": sorted(set(a.columns) - set(b.columns)),
        "only_old_columns": sorted(set(b.columns) - set(a.columns)),
    }


def punt_flag_effect(
    possessions_new: pd.DataFrame,
    possessions_old: pd.DataFrame,
    events_new: Mapping[str, pd.DataFrame],
    events_old: Mapping[str, pd.DataFrame],
) -> dict[str, Any]:
    """Bound the effect of the punt-return flag change on possessions and scoring.

    Allowed: only ``PUNT_BOOKKEEPING`` columns differ, eligible plus ineligible plays are
    conserved on every possession, eligible counts never increase, and possession
    eligibility, quality reasons, periods and every scoring event are unchanged.
    """
    possessions = keyed_differences(possessions_new, possessions_old, POSSESSION_KEYS)
    result: dict[str, Any] = {
        "possessions": possessions,
        "events": {
            name: canonical_equal(events_new[name], events_old[name])
            for name in events_new
        },
    }
    bounded = bool(possessions["same_keys"]) and set(
        possessions["differing_columns"]
    ) <= set(PUNT_BOOKKEEPING)
    if bounded:
        a = possessions_new.set_index(POSSESSION_KEYS).sort_index()
        b = possessions_old.set_index(POSSESSION_KEYS).sort_index()
        total_new = a["eligible_play_count"] + a["ineligible_play_count"]
        total_old = b["eligible_play_count"] + b["ineligible_play_count"]
        result["plays_conserved"] = bool((total_new == total_old).all())
        result["eligible_plays_moved"] = int(
            (b["eligible_play_count"] - a["eligible_play_count"]).sum()
        )
        result["eligible_increased"] = bool(
            (a["eligible_play_count"] > b["eligible_play_count"]).any()
        )
        bounded = result["plays_conserved"] and not result["eligible_increased"]
    result["bounded"] = bool(
        bounded and all(item["equal"] for item in result["events"].values())
    )
    return result


def population_parity(new: pd.DataFrame, legacy: pd.DataFrame) -> dict[str, Any]:
    keys = ["season", "game_id"]
    a = new.sort_values(keys).reset_index(drop=True)
    b = legacy.sort_values(keys).reset_index(drop=True)
    if len(a) != len(b) or not a[keys].equals(b[keys]):
        return {"equal": False, "reason": "game keys differ"}
    gated, labels = {}, {}
    for column in sorted(set(a.columns) & set(b.columns) - set(keys)):
        left, right = a[column], b[column]
        diff = int((~((left == right) | (left.isna() & right.isna()))).sum())
        if diff:
            (labels if column in LABEL_COLUMNS else gated)[column] = diff
    return {"equal": not gated, "differing_columns": gated, "label_differences": labels}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(context: StageContext) -> StageOutput:
    from cks_picks_cfb.data.data_first_possession_v1 import build_population
    from cks_picks_cfb.data.lake import read_dataset
    from cks_picks_cfb.ratings import admission as adm
    from cks_picks_cfb.ratings import possession_measurements as pm
    from cks_picks_cfb.ratings import possession_verification as verifier
    from cks_picks_cfb.ratings import score_envelope_r1 as r1
    from cks_picks_cfb.rebuild import legacy as legacy5c
    from cks_picks_cfb.rebuild.legacy import _repair

    storage = common.preview_storage(context)
    pins = {pin.name: pin for pin in context.plan.inputs}
    pin_file = json.loads(context.read_input("phase2c_silver_parents"))
    seasons = sorted(context.plan.seasons)
    elig_prefix = eligibility.PREFIX.format(run_id=context.plan.run_id)
    population_raw = pd.read_parquet(
        io.BytesIO(
            context.read_artifact("eligibility", elig_prefix + eligibility.POPULATION)
        )
    )
    population = build_population(population_raw, scope="historical")
    outcomes = pd.concat(
        [
            read_dataset(
                storage,
                common.dataset_ref(pin_file["seasons"][str(s)]["game_outcomes"]),
            )
            for s in seasons
        ],
        ignore_index=True,
    )
    byplay = common.staged_silver(context, "byplay")

    def ledger(plays, pop, outs):
        possessions, base = pm.build_possession_ledger(
            byplay=plays, population=pop, outcomes=outs, scope="historical"
        )
        canonical = pm._canonicalize_byplay_teams(plays)
        candidate_plays, _ = r1.apply_r1(canonical, legacy5c._finals(pop, outs))
        _, cand = pm.build_possession_ledger(
            byplay=candidate_plays, population=pop, outcomes=outs, scope="historical"
        )
        return possessions, base, cand

    possessions, base_events, cand_events = ledger(byplay, population, outcomes)
    members: dict[str, list[str]] = {}
    groups = r1.changed_groups(base_events, cand_events, members_out=members)
    status = pd.read_csv(io.BytesIO(context.read_input("corroboration_group_status")))
    group_ids_match = set(status["group_id"]) == set(groups["group_id"])
    if not group_ids_match:
        raise GateError(
            "rebuilt allocation groups differ from the pinned Step 5 groups"
        )
    decisions = adm.build_decisions(status, members)
    admitted = adm.build_admitted_events(base_events, cand_events, decisions, members)
    decisions_bytes = decisions.to_csv(index=False).encode()
    counts = {
        "baseline_events": len(base_events),
        "candidate_events": len(cand_events),
        "admitted_events": len(admitted),
        "decisions": {
            k: int(v) for k, v in decisions["decision"].value_counts().items()
        },
    }
    stage1 = pd.read_parquet(
        io.BytesIO(
            context.read_artifact(
                "baseline_reproduction",
                baseline.OUT.format(run_id=context.plan.run_id)
                + "admitted_events.parquet",
            )
        )
    )
    repair, _ = _repair(storage, pins["repair_v2_manifest"].uri, scope="historical")
    legacy_population = read_dataset(
        storage, common.dataset_ref(repair["output_refs"]["population"])
    )
    parity = population_parity(population_raw, legacy_population)

    # The only 2025 byplay flag change must not move any possession or scoring event.
    s = 2025
    legacy_2025 = read_dataset(
        storage,
        common.dataset_ref(pin_file["seasons"][str(s)]["legacy_comparison"]["byplay"]),
    )
    pop_s = population[population["season"] == s].reset_index(drop=True)
    out_s = outcomes[outcomes["season"] == s].reset_index(drop=True)
    new_s = byplay[byplay["season"] == s].reset_index(drop=True)
    poss_new, base_new, cand_new = ledger(new_s, pop_s, out_s)
    poss_old, base_old, cand_old = ledger(legacy_2025, pop_s, out_s)
    punt_effect = punt_flag_effect(
        poss_new,
        poss_old,
        {"baseline_events": base_new, "candidate_events": cand_new},
        {"baseline_events": base_old, "candidate_events": cand_old},
    )
    verdict = verifier.verify_admitted_ledger(
        byplay=byplay,
        population=population,
        outcomes=outcomes,
        baseline_events=base_events,
        admitted_events=admitted,
        decisions=decisions,
        expected_admitted_groups=baseline.EXPECTED["decisions"]["admitted"],
    )
    admitted_equal = canonical_equal(admitted, stage1)
    checks = {
        "group_ids_match_step5": group_ids_match,
        "decisions_csv_bytes": _sha(decisions_bytes)
        == context.plan.decisions["admission_decisions_csv"],
        "baseline_events": counts["baseline_events"]
        == baseline.EXPECTED["baseline_events"],
        "candidate_events": counts["candidate_events"]
        == baseline.EXPECTED["candidate_events"],
        "admitted_events": counts["admitted_events"]
        == baseline.EXPECTED["admitted_events"],
        "decision_counts": counts["decisions"] == baseline.EXPECTED["decisions"],
        "admitted_equals_stage1": bool(admitted_equal["equal"]),
        "population_parity": bool(parity["equal"]),
        "punt_flag_change_bounded": bool(punt_effect["bounded"]),
        "independent_verifier": bool(verdict["ok"]),
    }
    receipt = {
        "checks": checks,
        "passed": all(checks.values()),
        "counts": counts,
        "population": {
            "games": int(len(population_raw)),
            "parity": parity,
        },
        "admitted_vs_stage1": admitted_equal,
        "punt_flag_effect_2025": punt_effect,
        "verifier": {"ok": bool(verdict["ok"]), "problems": verdict["problems"][:20]},
        "decisions_csv_sha256": _sha(decisions_bytes),
    }
    prefix = PREFIX.format(run_id=context.plan.run_id)

    def artifacts() -> Iterator[tuple[str, bytes]]:
        yield prefix + FILES["decisions"], decisions_bytes
        yield prefix + FILES["possessions"], _parquet(possessions)
        yield prefix + FILES["baseline_events"], _parquet(base_events)
        yield prefix + FILES["candidate_events"], _parquet(cand_events)
        yield prefix + FILES["admitted_events"], _parquet(admitted)
        yield (
            prefix + RECEIPT,
            json.dumps(receipt, indent=2, sort_keys=True, default=str).encode(),
        )

    return StageOutput(
        artifacts=artifacts(), metrics={"gate_passed": receipt["passed"], **counts}
    )


def verify(context: StageContext) -> list[str]:
    """Re-derive the headline checks from the staged files, not the receipt's verdict."""
    stage = context.stage.name
    prefix = PREFIX.format(run_id=context.plan.run_id)
    read = lambda name: context.read_artifact(stage, prefix + name)  # noqa: E731
    problems: list[str] = []
    receipt = json.loads(read(RECEIPT))
    if (
        _sha(read(FILES["decisions"]))
        != context.plan.decisions["admission_decisions_csv"]
    ):
        problems.append("decisions differ from the pinned Step 5 file")
    admitted = pd.read_parquet(io.BytesIO(read(FILES["admitted_events"])))
    stage1 = pd.read_parquet(
        io.BytesIO(
            context.read_artifact(
                "baseline_reproduction",
                baseline.OUT.format(run_id=context.plan.run_id)
                + "admitted_events.parquet",
            )
        )
    )
    if not canonical_equal(admitted, stage1)["equal"]:
        problems.append("admitted ledger differs from the stage-1 admitted ledger")
    for name, expected in (
        ("baseline_events", baseline.EXPECTED["baseline_events"]),
        ("candidate_events", baseline.EXPECTED["candidate_events"]),
    ):
        if len(pd.read_parquet(io.BytesIO(read(FILES[name])))) != expected:
            problems.append(f"{name} count differs from Step 5")
    if not receipt.get("passed"):
        failed = [k for k, ok in receipt["checks"].items() if not ok]
        problems.append(f"comparison gate failed: {failed}")
    return problems
