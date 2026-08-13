import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

# Add project root to sys.path
sys.path.append(os.getcwd())

from cks_picks_cfb.artifacts import local_prediction_path


def format_cfbd_pickem_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Transform prediction DataFrame into CFBD Model Pick'em format.

    CFBD Pick'em expects:
    - game_id / gameId: Integer CFBD game identifier
    - home_team: Home team name
    - away_team: Away team name
    - projected_margin / margin: Home team projected margin (home_score - away_score)
    - projected_total: Optional total points prediction
    """
    df_out = pd.DataFrame()

    # Match game identifier
    if "game_id" in df.columns:
        df_out["game_id"] = df["game_id"].astype(int)
    elif "id" in df.columns:
        df_out["game_id"] = df["id"].astype(int)
    else:
        raise KeyError("Input DataFrame missing 'game_id' or 'id' column.")

    df_out["gameId"] = df_out["game_id"]

    # Match team names
    if "Home Team" in df.columns:
        df_out["home_team"] = df["Home Team"]
    elif "home_team" in df.columns:
        df_out["home_team"] = df["home_team"]
    else:
        raise KeyError("Input DataFrame missing 'Home Team' or 'home_team' column.")

    if "Away Team" in df.columns:
        df_out["away_team"] = df["Away Team"]
    elif "away_team" in df.columns:
        df_out["away_team"] = df["away_team"]
    else:
        raise KeyError("Input DataFrame missing 'Away Team' or 'away_team' column.")

    # Match margin / spread prediction
    # Note: In our model, spread_target = home_score - away_score.
    # Positive spread prediction means Home win margin.
    if "Spread Prediction" in df.columns:
        df_out["projected_margin"] = df["Spread Prediction"].round(2)
    elif "spread_prediction" in df.columns:
        df_out["projected_margin"] = df["spread_prediction"].round(2)
    elif "projected_margin" in df.columns:
        df_out["projected_margin"] = df["projected_margin"].round(2)
    else:
        raise KeyError(
            "Input DataFrame missing 'Spread Prediction' or 'projected_margin' column."
        )

    df_out["margin"] = df_out["projected_margin"]

    # Optional projected total
    if "Total Prediction" in df.columns:
        df_out["projected_total"] = df["Total Prediction"].round(2)
    elif "total_prediction" in df.columns:
        df_out["projected_total"] = df["total_prediction"].round(2)
    elif "projected_total" in df.columns:
        df_out["projected_total"] = df["projected_total"].round(2)

    return df_out


def build_api_payload(pickem_df: pd.DataFrame) -> list[dict]:
    """Build list of dict objects for CFBD Pick'em API POST request.

    Payload format expected by CFBD Model Pick'em /api/picks:
    [
        {"gameId": 401636830, "margin": 14.5}, ...
    ]
    """
    payload = []
    for _, row in pickem_df.iterrows():
        item = {
            "gameId": int(row["game_id"]),
            "margin": float(row["projected_margin"]),
        }
        if "projected_total" in row and pd.notna(row["projected_total"]):
            item["projectedTotal"] = float(row["projected_total"])
        payload.append(item)
    return payload


def submit_picks_to_api(payload: list[dict], api_key: str, api_url: str) -> dict:
    """Submit predictions payload to CFBD Pick'em API."""
    if not api_key:
        raise ValueError(
            "CFBD_API_KEY environment variable is required to submit picks to API."
        )

    json_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=json_data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "CFB-Model-Pickem-Exporter/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            result = json.loads(body) if body else {}
            print(
                f"✅ Successfully submitted {len(payload)} picks to CFBD Pick'em API (HTTP {status})."
            )
            return {"status": status, "response": result}
    except urllib.error.HTTPError as err:
        error_body = err.read().decode("utf-8") if err.fp else str(err)
        print(f"❌ API Submission failed with HTTP {err.code}: {error_body}")
        raise RuntimeError(f"CFBD Pick'em API error {err.code}: {error_body}") from err


def main():
    parser = argparse.ArgumentParser(
        description="Export weekly predictions formatted for CFBD 2026 Model Pick'em contest."
    )
    parser.add_argument(
        "--year", type=int, default=2026, help="Season year (default 2026)"
    )
    parser.add_argument("--week", type=int, default=0, help="Week number (default 0)")
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=None,
        help="Input predictions CSV path (defaults to local_prediction_path(year, week))",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Output Pick'em CSV path (defaults to artifacts/preview/pickem/cfbd_pickem_<year>_w<week>.csv)",
    )
    parser.add_argument(
        "--submit-api",
        action="store_true",
        help="Submit formatted picks directly to CFBD Pick'em API",
    )
    parser.add_argument(
        "--api-url",
        default="https://predictions.collegefootballdata.com/api/picks",
        help="CFBD Pick'em API endpoint URL",
    )
    args = parser.parse_args()

    input_path = args.input_csv
    if input_path is None:
        candidate_paths = [
            local_prediction_path(args.year, args.week),
            Path(
                f"data/production/predictions/{args.year}/CFB_week{args.week}_bets.csv"
            ),
            Path(
                f"artifacts/production/predictions/year={args.year}/CFB_week{args.week}_bets.csv"
            ),
            Path(
                f"artifacts/preview/predictions/year={args.year}/CFB_week{args.week}_bets.csv"
            ),
        ]
        for candidate in candidate_paths:
            if candidate.exists():
                input_path = candidate
                break
        if input_path is None:
            input_path = candidate_paths[0]

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input predictions file not found: {input_path}. "
            f"Run 'make publish-week YEAR={args.year} WEEK={args.week}' or generate predictions first."
        )

    print(f"Reading predictions from {input_path}...")
    df_raw = pd.read_csv(input_path)
    pickem_df = format_cfbd_pickem_dataframe(df_raw)

    output_path = args.output_csv or Path(
        f"artifacts/preview/pickem/cfbd_pickem_{args.year}_w{args.week}.csv"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pickem_df.to_csv(output_path, index=False)
    print(f"✅ Exported CFBD Pick'em CSV ({len(pickem_df)} games) to {output_path}")

    if args.submit_api:
        api_key = os.getenv("CFBD_API_KEY")
        payload = build_api_payload(pickem_df)
        print(f"Submitting {len(payload)} picks to {args.api_url}...")
        submit_picks_to_api(payload, api_key=api_key, api_url=args.api_url)


if __name__ == "__main__":
    main()
