"""Compare Weeks 0-4 rows of the new Silver versions with the pinned ones, dataset by dataset."""

import io
import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(sys.argv[1])
sys.path.insert(0, str(REPO_ROOT / "src"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")
from cks_picks_cfb.data.storage import get_storage  # noqa: E402

st = get_storage(environment="preview")


def read(dataset, version):
    return pd.read_parquet(
        io.BytesIO(
            st.read_bytes(
                f"lake/silver/dataset={dataset}/version={version}/data.parquet"
            )
        )
    )


# (dataset, pinned version, new version, key columns)
PAIRS = [
    (
        "plays",
        "eda5263ca8784698589fec77",
        "51374ea11dcdc74d84924c08",
        ["game_id", "drive_number", "play_number"],
    ),
    ("games", "31a337df6cf49f1578457ec6", "c2f7c20755fea27d6f7004c5", ["game_id"]),
    (
        "game_outcomes",
        "d9a37cf473c63d2acc9f29cc",
        "33134d76df0ec7a916faea47",
        ["game_id"],
    ),
    (
        "team_game_stats",
        "ccf56d5837da8bc7eb31b2ce",
        "3203f27739424ca2337a1c0c",
        ["game_id", "team"],
    ),
    (
        "byplay",
        "443019a9a7b6a2454a4af4ac",
        "7ad61582a5205b31c5e3474d",
        ["game_id", "drive_number", "play_number"],
    ),
    (
        "reconciled_team_game",
        "5286ae2e1beeb0e747cc9750",
        "a6f29a3f51905261d0516f83",
        ["game_id", "team"],
    ),
]
games_new = read("games", "c2f7c20755fea27d6f7004c5")
week_of = dict(zip(games_new["game_id"].astype(int), games_new["week"].astype(int)))


def same(a, b):
    if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
        return (a == b) | (a.isna() & b.isna())
    return (a.astype(str) == b.astype(str)) | (a.isna() & b.isna())


report = {}
for dataset, old_v, new_v, keys in PAIRS:
    old, new = read(dataset, old_v), read(dataset, new_v)
    for frame in (old, new):
        if "week" not in frame.columns:
            frame["week"] = frame["game_id"].astype(int).map(week_of)
        else:
            frame["week"] = frame["week"].astype("float").astype("Int64")
    old = (
        old[(old["season"].astype(int) == 2026) & (old["week"] <= 4)]
        if "season" in old
        else old[old["week"] <= 4]
    )
    new = (
        new[(new["season"].astype(int) == 2026) & (new["week"] <= 4)]
        if "season" in new
        else new[new["week"] <= 4]
    )
    meta = [c for c in old.columns if c.startswith("__")]
    cols = [c for c in old.columns if c in new.columns and c not in meta]
    o = old.sort_values(keys, kind="mergesort").reset_index(drop=True)
    n = new.sort_values(keys, kind="mergesort").reset_index(drop=True)
    entry = {
        "rows_old": len(o),
        "rows_new": len(n),
        "only_old_columns": sorted(set(old.columns) - set(new.columns) - set(meta)),
        "only_new_columns": sorted(set(new.columns) - set(old.columns) - set(meta)),
    }
    if (
        len(o) != len(n)
        or not (o[keys].astype(str).values == n[keys].astype(str).values).all()
    ):
        a = set(map(tuple, o[keys].astype(str).values))
        b = set(map(tuple, n[keys].astype(str).values))
        entry["key_mismatch"] = {"only_old": len(a - b), "only_new": len(b - a)}
        report[dataset] = entry
        continue
    neq = pd.DataFrame({c: ~same(o[c], n[c]) for c in cols})
    rows = neq.any(axis=1)
    entry["rows_differing"] = int(rows.sum())
    entry["games_with_differences"] = sorted(
        o.loc[rows, "game_id"].astype(int).unique().tolist()
    )
    entry["columns_differing"] = {c: int(neq[c].sum()) for c in cols if neq[c].sum()}
    report[dataset] = entry
json.dump(report, open(sys.argv[2], "w"), indent=1, default=str)
for k, v in report.items():
    print(
        k,
        json.dumps(
            {
                x: v[x]
                for x in v
                if x not in ("only_old_columns", "only_new_columns") or v[x]
            }
        )[:420],
    )
