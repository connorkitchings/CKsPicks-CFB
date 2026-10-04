#!/usr/bin/env python3
"""Window 2 Step 5A: corroborate changed R1 allocation groups with retained CFBD drives.

Applies the four frozen usability checks per game and the frozen group rule
(docs/plans/2026-10-03/window2/5a-frozen-definitions.md), then computes the 25% gate.
Read-only: reads the sizing outputs, the retained CFBD responses and the pinned Silver
inputs; writes only under ``--output-dir``. No network access.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_possession_v1 import build_population
from cks_picks_cfb.data.lake import read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.preseason_features import canonical_team
from cks_picks_cfb.ratings import drive_corroboration as dc
from cks_picks_cfb.ratings import score_envelope_r1 as r1
from scripts.research.run_data_first_possession_measurements import (
    _ref,
    _repair,
    _sources,
)

GATE = 0.25


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument(
        "--sizing-dir",
        type=Path,
        required=True,
        help="Has baseline/candidate events and possessions",
    )
    parser.add_argument(
        "--cfbd-dir", type=Path, required=True, help="Has raw/ and manifest.jsonl"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    storage = get_storage(environment="preview")
    repair, _ = _repair(storage, args.repair_manifest_uri, scope="historical")
    refs = _sources(storage, repair, scope="historical")
    population = build_population(
        read_dataset(storage, _ref(repair["output_refs"]["population"])),
        scope="historical",
    )
    games = pd.concat(
        [read_dataset(storage, refs[s]["fbs_involved_games"]) for s in sorted(refs)],
        ignore_index=True,
    ).drop_duplicates("game_id")
    outcomes = pd.concat(
        [read_dataset(storage, refs[s]["game_outcomes"]) for s in sorted(refs)],
        ignore_index=True,
    ).drop_duplicates(["season", "game_id"])
    info = (
        population[["season", "game_id"]]
        .merge(
            games[
                [
                    "game_id",
                    "home_team",
                    "away_team",
                    "home_line_scores",
                    "away_line_scores",
                ]
            ],
            on="game_id",
        )
        .merge(
            outcomes[["game_id", "home_points", "away_points"]],
            on="game_id",
            how="left",
        )
    )
    info["home_team"] = info["home_team"].map(canonical_team)
    info["away_team"] = info["away_team"].map(canonical_team)

    base_events = pd.read_parquet(args.sizing_dir / "baseline_events.parquet")
    cand_events = pd.read_parquet(args.sizing_dir / "candidate_events.parquet")
    possessions = pd.read_parquet(args.sizing_dir / "baseline_possessions.parquet")
    # Groups with their touched drives; cause and channel come from the sizing run, which
    # also had the raw play stream needed for the restoration flag.
    groups = r1.changed_groups(base_events, cand_events)
    sized = pd.read_csv(args.sizing_dir / "groups.csv")
    if set(groups["group_id"]) != set(sized["group_id"]):
        raise SystemExit("recomputed group ids differ from the sizing run's groups.csv")
    groups = groups.drop(columns=["channel", "primary_cause", "net_points"]).merge(
        sized[["group_id", "channel", "primary_cause", "net_points"]], on="group_id"
    )
    groups.to_csv(args.output_dir / "groups_with_drives.csv", index=False)

    manifest = [
        json.loads(line)
        for line in (args.cfbd_dir / "manifest.jsonl").read_text().splitlines()
        if line.strip()
    ]
    rows = []
    for record in manifest:
        body = (args.cfbd_dir / "raw" / record["file"]).read_bytes()
        rows.extend(json.loads(body))
    cfbd_all = dc.parse_drives(rows, canonical_team)
    in_scope = set(info["game_id"])
    cfbd_all = cfbd_all[cfbd_all["gameId"].isin(in_scope)]
    by_game = {int(g): frame for g, frame in cfbd_all.groupby("gameId")}

    regulation = possessions[possessions["period_class"] == "regulation"]

    def _sets(frame: pd.DataFrame) -> dict[int, set[tuple[int, str]]]:
        return {
            int(g): {(int(d), str(o)) for d, o in zip(f["drive_number"], f["offense"])}
            for g, f in frame.groupby("game_id")
        }

    ledger_all = _sets(regulation)
    ledger_eligible = _sets(
        regulation[regulation["possession_eligible"].fillna(False).astype(bool)]
    )
    base_by_game = {int(g): f for g, f in base_events.groupby("game_id")}
    cand_by_game = {int(g): f for g, f in cand_events.groupby("game_id")}

    usability = []
    for row in info.itertuples(index=False):
        gid = int(row.game_id)
        drives = by_game.get(gid, pd.DataFrame())
        if pd.isna(row.home_points) or pd.isna(row.away_points):
            result = {
                "c1": False,
                "c2": False,
                "c3": False,
                "c4": False,
                "usable": False,
                "reasons": ["no_certified_final"],
            }
        else:
            result = dc.check_game(
                drives,
                home=row.home_team,
                away=row.away_team,
                final_home=float(row.home_points),
                final_away=float(row.away_points),
                home_line_scores=row.home_line_scores,
                away_line_scores=row.away_line_scores,
                ledger_regulation_all=ledger_all.get(gid, set()),
                ledger_regulation_eligible=ledger_eligible.get(gid, set()),
            )
        usability.append(
            {
                "season": int(row.season),
                "game_id": gid,
                "has_cfbd": not drives.empty,
                **{k: result[k] for k in ("c1", "c2", "c3", "c4", "usable")},
                "reasons": ";".join(result["reasons"]),
                "c2_strict": bool(result.get("c2_strict", False)),
                "non_drive_points": result.get("non_drive_points", 0),
                "c2_cfbd_not_in_ledger": result.get("c2_cfbd_not_in_ledger", 0),
                "c2_eligible_not_in_cfbd": result.get("c2_eligible_not_in_cfbd", 0),
            }
        )
    usable = pd.DataFrame(usability)
    usable.to_csv(args.output_dir / "game_usability.csv", index=False)
    usable_ids = set(usable.loc[usable["usable"], "game_id"])

    status_rows = []
    info_by_game = info.set_index("game_id")
    for g in groups.itertuples(index=False):
        gid = int(g.game_id)
        drives = by_game.get(gid, pd.DataFrame())
        home, away = (
            info_by_game.loc[gid, "home_team"],
            info_by_game.loc[gid, "away_team"],
        )
        cfbd = dc.cfbd_points_by_drive(drives, home, away) if not drives.empty else {}
        status = dc.classify_group(
            set(json.loads(g.drive_numbers)),
            g.team,
            cfbd,
            dc.ledger_points_by_drive(
                base_by_game.get(gid, pd.DataFrame(columns=base_events.columns))
            ),
            dc.ledger_points_by_drive(
                cand_by_game.get(gid, pd.DataFrame(columns=cand_events.columns))
            ),
            game_usable=gid in usable_ids,
            has_cfbd=not drives.empty,
        )
        status_if_usable = dc.classify_group(
            set(json.loads(g.drive_numbers)),
            g.team,
            cfbd,
            dc.ledger_points_by_drive(
                base_by_game.get(gid, pd.DataFrame(columns=base_events.columns))
            ),
            dc.ledger_points_by_drive(
                cand_by_game.get(gid, pd.DataFrame(columns=cand_events.columns))
            ),
            game_usable=True,
            has_cfbd=not drives.empty,
        )
        status_rows.append(
            {
                "group_id": g.group_id,
                "season": g.season,
                "game_id": gid,
                "team": g.team,
                "channel": g.channel,
                "primary_cause": g.primary_cause,
                "net_points": g.net_points,
                "status": status,
                "status_if_usable": status_if_usable,
            }
        )
    status = pd.DataFrame(status_rows)
    status.to_csv(args.output_dir / "group_status.csv", index=False)

    # Sensitivity of the gate to the usability definition. Variants that drop or tighten a
    # check are shown so the result's dependence on each operationalization is visible.
    flags = usable.set_index("game_id")
    joined = status.merge(
        flags[["has_cfbd", "c1", "c2", "c3", "c4", "c2_strict"]],
        left_on="game_id",
        right_index=True,
    )
    corroborable = joined["status_if_usable"] == "corroborated"
    variants = {
        "frozen_as_clarified (c1 and c2 and c3 and c4)": joined[
            ["c1", "c2", "c3", "c4"]
        ].all(axis=1),
        "without_c2": joined[["c1", "c3", "c4"]].all(axis=1),
        "c2_strict_equality (c1, strict c2, c3, c4)": joined["c1"]
        & joined["c2_strict"]
        & joined["c3"]
        & joined["c4"],
        "only_c3_and_c4": joined["c3"] & joined["c4"],
        "no_usability_filter (upper bound, not valid under the frozen rule)": joined[
            "has_cfbd"
        ],
    }
    sensitivity = {
        name: {
            "corroborated": int((corroborable & mask).sum()),
            "share": round(float((corroborable & mask).sum() / len(joined)), 4),
        }
        for name, mask in variants.items()
    }
    total = len(status)
    corroborated = int((status["status"] == "corroborated").sum())

    def share(frame: pd.DataFrame) -> dict:
        n = len(frame)
        c = int((frame["status"] == "corroborated").sum())
        return {"groups": n, "corroborated": c, "share": round(c / n, 4) if n else None}

    summary = {
        "gate_threshold": GATE,
        "groups": total,
        "corroborated": corroborated,
        "share": round(corroborated / total, 4) if total else None,
        "needed_for_gate": -(-total // 4),
        "sensitivity": sensitivity,
        "gate_passed": bool(total and corroborated / total >= GATE),
        "status_counts": {
            k: int(v) for k, v in status["status"].value_counts().items()
        },
        "by_season": {int(s): share(f) for s, f in status.groupby("season")},
        "by_primary_cause": {
            str(c): share(f) for c, f in status.groupby("primary_cause")
        },
        "by_channel": {str(c): share(f) for c, f in status.groupby("channel")},
        "points_recovered_total": float(
            status.loc[status["net_points"] > 0, "net_points"].sum()
        ),
        "points_recovered_corroborated": float(
            status.loc[
                (status["net_points"] > 0) & (status["status"] == "corroborated"),
                "net_points",
            ].sum()
        ),
        "games": {
            "in_scope": len(usable),
            "with_cfbd_drives": int(usable["has_cfbd"].sum()),
            "usable": int(usable["usable"].sum()),
            "usable_share_by_season": {
                int(s): round(float(f["usable"].mean()), 4)
                for s, f in usable.groupby("season")
            },
            "check_pass_counts": {
                c: int(usable[c].sum()) for c in ("c1", "c2", "c3", "c4")
            },
            "c2_strict_equality_pass": int(usable["c2_strict"].sum()),
            "games_with_non_drive_points": int((usable["non_drive_points"] != 0).sum()),
            "changed_games": int(groups["game_id"].nunique()),
            "changed_games_usable": int(
                groups["game_id"].drop_duplicates().isin(usable_ids).sum()
            ),
        },
        "unusable_reason_counts": {
            k: int(v)
            for k, v in usable.loc[~usable["usable"], "reasons"]
            .str.split(";")
            .explode()
            .value_counts()
            .head(25)
            .items()
        },
        "cfbd_manifest_files": len(manifest),
        "cfbd_drive_rows": int(len(cfbd_all)),
    }
    (args.output_dir / "corroboration_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
