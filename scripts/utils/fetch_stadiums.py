import os
import sys
from pathlib import Path

import cfbd
import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())
# noqa: E402
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

    # Save to data root
    data_root = Path("/Volumes/CK SSD/Coding Projects/cfb_model/")
    out_path = data_root / "stadiums.csv"

    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} venues to {out_path}")


if __name__ == "__main__":
    main()
