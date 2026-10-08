import glob
import sys

import pandas as pd

S = sys.argv[1]
served = pd.read_parquet(
    glob.glob(
        "artifacts/rebuild/6b-replay-w5-20261008-r1/stages/old_grade_reproduction/artifacts/**/predictions.parquet",
        recursive=True,
    )[0]
)
print("served columns:", list(served.columns)[:16], len(served))


def load(tag):
    return pd.concat(
        [
            pd.read_csv(p)
            for p in sorted(glob.glob(f"{S}/t7/fc_{tag}/week=*/predictions.csv"))
        ],
        ignore_index=True,
    )


six = pd.read_parquet(
    glob.glob(
        "artifacts/rebuild/6b-replay-w5-20261008-r1/stages/predictions/artifacts/**/predictions.parquet",
        recursive=True,
    )[0]
)
cols = [
    c
    for c in served.columns
    if c.lower()
    in (
        "predicted_spread",
        "spread prediction",
        "predicted_margin",
        "pred_margin",
        "total prediction",
        "predicted_total",
    )
]
print("candidate served numeric columns:", cols)
for tag in ("b1", "b2"):
    f = load(tag)
    marg = f[f.target == "margin"].set_index("game_id")["mean"]
    tot = f[f.target == "total"].set_index("game_id")["mean"]
    sv = served.set_index("game_id")
    sign = (
        1
        if (marg - sv.predicted_spread).abs().mean()
        < (marg + sv.predicted_spread).abs().mean()
        else -1
    )
    dm = (sign * marg - sv.predicted_spread).abs()
    dt = (tot - sv.predicted_total).abs()
    flips = ((sign * marg > 0) != (sv.predicted_spread > 0)).sum()
    print(
        f"{tag} vs SERVED: margin mean|Δ|={dm.mean():.3f} max={dm.max():.3f} >1pt: {(dm > 1).sum()} | total mean|Δ|={dt.mean():.3f} max={dt.max():.3f} >1pt: {(dt > 1).sum()} | sign(win-side) differs: {flips} of {len(sv)} (sign convention {sign})"
    )
