import glob
import sys

import pandas as pd

S = sys.argv[1]
sixb = pd.read_parquet(
    glob.glob(
        "artifacts/rebuild/6b-replay-w5-20261008-r1/stages/predictions/artifacts/**/predictions.parquet",
        recursive=True,
    )[0]
)
print("6B columns:", list(sixb.columns))


def load(tag):
    parts = [
        pd.read_csv(p)
        for p in sorted(glob.glob(f"{S}/t7/fc_{tag}/week=*/predictions.csv"))
    ]
    return pd.concat(parts, ignore_index=True)


for tag in ("b1", "b2"):
    f = load(tag)
    if tag == "b1":
        print("forecast columns:", list(f.columns))
    key = [c for c in ("game_id", "target") if c in f.columns and c in sixb.columns]
    m = f.merge(sixb, on=key, suffixes=("_f", "_6b"), validate="one_to_one")
    num = [
        c
        for c in f.columns
        if c not in key and c + "_6b" in m.columns and pd.api.types.is_float_dtype(f[c])
    ]
    worst = {c: float((m[c + "_f"] - m[c + "_6b"]).abs().max()) for c in num}
    print(
        tag,
        "rows",
        len(f),
        "matched",
        len(m),
        "max abs diff by numeric column:",
        {k: round(v, 6) for k, v in worst.items()},
    )
    if "mean" in worst:
        for t in ("margin", "total"):
            sel = m[m["target"] == t]
            d = (sel["mean_f"] - sel["mean_6b"]).abs()
            print(
                f"   {t}: mean|Δ|={d.mean():.3f} max|Δ|={d.max():.3f} games with |Δ|>1: {(d > 1).sum()} of {len(sel)}"
            )
