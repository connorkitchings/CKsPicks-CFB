import os
import sys

# Add project root to path
sys.path.append(os.getcwd())
# noqa: E402
from cks_picks_cfb.config import get_data_root
from cks_picks_cfb.features.persist import persist_preaggregations


def main():
    year = 2025
    data_root = str(get_data_root())

    print(f"Running pre-aggregation pipeline for {year}...")
    print(f"Data Root: {data_root}")

    totals = persist_preaggregations(year=year, data_root=data_root, verbose=True)

    print("Pipeline complete.")
    print(totals)


if __name__ == "__main__":
    main()
