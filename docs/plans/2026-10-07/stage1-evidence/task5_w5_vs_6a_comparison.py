"""Read-only comparison of the Week 5 rebuild (-r2) with the first 6A run (-r1).

Compares the staged 2026 state artifacts of the two runs and attributes every difference to
the one game whose CFBD data changed (401856660) or to a named downstream bucket.
Nothing is written except the JSON summary named by --out.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
R1, R2 = "6a-rebuild-20261004-r1", "6a-rebuild-w5-20261007-r2"
LSU_GAME = 401856660
MATERIAL = 0.05


def states(run: str) -> Path:
    return (
        REPO_ROOT
        / f"artifacts/rebuild/{run}/stages/states_2026/artifacts/rebuild/6a/{run}/states_2026"
    )


def load(run: str, name: str) -> pd.DataFrame:
    return pd.read_parquet(states(run) / f"{name}.parquet")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out: dict = {}

    pop1, pop2 = load(R1, "population"), load(R2, "population")
    ids1, ids2 = set(pop1.game_id), set(pop2.game_id)
    out["population"] = {
        "r1_games": len(ids1),
        "r2_games": len(ids2),
        "r1_not_in_r2": sorted(ids1 - ids2),
        "added_in_r2": len(ids2 - ids1),
    }
    both = pop1.merge(pop2, on="game_id", suffixes=("_1", "_2"))
    changed = {
        c: int((both[f"{c}_1"].astype(str) != both[f"{c}_2"].astype(str)).sum())
        for c in (
            "week",
            "kickoff_utc",
            "population_disposition",
            "measurement_disposition",
            "timing_class",
        )
    }
    out["population_changes_on_common_games"] = changed

    o1, o2 = load(R1, "observations"), load(R2, "observations")
    key = ["game_id", "team", "unit_role", "measurement_id"]
    m = o1.merge(o2, on=key, how="outer", suffixes=("_1", "_2"), indicator=True)
    common = m[m["_merge"] == "both"]
    value_cols = ["numerator", "denominator", "raw_value", "usable_exposure"]
    diff_mask = pd.Series(False, index=common.index)
    for c in value_cols:
        a, b = common[f"{c}_1"], common[f"{c}_2"]
        diff_mask |= ~((a == b) | (a.isna() & b.isna()))
    differing = common[diff_mask]
    out["observations"] = {
        "r1_rows": len(o1),
        "r2_rows": len(o2),
        "left_only_games": sorted(
            m.loc[m["_merge"] == "left_only", "game_id"].unique().tolist()
        ),
        "right_only_games": len(m.loc[m["_merge"] == "right_only", "game_id"].unique()),
        "common_rows": len(common),
        "common_rows_with_value_change": len(differing),
        "games_with_value_change": sorted(differing["game_id"].unique().tolist()),
        "changes_outside_lsu_game": int((differing["game_id"] != LSU_GAME).sum()),
    }
    lsu = o2[o2.game_id == LSU_GAME]
    out["lsu_game"] = {
        "game_id": LSU_GAME,
        "teams": sorted(lsu.team.unique().tolist()),
        "week": int(lsu.week.iloc[0]) if len(lsu) else None,
    }
    lsu_teams = set(out["lsu_game"]["teams"])

    p1, p2 = load(R1, "priors"), load(R2, "priors")
    pk = ["team", "unit_role"]
    pm = p1.merge(p2, on=pk, suffixes=("_1", "_2"))
    out["priors"] = {
        "rows": len(pm),
        "mean_changed": int((pm.prior_mean_1 != pm.prior_mean_2).sum()),
        "variance_changed": int((pm.prior_variance_1 != pm.prior_variance_2).sum()),
    }

    results = {}
    for name in ("pregame_roles", "current_roles", "final_roles"):
        a, b = load(R1, name), load(R2, name)
        k = (
            ["game_id", "team", "unit_role"]
            if name == "pregame_roles"
            else ["team", "unit_role"]
        )
        if name == "current_roles":
            k = ["week", "team", "unit_role"] if "week" in a.columns else k
        j = a.merge(b, on=k, suffixes=("_1", "_2"))
        j["delta"] = (j.rating_mean_2 - j.rating_mean_1).abs()
        # Rows are comparable only when both runs drew on the same cutoff.
        same_cutoff = j.cutoff_utc_1.astype(str) == j.cutoff_utc_2.astype(str)
        jj = j[same_cutoff]
        teams = jj[jj.delta > 0].team.unique()
        results[name] = {
            "joined": len(j),
            "same_cutoff_rows": int(same_cutoff.sum()),
            "rows_changed": int((jj.delta > 0).sum()),
            "rows_material": int((jj.delta > MATERIAL).sum()),
            "max_abs_delta": float(jj.delta.max()) if len(jj) else None,
            "mean_abs_delta_changed": float(jj.loc[jj.delta > 0, "delta"].mean())
            if (jj.delta > 0).any()
            else 0.0,
            "teams_changed": len(teams),
            "lsu_game_teams_changed": sorted(set(teams) & lsu_teams),
            "variance_changed_rows": int(
                (jj.rating_variance_1 != jj.rating_variance_2).sum()
            ),
            "exposure_changed_rows": int(
                (jj.usable_exposure_1 != jj.usable_exposure_2).sum()
            ),
        }
        if len(jj):
            top = jj.sort_values("delta", ascending=False).head(8)
            results[name]["top_deltas"] = [
                {"team": r.team, "role": r.unit_role, "delta": round(float(r.delta), 4)}
                for r in top.itertuples()
            ]
    out["ratings"] = results
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True, default=str))
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
