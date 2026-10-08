import io
import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")
from cks_picks_cfb.data.storage import get_storage  # noqa: E402

st = get_storage(environment="preview")


def rd(uri):
    return pd.read_parquet(io.BytesIO(st.read_bytes(uri)))


old = rd("lake/silver/dataset=plays/version=eda5263ca8784698589fec77/data.parquet")
new = rd("lake/silver/dataset=plays/version=46a62d343b18473fc26caf70/data.parquet")
keys = ["game_id", "drive_number", "play_number"]
meta = [c for c in old.columns if c.startswith("__")]
cols = [c for c in old.columns if c not in meta]
o = old[old.week <= 4].sort_values(keys, kind="mergesort").reset_index(drop=True)
n = new[new.week <= 4].sort_values(keys, kind="mergesort").reset_index(drop=True)


def same(a, b):
    if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
        return (a == b) | (a.isna() & b.isna())
    return (a.astype(str) == b.astype(str)) | (a.isna() & b.isna())


neq = pd.DataFrame({c: ~same(o[c], n[c]) for c in cols})
rows = neq.any(axis=1)
print(
    "rows differing (NaN-aware):",
    int(rows.sum()),
    "| games:",
    sorted(o[rows].game_id.astype(int).unique().tolist()),
    "| weeks:",
    sorted(o[rows].week.astype(int).unique().tolist()),
)
print(
    "differing cells per column:", {c: int(neq[c].sum()) for c in cols if neq[c].sum()}
)
capold = old[old.week <= 4].groupby("week")["__capture_id"].nunique().to_dict()
capnew = new[new.week <= 4].groupby("week")["__capture_id"].nunique().to_dict()
print("capture ids per week old:", capold, "new:", capnew)
w1old = set(old[old.week == 1]["__capture_id"])
w1new = set(new[new.week == 1]["__capture_id"])
print(
    "week 1 capture ids old:", [x[:10] for x in w1old], "new:", [x[:10] for x in w1new]
)
out = {
    "rows_differing": int(rows.sum()),
    "games": sorted(o[rows].game_id.astype(int).unique().tolist()),
    "cells_by_column": {c: int(neq[c].sum()) for c in cols if neq[c].sum()},
    "week1_capture_old": sorted(w1old),
    "week1_capture_new": sorted(w1new),
    "rows": [
        {k: (None if pd.isna(o.at[i, k]) else str(o.at[i, k])) for k in keys}
        for i in o[rows].index
    ],
}
json.dump(out, open(sys.argv[1], "w"), indent=1)
