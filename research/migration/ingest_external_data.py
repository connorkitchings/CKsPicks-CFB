#!/usr/bin/env python3
"""Ingest external data into cloud storage (R2)."""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cks_picks_cfb.data.external_ratings import ExternalRatingsIngester
from cks_picks_cfb.data.rankings import RankingsIngester
from cks_picks_cfb.data.recruiting import RecruitingIngester
from cks_picks_cfb.data.storage import get_storage


def main():
    storage = get_storage()
    print(f"Using storage: {storage.root()}")
    print("=" * 60)

    years = [2019, 2021, 2022, 2023, 2024, 2025]

    # 1. Ingest external ratings (SP+/FPI/SRS)
    print("\n1. Ingesting External Ratings (SP+/FPI/SRS)...")
    for year in years:
        try:
            ingester = ExternalRatingsIngester(
                year=year, rating_type="all", storage=storage
            )
            data = ingester.fetch_data()
            transformed = ingester.transform_data(data)
            ingester.ingest_data(transformed)
            print(f"   {year}: ✓ {len(transformed)} ratings")
        except Exception as e:
            print(f"   {year}: ✗ Error - {e}")

    # 2. Ingest recruiting data
    print("\n2. Ingesting Recruiting Data...")
    for year in years:
        try:
            ingester = RecruitingIngester(year=year, storage=storage)
            data = ingester.fetch_data()
            transformed = ingester.transform_data(data)
            ingester.ingest_data(transformed)
            print(f"   {year}: ✓ {len(transformed)} teams")
        except Exception as e:
            print(f"   {year}: ✗ Error - {e}")

    # 3. Ingest rankings (AP/Coaches polls)
    print("\n3. Ingesting Rankings Data...")
    for year in years:
        try:
            ingester = RankingsIngester(year=year, storage=storage)
            data = ingester.fetch_data()
            transformed = ingester.transform_data(data)
            ingester.ingest_data(transformed)
            print(f"   {year}: ✓ {len(transformed)} rankings")
        except Exception as e:
            print(f"   {year}: ✗ Error - {e}")

    print("\n" + "=" * 60)
    print("Ingestion complete!")


if __name__ == "__main__":
    main()
