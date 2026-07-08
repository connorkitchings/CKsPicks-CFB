import os
import sys
from pathlib import Path

import cfbd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()
CFBD_API_KEY = os.getenv("CFBD_API_KEY")


def main():
    if not CFBD_API_KEY:
        print("Error: CFBD_API_KEY not found in environment.")
        return

    print("Fetching venues from CFBD...")
    config = cfbd.Configuration(access_token=CFBD_API_KEY)

    api = cfbd.VenuesApi(cfbd.ApiClient(config))
    venues = api.get_venues()

    data = []
    for v in venues:
        data.append(
            {
                "id": v.id,
                "name": v.name,
                "city": v.city,
                "state": v.state,
                "zip": v.zip,
                "country_code": v.country_code,
                "timezone": v.timezone,
                "latitude": getattr(v, "latitude", None),
                "longitude": getattr(v, "longitude", None),
                "elevation": v.elevation,
                "grass": v.grass,
                "dome": v.dome,
            }
        )

    df = pd.DataFrame(data)

    from cks_picks_cfb.config import DATA_ROOT

    data_root = Path(
        os.getenv("CFB_DATA_ROOT") or os.getenv("CFB_MODEL_DATA_ROOT") or str(DATA_ROOT)
    )
    out_path = data_root / "stadiums.csv"

    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} venues to {out_path}")


if __name__ == "__main__":
    main()
