import os

import pandas as pd

R1, R2 = "6a-rebuild-20261004-r1", "6a-rebuild-w5-20261007-r2"
LSU = 401856660


def sd(run):
    return f"artifacts/rebuild/{run}/stages/states_2026/artifacts/rebuild/6a/{run}/states_2026/"


a, b = (
    pd.read_parquet(sd(R1) + "pregame_roles.parquet"),
    pd.read_parquet(sd(R2) + "pregame_roles.parquet"),
)
j = a.merge(b, on=["game_id", "team", "unit_role"], suffixes=("_1", "_2"))
odd = j[j.cutoff_utc_1.astype(str) != j.cutoff_utc_2.astype(str)]
print("pregame rows with moved cutoff:", len(odd))
print(
    odd[
        [
            "game_id",
            "team",
            "unit_role",
            "cutoff_utc_1",
            "cutoff_utc_2",
            "rating_mean_1",
            "rating_mean_2",
        ]
    ].to_string()
)
o = pd.read_parquet(sd(R2) + "observations.parquet")
print(
    "LSU-game observation rows:",
    int((o.game_id == LSU).sum()),
    sorted(o[o.game_id == LSU].unit_role.unique()),
)


def silver(run, ds):
    base = f"artifacts/rebuild/{run}/stages/silver_2026/artifacts/lake/silver/dataset={ds}/"
    v = os.listdir(base)[0]
    return pd.read_parquet(base + v + "/data.parquet")


for ds, key in (
    ("byplay", ["game_id", "drive_number", "play_number"]),
    ("reconciled_team_game", ["game_id", "team"]),
):
    x, y = silver(R1, ds), silver(R2, ds)
    x = x[x.game_id.isin(set(y.game_id))]
    m = x.merge(y, on=key, how="outer", suffixes=("_1", "_2"), indicator=True)
    c = m[m["_merge"] == "both"]
    cols = [
        col[:-2]
        for col in c.columns
        if col.endswith("_1") and col[:-2] + "_2" in c.columns
    ]
    dif = {}
    for col in cols:
        p, q = c[col + "_1"], c[col + "_2"]
        bad = ~((p == q) | (p.isna() & q.isna()))
        if bad.any():
            dif[col] = (
                int(bad.sum()),
                int(c.loc[bad, "game_id"].nunique()),
                int((c.loc[bad, "game_id"] == LSU).sum()),
            )
    print(
        ds,
        "unmatched left/right games:",
        sorted(m[m["_merge"] == "left_only"].game_id.unique().tolist())[:5],
        sorted(m[m["_merge"] == "right_only"].game_id.unique().tolist())[:5],
    )
    print(
        "   differing columns (rows, games, rows_in_LSU_game):",
        {k: dif[k] for k in sorted(dif, key=lambda k: -dif[k][0])[:12]},
    )
