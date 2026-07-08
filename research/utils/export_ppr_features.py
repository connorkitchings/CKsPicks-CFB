import glob
import os

import pandas as pd


def main():
    print("Aggregating PPR predictions...")

    # Pattern: artifacts/predictions/{year}/week_{week}_ratings_preds.csv
    files = glob.glob("artifacts/predictions/*/*_ratings_preds.csv")

    if not files:
        print("No prediction files found.")
        return

    print(f"Found {len(files)} files.")

    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            # Ensure required columns exist
            req_cols = [
                "game_id",
                "home_rating",
                "away_rating",
                "pred_spread",
                "pred_total",
            ]
            if all(c in df.columns for c in req_cols):
                # Rename for clarity
                df = df[req_cols].rename(
                    columns={
                        "home_rating": "ppr_home_rating",
                        "away_rating": "ppr_away_rating",
                        "pred_spread": "ppr_predicted_spread",
                        "pred_total": "ppr_predicted_total",
                    }
                )
                dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    if not dfs:
        print("No valid data found.")
        return

    all_ppr = pd.concat(dfs, ignore_index=True)

    # Deduplicate by game_id (taking the latest prediction if duplicates exist)
    # Actually, backfill should be unique per game_id usually, but let's be safe
    all_ppr = all_ppr.drop_duplicates(subset=["game_id"])

    output_path = "data/processed/ppr_features.csv"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    all_ppr.to_csv(output_path, index=False)
    print(f"Saved {len(all_ppr)} rows to {output_path}")


if __name__ == "__main__":
    main()
