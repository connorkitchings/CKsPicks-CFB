import pandas as pd

R = "artifacts/rebuild/6a-rebuild-w5-20261007-r2/stages/states_2026/artifacts/rebuild/6a/6a-rebuild-w5-20261007-r2/states_2026/"
L = __import__("sys").argv[1]
for mine, theirs in (
    ("priors", "priors"),
    ("pregame_roles", "pregame_roles"),
    ("pregame_teams", "pregame_teams"),
    ("current_roles", "current_roles"),
    ("current_teams", "current_teams"),
):
    a, b = (
        pd.read_parquet(f"{L}/{mine}.parquet"),
        pd.read_parquet(R + f"{theirs}.parquet"),
    )
    cols = [c for c in a.columns if c in b.columns]
    key = [c for c in ("season", "week", "game_id", "team", "unit_role") if c in cols]
    if mine == "priors":
        key = ["team", "unit_role"]
    m = a.merge(b, on=key, suffixes=("_a", "_b"), how="outer", indicator=True)
    both = m[m["_merge"] == "both"]
    num = [c for c in cols if c not in key and pd.api.types.is_float_dtype(a[c])]
    worst = (
        max((both[c + "_a"] - both[c + "_b"]).abs().max() for c in num) if num else 0.0
    )
    print(
        f"{mine:15s} rows mine={len(a)} 6A={len(b)} matched={len(both)} left_only={(m['_merge'] == 'left_only').sum()} right_only={(m['_merge'] == 'right_only').sum()} max|diff|={worst}"
    )
