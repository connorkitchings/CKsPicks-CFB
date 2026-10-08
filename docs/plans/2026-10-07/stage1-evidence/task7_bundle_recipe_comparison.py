import json
import sys

sys.path.insert(0, "src")
from dotenv import load_dotenv

load_dotenv()
from cks_picks_cfb.data.storage import get_storage  # noqa: E402

st = get_storage(environment="preview")
f80 = json.loads(
    st.read_bytes(
        "artifacts/research/data-first-football-v1/forecasts/inference/f80b63ef01211bc9679b4b65769a3f16c7302c06cfa2b7806f6b8d830f19da0b/bundle.json"
    )
)
new = json.loads(
    st.read_bytes(
        "artifacts/research/data-first-football-v1/forecasts/intended-update/runs/v5-intended-update-2026-v1/bundle.json"
    )
)
six = json.load(
    open(
        "artifacts/rebuild/6a-rebuild-w5-20261007-r2/stages/offsets_refit/artifacts/rebuild/6a/6a-rebuild-w5-20261007-r2/forecast/bundle.json"
    )
)
mine = json.load(open(sys.argv[1] + "/bundle.json"))


def d(a, b, t):
    return max(
        abs(x - y)
        for x, y in zip(
            a["targets"][t]["coefficients"], b["targets"][t]["coefficients"]
        )
    )


for t in ("margin", "total"):
    print(
        t,
        "f80b63ef(accepted forecast-v1) vs 30c4f1eb(served):",
        round(d(f80, new, t), 4),
        "| vs 6A:",
        round(d(f80, six, t), 4),
        "| served vs 6A:",
        round(d(new, six, t), 4),
        "| served vs successor-on-corrected:",
        round(d(new, mine, t), 4),
    )
print(
    "training rows served/6A/mine:",
    new["targets"]["margin"]["training_rows"],
    six["targets"]["margin"]["training_rows"],
    mine["targets"]["margin"]["training_rows"],
)
print("keys", sorted(new)[:12])
