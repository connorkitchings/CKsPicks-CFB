#!/usr/bin/env python3
"""Re-key the pinned Window-2 5C admission decisions to provider-keyed ids (offline, read-only).

Contract 2026-10-09/01, Task 4.5. No CFBD request and no write outside ``--output-dir``.

``season``: for one season, rebuild the v1 ledgers from the historical by-play (anchor: the
recomputed groups must equal the pinned groups), rebuild the v2 ledgers from every distinct
provider play, re-key the pinned decisions through a deterministic id mapping, reconcile them
with the groups recomputed from v2, build the v2 admitted ledger, run the independent verifier
on it and convert it to the Gold v2 contracts with evidence.

``assemble``: combine the seasons into ``admission_decisions_v2.csv`` and
``corroboration_group_status_v2.csv`` plus a report, and check the headline invariants.

    PYTHONPATH=src:. uv run python scripts/analysis/rekey_admission_v2.py season \\
        --season 2022 --output-dir <dir>
    PYTHONPATH=src:. uv run python scripts/analysis/rekey_admission_v2.py assemble \\
        --output-dir <dir> --evidence-dir <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.ratings.admission_rekey import (
    admitted_equal_outside,
    canonical_equal,
    legacy_event_map,
    reconcile_groups,
    rekey_decisions,
    rekey_status,
)

PINNED_DECISIONS = Path("docs/plans/2026-10-03/window2/5c-data/admission_decisions.csv")
PINNED_STATUS = Path(
    "docs/plans/2026-10-03/window2/5a-data/corroboration_group_status.csv"
)
CFBD_MANIFEST = Path("docs/plans/2026-10-03/window2/5a-data/cfbd_drives_manifest.jsonl")
PHASE2C_PARENTS = Path("conf/rebuild/phase2c_silver_parents_v1.json")
REPAIR_MANIFEST = (
    "artifacts/research/data-first-football-v1/repair/v2/runs/"
    "repair-v2-20260909T1417Z/repair-manifest.json"
)
COLLISION_GAMES = frozenset({401310699, 401756916, 401761632, 401762831})
SCHEMA = "admission_rekey_v2"
EXPECTED = {"admitted": 1416, "reverted_contradicted": 28, "reverted_unverified": 1749}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_season(season: int, output_dir: Path) -> dict[str, Any]:  # pragma: no cover
    from dotenv import load_dotenv

    from cks_picks_cfb.data.data_first_possession_v1 import build_population
    from cks_picks_cfb.data.lake import DatasetRef, read_dataset
    from cks_picks_cfb.data.storage import get_storage
    from cks_picks_cfb.features.pipeline import build_preaggregation_pipeline
    from cks_picks_cfb.metrics import contracts as gold
    from cks_picks_cfb.metrics import evidence as ev
    from cks_picks_cfb.metrics import ledger as ml
    from cks_picks_cfb.ratings import admission as adm
    from cks_picks_cfb.ratings import possession_measurements as pm
    from cks_picks_cfb.ratings import possession_verification as verifier
    from cks_picks_cfb.ratings import score_envelope_r1 as r1
    from cks_picks_cfb.rebuild.legacy import _finals, _repair
    from scripts.analysis.play_identity_impact import legacy_dedup

    load_dotenv(".env")
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("The re-key requires explicit R2 storage")
    storage = get_storage(environment="preview")

    def ref(entry: dict) -> DatasetRef:
        return DatasetRef(
            **{
                k: entry[k]
                for k in (
                    "dataset",
                    "version_id",
                    "schema_version",
                    "content_sha",
                    "uri",
                )
            }
        )

    pins = json.loads(PHASE2C_PARENTS.read_text())["seasons"][str(season)]
    frames = {p["dataset"]: read_dataset(storage, ref(p)) for p in pins["parents"]}
    outcomes = read_dataset(storage, ref(pins["game_outcomes"]))
    repair, _ = _repair(storage, REPAIR_MANIFEST, scope="historical")
    population = build_population(
        read_dataset(storage, ref(repair["output_refs"]["population"])),
        scope="historical",
    )
    population = population[population["season"] == season].reset_index(drop=True)
    games = frames["fbs_involved_games"]
    options = dict(
        games_df=games.rename(columns={"kickoff_utc": "start_date"}),
        teams_df=frames["teams"],
        venues_df=None,
        weather_df=None,
        corrections_df=frames["data_corrections"],
        nullable_ppa=True,
    )
    by1, *_ = build_preaggregation_pipeline(legacy_dedup(frames["plays"]), **options)
    by2, drives2, *_ = build_preaggregation_pipeline(
        frames["plays"], play_identity="byplay_v2", **options
    )
    finals = _finals(population, outcomes)

    def ledgers(byplay: pd.DataFrame, identity: str | None):
        extra = {"play_identity": identity} if identity else {}
        possessions, baseline = pm.build_possession_ledger(
            byplay=byplay,
            population=population,
            outcomes=outcomes,
            scope="historical",
            **extra,
        )
        canonical = pm._canonicalize_byplay_teams(byplay)
        candidate_plays, _ = r1.apply_r1(canonical, finals)
        _, candidate = pm.build_possession_ledger(
            byplay=candidate_plays,
            population=population,
            outcomes=outcomes,
            scope="historical",
            **extra,
        )
        members: dict[str, list[str]] = {}
        groups = r1.changed_groups(
            baseline,
            candidate,
            restoration_team_games=r1.restoration_jumps(canonical),
            members_out=members,
        )
        return possessions, baseline, candidate, groups, members

    pinned_decisions = pd.read_csv(PINNED_DECISIONS)
    pinned_status = pd.read_csv(PINNED_STATUS)
    pinned_d = pinned_decisions[pinned_decisions["season"] == season].reset_index(
        drop=True
    )
    pinned_s = pinned_status[pinned_status["season"] == season].reset_index(drop=True)

    poss1, base1, cand1, groups1, members1 = ledgers(by1, None)
    anchor_groups = set(groups1["group_id"]) == set(pinned_s["group_id"])
    decisions1 = adm.build_decisions(pinned_s, members1) if anchor_groups else None
    anchor_decisions = bool(
        decisions1 is not None and canonical_equal(decisions1, pinned_d)["equal"]
    )
    poss2, base2, cand2, groups2, members2 = ledgers(by2, "byplay_v2")

    event_map = legacy_event_map(frames["plays"], season)
    rekeyed = rekey_decisions(pinned_d, event_map)
    reconciled = reconcile_groups(pinned_d, rekeyed, groups2, members2, COLLISION_GAMES)
    final = reconciled["final_status"]
    decisions2 = adm.build_decisions(final, members2)
    admitted2 = adm.build_admitted_events(base2, cand2, decisions2, members2)

    # v1 admitted ledger mapped to v2 ids, compared outside the collision games.
    admitted1 = (
        adm.build_admitted_events(base1, cand1, decisions1, members1)
        if anchor_groups
        else None
    )
    group_map = dict(zip(rekeyed["group_id_v1"], rekeyed["group_id"]))
    equality: dict[str, Any] = {"compared": False}
    if admitted1 is not None:
        equality = {
            "compared": True,
            **admitted_equal_outside(
                admitted2, admitted1, event_map, group_map, COLLISION_GAMES
            ),
        }

    verdict = verifier.verify_admitted_ledger(
        byplay=by2,
        population=population,
        outcomes=outcomes,
        baseline_events=base2,
        admitted_events=admitted2,
        decisions=decisions2,
        play_identity="byplay_v2",
    )

    # Gold v2 dry run with evidence from the retained, hash-verified bundles (read-only).
    records = [
        json.loads(r) for r in CFBD_MANIFEST.read_text().splitlines() if r.strip()
    ]
    cache: dict[str, bytes] = {}

    def read_bundle(name: str) -> bytes:
        if name not in cache:
            cache[name] = storage.read_bytes(ev.BUNDLE_PREFIX + name)
        return cache[name]

    index = ev.bundle_index(records, read_bundle)
    admitted_groups = decisions2[decisions2["decision"] == adm.ADMITTED]
    evidence_ids = {
        r.group_id: (ev.evidence_id(r.group_id, index[int(r.game_id)]["sha256"]),)
        for r in admitted_groups.itertuples(index=False)
    }
    canonical_by2 = pm._canonicalize_byplay_teams(by2)
    versions = {"byplay": "byplay_v2"}
    groups_by_event = {
        (int(r.game_id), str(r.team), str(r.source_event_id)): r.allocation_group_id
        for r in admitted2.dropna(subset=["allocation_group_id"]).itertuples()
    }
    drives_gold = (
        drives2.merge(
            by2[["game_id", "season", "week"]].drop_duplicates("game_id"),
            on="game_id",
            how="left",
            suffixes=("", "_play"),
        )
        if "season" not in drives2
        else drives2
    )
    possessions_gold = ml.possessions_to_v2(
        poss2, drives_gold, source_versions=versions
    )
    ledger_gold = ml.scoring_events_to_v2(
        admitted2,
        canonical_by2,
        finals=finals,
        source_versions=versions,
        rule_version="baseline_v1",
        groups=groups_by_event,
        admitted_evidence=evidence_ids,
        admitted_rule_version=adm.RULE_VERSION,
        populate_envelopes=True,
    )
    evidence = ev.build_evidence(decisions2, ledger_gold, index)
    gold_problems = (
        gold.possessions_v2_problems(possessions_gold)
        + gold.scoring_ledger_v2_problems(ledger_gold, possessions_gold)
        + gold.evidence_problems(evidence)
        + ev.evidence_reference_problems(
            evidence,
            ledger_gold.assign(),
            index,
            read_bundle,
        )
    )

    status_v2 = rekey_status(pinned_s, group_map)
    status_v2 = status_v2[status_v2["group_id"].isin(set(final["group_id"]))]
    new_rows = final[~final["group_id"].isin(set(status_v2["group_id"]))].assign(
        group_id_v1=pd.NA
    )
    status_v2 = pd.concat(
        [status_v2, new_rows[[c for c in status_v2.columns if c in new_rows.columns]]],
        ignore_index=True,
    )

    out = output_dir / f"season={season}"
    out.mkdir(parents=True, exist_ok=True)
    decisions2.to_csv(out / "decisions_v2.csv", index=False)
    status_v2.sort_values("group_id").to_csv(out / "status_v2.csv", index=False)
    summary = {
        "season": season,
        "population_games": int(len(population)),
        "anchor": {
            "v1_groups_equal_pinned": anchor_groups,
            "v1_decisions_equal_pinned": anchor_decisions,
        },
        "groups": {
            "pinned": int(len(pinned_d)),
            "recomputed_v2": int(len(groups2)),
            "matched": reconciled["matched"],
        },
        "reconcile_problems": reconciled["problems"],
        "pinned_only": reconciled["pinned_only"],
        "recomputed_only": reconciled["recomputed_only"],
        "differing": reconciled["differing"],
        "decisions_v2": {
            k: int(v) for k, v in decisions2["decision"].value_counts().items()
        },
        "decisions_pinned": {
            k: int(v) for k, v in pinned_d["decision"].value_counts().items()
        },
        "admitted_events": {
            "v2": int(len(admitted2)),
            "v1": None if admitted1 is None else int(len(admitted1)),
        },
        "admitted_equals_v1_outside_collisions": equality,
        "independent_verifier": {
            "ok": bool(verdict["ok"]),
            "problems": verdict["problems"][:10],
        },
        "gold_v2": {
            "possessions": int(len(possessions_gold)),
            "ledger": int(len(ledger_gold)),
            "evidence": int(len(evidence)),
            "problems": gold_problems[:10],
            "problem_count": len(gold_problems),
        },
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n"
    )
    return summary


def assemble(output_dir: Path, evidence_dir: Path) -> dict[str, Any]:
    seasons = sorted(
        p for p in output_dir.glob("season=*") if (p / "summary.json").exists()
    )
    summaries = [json.loads((p / "summary.json").read_text()) for p in seasons]
    decisions = pd.concat(
        [pd.read_csv(p / "decisions_v2.csv") for p in seasons], ignore_index=True
    )
    status = pd.concat(
        [pd.read_csv(p / "status_v2.csv") for p in seasons], ignore_index=True
    )
    decisions = decisions.sort_values("group_id", kind="mergesort").reset_index(
        drop=True
    )
    status = status.sort_values("group_id", kind="mergesort").reset_index(drop=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    decisions.to_csv(evidence_dir / "admission_decisions_v2.csv", index=False)
    status.to_csv(evidence_dir / "corroboration_group_status_v2.csv", index=False)
    counts = {k: int(v) for k, v in decisions["decision"].value_counts().items()}
    pinned = {
        k: int(v)
        for k, v in pd.read_csv(PINNED_DECISIONS)["decision"].value_counts().items()
    }
    problems: list[str] = []
    if decisions["group_id"].duplicated().any():
        problems.append("duplicate v2 group ids")
    for key in ("admitted", "reverted_contradicted"):
        if counts.get(key) != pinned.get(key):
            problems.append(
                f"{key} count {counts.get(key)} != pinned {pinned.get(key)}"
            )
    for item in summaries:
        s = item["season"]
        if not all(item["anchor"].values()):
            problems.append(f"{s}: v1 anchor failed {item['anchor']}")
        problems += [f"{s}: {p}" for p in item["reconcile_problems"]]
        if (
            item["admitted_equals_v1_outside_collisions"].get("compared")
            and not item["admitted_equals_v1_outside_collisions"]["equal"]
        ):
            problems.append(
                f"{s}: admitted ledger differs from v1 outside the collision games"
            )
        if not item["independent_verifier"]["ok"]:
            problems.append(f"{s}: independent verifier failed")
        if item["gold_v2"]["problem_count"]:
            problems.append(
                f"{s}: {item['gold_v2']['problem_count']} Gold v2 contract problems"
            )
    report = {
        "schema_version": SCHEMA,
        "contract": "docs/plans/2026-10-09/01-byplay-v2-play-identity.md#task-4",
        "collision_games": sorted(COLLISION_GAMES),
        "inputs": {
            "pinned_decisions_sha256": sha256_file(PINNED_DECISIONS),
            "pinned_status_sha256": sha256_file(PINNED_STATUS),
            "phase2c_parents_sha256": sha256_file(PHASE2C_PARENTS),
        },
        "outputs": {
            "admission_decisions_v2_sha256": sha256_file(
                evidence_dir / "admission_decisions_v2.csv"
            ),
            "corroboration_group_status_v2_sha256": sha256_file(
                evidence_dir / "corroboration_group_status_v2.csv"
            ),
        },
        "decisions": {"v2": counts, "pinned": pinned, "expected": EXPECTED},
        "totals": {
            "groups_v2": int(len(decisions)),
            "pinned_only": sum(len(s["pinned_only"]) for s in summaries),
            "recomputed_only": sum(len(s["recomputed_only"]) for s in summaries),
            "differing": sum(len(s["differing"]) for s in summaries),
            "evidence_rows": sum(s["gold_v2"]["evidence"] for s in summaries),
        },
        "seasons": {str(s["season"]): s for s in summaries},
        "problems": problems,
        "passed": not problems,
    }
    (evidence_dir / "rekey_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    )
    return report


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("season")
    one.add_argument("--season", type=int, required=True)
    one.add_argument("--output-dir", type=Path, required=True)
    many = sub.add_parser("assemble")
    many.add_argument("--output-dir", type=Path, required=True)
    many.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "season":
        print(
            json.dumps(
                run_season(args.season, args.output_dir),
                indent=2,
                sort_keys=True,
                default=str,
            )[:3000]
        )
    else:
        report = assemble(args.output_dir, args.evidence_dir)
        print(
            json.dumps(
                {k: report[k] for k in ("decisions", "totals", "problems", "passed")},
                indent=2,
                default=str,
            )
        )


if __name__ == "__main__":
    main()
