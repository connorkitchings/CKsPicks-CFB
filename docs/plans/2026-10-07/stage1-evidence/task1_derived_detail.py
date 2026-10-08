import io
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(sys.argv[1])
sys.path.insert(0, str(REPO_ROOT / "src"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")
from cks_picks_cfb.data.storage import get_storage  # noqa: E402

st = get_storage(environment="preview")


def rd(dataset, version):
    key = f"lake/silver/dataset={dataset}/version={version}/data.parquet"
    return pd.read_parquet(io.BytesIO(st.read_bytes(key)))


def same(a, b):
    if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
        return (a == b) | (a.isna() & b.isna())
    return (a.astype(str) == b.astype(str)) | (a.isna() & b.isna())


out = {}
# byplay: outer merge on key, weeks 0-4
ob, nb = (
    rd("byplay", "443019a9a7b6a2454a4af4ac"),
    rd("byplay", "7ad61582a5205b31c5e3474d"),
)
keys = ["game_id", "drive_number", "play_number"]
nb = nb[nb.week <= 4]
m = ob.merge(nb, on=keys, how="outer", suffixes=("_o", "_n"), indicator=True)
unmatched = m[m._merge != "both"]
print(
    "byplay unmatched keys:", unmatched[keys + ["_merge"]].astype(str).values.tolist()
)
both = m[m._merge == "both"]
cols = [
    c
    for c in ob.columns
    if c not in keys and not c.startswith("__") and c + "_n" in m.columns
]
diff = {c: int((~same(both[c + "_o"], both[c + "_n"])).sum()) for c in cols}
diff = {c: v for c, v in diff.items() if v}
rows = pd.concat([~same(both[c + "_o"], both[c + "_n"]) for c in cols], axis=1).any(
    axis=1
)
print(
    "byplay matched rows:",
    len(both),
    "| rows differing:",
    int(rows.sum()),
    "| games:",
    both.loc[rows, "game_id"].nunique(),
)
print("byplay columns differing:", diff)
print(
    "byplay games with differences (first 8):",
    sorted(both.loc[rows, "game_id"].astype(int).unique().tolist())[:8],
)
# reconciled_team_game
orc, nrc = (
    rd("reconciled_team_game", "5286ae2e1beeb0e747cc9750"),
    rd("reconciled_team_game", "a6f29a3f51905261d0516f83"),
)
nrc = nrc[nrc.week <= 4] if "week" in nrc else nrc
k2 = ["game_id", "team"]
mm = orc.merge(nrc, on=k2, how="inner", suffixes=("_o", "_n"))
c2 = [
    c
    for c in orc.columns
    if c not in k2 and not c.startswith("__") and c + "_n" in mm.columns
]
d2 = {c: int((~same(mm[c + "_o"], mm[c + "_n"])).sum()) for c in c2}
print(
    "team_game rows matched:",
    len(mm),
    "| columns differing:",
    {c: v for c, v in d2.items() if v},
)
print(
    "team_game only-new columns:",
    sorted(set(nrc.columns) - set(orc.columns)),
    "| only-old:",
    sorted(set(orc.columns) - set(nrc.columns)),
)
