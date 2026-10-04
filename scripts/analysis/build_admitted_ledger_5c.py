#!/usr/bin/env python3
"""Window 2 Step 5C: build the admitted historical scoring ledger and verify it. Local dry run.

Reads the pinned Silver inputs from Preview (read-only), rebuilds the baseline and R1
candidate ledgers, applies the 5A gate decisions per allocation group (corroborated groups
take R1, everything else reverts exactly to baseline), converts the result to the
``football_scoring_ledger_v1`` contract, and runs the independent verifier in
``ratings/possession_verification.py``. Writes only under ``--output-dir``. No R2 write, no
database write, no CFBD request.

    PYTHONPATH=src:. uv run python scripts/analysis/build_admitted_ledger_5c.py \\
        --repair-manifest-uri <uri> --output-dir <dir> --cfbd-dir <dir> \\
        [--reuse-sizing-dir <dir>] [--expected-admitted 1416]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_possession_v1 import build_population
from cks_picks_cfb.data.lake import read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.metrics import contracts as gold
from cks_picks_cfb.metrics.ledger import scoring_events_to_v1
from cks_picks_cfb.ratings import admission as adm
from cks_picks_cfb.ratings import possession_measurements as pm
from cks_picks_cfb.ratings import possession_verification as verifier
from cks_picks_cfb.ratings import score_envelope_r1 as r1
from scripts.research.run_data_first_possession_measurements import (
    _concat_source_frames,
    _ref,
    _repair,
    _sources,
)

DEFAULT_STATUS = Path(
    "docs/plans/2026-10-03/window2/5a-data/corroboration_group_status.csv"
)


def _log(message: str, start: float) -> None:
    print(f"[{time.time() - start:7.1f}s] {message}", file=sys.stderr, flush=True)


def _finals(population: pd.DataFrame, outcomes: pd.DataFrame) -> dict:
    scores = population
    if "home_points" not in population.columns:
        scores = population.merge(
            outcomes[
                ["season", "game_id", "home_points", "away_points"]
            ].drop_duplicates(["season", "game_id"]),
            on=["season", "game_id"],
            how="left",
        )
    finals = {}
    for row in scores.itertuples(index=False):
        if getattr(row, "outcome_valid", False):
            if pd.notna(row.home_points):
                finals[(int(row.game_id), str(row.home_team))] = float(row.home_points)
            if pd.notna(row.away_points):
                finals[(int(row.game_id), str(row.away_team))] = float(row.away_points)
    return finals


def _evidence_ids(
    cfbd_dir: Path, decisions: pd.DataFrame
) -> dict[str, tuple[str, ...]]:
    """One deterministic evidence id per admitted group, tied to the retained bundle hash."""
    manifest = [
        json.loads(line)
        for line in (cfbd_dir / "manifest.jsonl").read_text().splitlines()
        if line.strip()
    ]
    game_bundle: dict[int, str] = {}
    for record in manifest:
        for row in json.loads((cfbd_dir / "raw" / record["file"]).read_bytes()):
            game_bundle[int(row["gameId"])] = record["sha256"]
    out: dict[str, tuple[str, ...]] = {}
    for row in decisions[decisions["decision"] == adm.ADMITTED].itertuples(index=False):
        sha = game_bundle[int(row.game_id)]
        digest = hashlib.sha256(f"{row.group_id}|{sha}".encode()).hexdigest()[:20]
        out[row.group_id] = (f"cfbd_drives:{digest}",)
    return out


FULL_SEASON_POSSESSIONS = 60  # FCS teams in FBS-involved games have far fewer


def _materiality(
    base_events: pd.DataFrame, admitted: pd.DataFrame, possessions: pd.DataFrame
) -> dict:
    """Raw PPP and raw PPP rank deltas on the admitted output (adjusted/state deltas: 6A).

    Reported for every team-season and for team-seasons with at least
    ``FULL_SEASON_POSSESSIONS`` eligible possessions; the small samples are mostly FCS teams
    that appear in one or two FBS-involved games, where one touchdown moves PPP by 0.5+.
    """
    reg = possessions[
        (possessions["period_class"] == "regulation")
        & possessions["possession_eligible"].fillna(False).astype(bool)
        & possessions["quality_reason"].isna()
    ]
    n = reg.groupby(["season", "offense"]).size().rename("n")

    def ppp(events: pd.DataFrame) -> pd.Series:
        pts = (
            events[events["scoring_category"] == "eligible_regulation_offense"]
            .groupby(["season", "team"])["score_increment"]
            .sum()
        )
        pts.index.names = ["season", "offense"]
        return (pts / n).dropna()

    before, after = ppp(base_events), ppp(admitted)
    both = pd.concat([before.rename("b"), after.rename("a"), n], axis=1).dropna()
    both["delta"] = both["a"] - both["b"]
    both["rank_b"] = both.groupby("season")["b"].rank(ascending=False, method="min")
    both["rank_a"] = both.groupby("season")["a"].rank(ascending=False, method="min")
    both["rank_delta"] = (both["rank_a"] - both["rank_b"]).abs()

    def summary(frame: pd.DataFrame) -> dict:
        return {
            "team_seasons": len(frame),
            "raw_ppp_changed": int((frame["delta"].abs() > 1e-12).sum()),
            "raw_ppp_delta_gt_0_05": int((frame["delta"].abs() > 0.05).sum()),
            "max_abs_raw_ppp_delta": round(float(frame["delta"].abs().max()), 5),
            "raw_rank_move_gt_5": int((frame["rank_delta"] > 5).sum()),
            "max_raw_rank_move": int(frame["rank_delta"].max()),
        }

    full = both[both["n"] >= FULL_SEASON_POSSESSIONS].copy()
    # Ranks are only meaningful among comparable team-seasons.
    full["rank_b"] = full.groupby("season")["b"].rank(ascending=False, method="min")
    full["rank_a"] = full.groupby("season")["a"].rank(ascending=False, method="min")
    full["rank_delta"] = (full["rank_a"] - full["rank_b"]).abs()
    return {
        "all_team_seasons": summary(both),
        f"at_least_{FULL_SEASON_POSSESSIONS}_possessions": summary(full),
        "adjusted_and_state_deltas": "not computed in 5C; they need the 6A rating rebuild",
    }


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cfbd-dir", type=Path, required=True)
    parser.add_argument("--group-status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--reuse-sizing-dir", type=Path, default=None)
    parser.add_argument("--expected-admitted", type=int, default=None)
    parser.add_argument("--skip-verifier", action="store_true")
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    start = time.time()

    storage = get_storage(environment="preview")
    repair, _ = _repair(storage, args.repair_manifest_uri, scope="historical")
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
    _log(f"inputs: {len(byplay)} plays, {len(population)} games", start)

    reuse = args.reuse_sizing_dir
    if reuse is not None and (reuse / "baseline_events.parquet").exists():
        base_events = pd.read_parquet(reuse / "baseline_events.parquet")
        possessions = pd.read_parquet(reuse / "baseline_possessions.parquet")
        cand_events = pd.read_parquet(reuse / "candidate_events.parquet")
        _log("baseline and candidate ledgers reused from the sizing run", start)
    else:
        possessions, base_events = pm.build_possession_ledger(
            byplay=byplay, population=population, outcomes=outcomes, scope="historical"
        )
        canonical = pm._canonicalize_byplay_teams(byplay)
        candidate_plays, _ = r1.apply_r1(canonical, _finals(population, outcomes))
        _, cand_events = pm.build_possession_ledger(
            byplay=candidate_plays,
            population=population,
            outcomes=outcomes,
            scope="historical",
        )
        _log("baseline and candidate ledgers built", start)

    members: dict[str, list[str]] = {}
    groups = r1.changed_groups(base_events, cand_events, members_out=members)
    status = pd.read_csv(args.group_status)
    if set(status["group_id"]) != set(groups["group_id"]):
        print("gate decisions do not match the recomputed groups", file=sys.stderr)
        return 2
    decisions = adm.build_decisions(status, members)
    admitted = adm.build_admitted_events(base_events, cand_events, decisions, members)
    counts = {k: int(v) for k, v in decisions["decision"].value_counts().items()}
    _log(f"decisions {counts}; admitted ledger {len(admitted)} events", start)
    if (
        args.expected_admitted is not None
        and counts.get(adm.ADMITTED) != args.expected_admitted
    ):
        print(f"admitted {counts.get(adm.ADMITTED)} != expected", file=sys.stderr)
        return 2

    decisions.to_csv(args.output_dir / "admission_decisions.csv", index=False)
    admitted.to_parquet(args.output_dir / "admitted_events.parquet")

    # v1 contract dry run: convert and validate (no write outside output-dir).
    canonical = pm._canonicalize_byplay_teams(byplay)
    evidence = _evidence_ids(args.cfbd_dir, decisions)
    group_map = {
        (int(r.game_id), str(r.team), str(r.source_event_id)): r.allocation_group_id
        for r in admitted.dropna(subset=["allocation_group_id"]).itertuples()
    }
    v1_plays = canonical.copy()
    v1 = scoring_events_to_v1(
        admitted,
        v1_plays,
        finals=_finals(population, outcomes),
        source_versions={"repair_manifest": args.repair_manifest_uri},
        rule_version="baseline_v1",
        groups=group_map,
        admitted_evidence=evidence,
        admitted_rule_version=adm.RULE_VERSION,
    )
    v1_problems = gold.scoring_ledger_problems(v1)
    v1.to_parquet(args.output_dir / "admitted_ledger_v1.parquet")
    _log(f"v1 conversion: {len(v1)} rows, {len(v1_problems)} contract problems", start)

    by = decisions.assign(
        points=decisions["net_points"].where(decisions["net_points"] > 0, 0.0)
    )
    delta = {
        "by_decision": counts,
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
        "materiality": _materiality(base_events, admitted, possessions),
    }
    report = {
        "delta": delta,
        "v1_contract_problems": v1_problems[:20],
        "v1_contract_problem_count": len(v1_problems),
        "verifier": None,
    }
    if not args.skip_verifier:
        _log("independent verifier starting", start)
        report["verifier"] = verifier.verify_admitted_ledger(
            byplay=byplay,
            population=population,
            outcomes=outcomes,
            baseline_events=base_events,
            admitted_events=admitted,
            decisions=decisions,
            expected_admitted_groups=args.expected_admitted,
        )
        _log(f"verifier ok={report['verifier']['ok']}", start)
    (args.output_dir / "admission_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str)
    )
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    ok = not v1_problems and (args.skip_verifier or report["verifier"]["ok"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
