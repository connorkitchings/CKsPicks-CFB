"""Export and submit validated CFBD Model Pick'em projections.

The Model Pick'em service is separate from the regular CFBD data API.  It
uses a short-lived prediction token and accepts one ``{gameId, pick}`` payload
per contest game.  We intentionally submit only game IDs produced by the
validated FBS-vs-FBS model; unsupported contest games are reported, never
filled with synthetic predictions.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from cks_picks_cfb.artifacts import local_prediction_path

PICKEM_API_URL = "https://predictionsapi.collegefootballdata.com/api/picks"
PREDICTION_TOKEN_ENV = "CFBD_PREDICTION_TOKEN"


@dataclass(frozen=True)
class PickemReconciliation:
    """Exact game-ID reconciliation between model output and contest slate."""

    matched_game_ids: tuple[int, ...]
    unsupported_contest_game_ids: tuple[int, ...]
    unavailable_model_game_ids: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched_game_ids": list(self.matched_game_ids),
            "unsupported_contest_game_ids": list(self.unsupported_contest_game_ids),
            "unavailable_model_game_ids": list(self.unavailable_model_game_ids),
            "matched_count": len(self.matched_game_ids),
            "unsupported_contest_count": len(self.unsupported_contest_game_ids),
            "unavailable_model_count": len(self.unavailable_model_game_ids),
        }


def format_cfbd_pickem_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize model output into the Pick'em CSV contract.

    ``pick`` is the model's home-team projected margin (home score minus away
    score), matching the provider's documented API field.  Totals are kept out
    of the submission contract because the contest endpoint accepts margin picks
    only.
    """
    if "game_id" in df:
        game_ids = df["game_id"]
    elif "id" in df:
        game_ids = df["id"]
    elif "gameId" in df:
        game_ids = df["gameId"]
    else:
        raise KeyError("Input DataFrame missing 'game_id', 'id', or 'gameId' column.")
    if "Spread Prediction" in df:
        margin = df["Spread Prediction"]
    elif "spread_prediction" in df:
        margin = df["spread_prediction"]
    elif "projected_margin" in df:
        margin = df["projected_margin"]
    elif "predicted_spread" in df:
        margin = df["predicted_spread"]
    elif "pick" in df:
        # Permit an already exported, reviewable Pick'em CSV to be the exact
        # input for later authenticated reconciliation and submission.
        margin = df["pick"]
    else:
        raise KeyError("Input DataFrame missing a projected home margin column.")

    output = pd.DataFrame(
        {
            "gameId": pd.to_numeric(game_ids, errors="raise").astype(int),
            "pick": pd.to_numeric(margin, errors="raise").round(2),
        }
    )
    for output_column, candidates in {
        "home_team": ("Home Team", "home_team"),
        "away_team": ("Away Team", "away_team"),
    }.items():
        for column in candidates:
            if column in df:
                output[output_column] = df[column]
                break
    if output["gameId"].duplicated().any():
        raise ValueError("Input predictions contain duplicate game IDs.")
    if output["pick"].isna().any():
        raise ValueError("Input predictions contain missing projected margins.")
    return output


def build_api_payload(pickem_df: pd.DataFrame) -> list[dict[str, float | int]]:
    """Return one documented Model Pick'em request body per game."""
    required = {"gameId", "pick"}
    missing = sorted(required - set(pickem_df.columns))
    if missing:
        raise KeyError(f"Pick'em frame is missing columns: {missing}")
    return [
        {"gameId": int(row.gameId), "pick": float(row.pick)}
        for row in pickem_df.loc[:, ["gameId", "pick"]].itertuples(index=False)
    ]


def _request(
    api_url: str,
    token: str,
    *,
    method: str,
    payload: dict[str, float | int] | None = None,
) -> Any:
    if not token:
        raise ValueError(f"{PREDICTION_TOKEN_ENV} is required for CFBD Model Pick'em.")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        api_url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "CKsPicks-CFB/2026",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8") if error.fp else str(error)
        raise RuntimeError(
            f"CFBD Model Pick'em API error {error.code}: {detail}"
        ) from error


def fetch_pickem_games(
    token: str, api_url: str = PICKEM_API_URL
) -> list[dict[str, Any]]:
    """Fetch the authenticated contest slate without mutating any picks."""
    response = _request(api_url, token, method="GET")
    if not isinstance(response, list):
        raise RuntimeError(
            "CFBD Model Pick'em GET /api/picks returned a non-list response."
        )
    return [dict(item) for item in response]


def reconcile_pickem_games(
    pickem_df: pd.DataFrame, contest_games: Iterable[dict[str, Any]]
) -> PickemReconciliation:
    """Match model and contest slate strictly by the provider game ID."""
    model_ids = {int(game_id) for game_id in pickem_df["gameId"]}
    contest_ids = {
        int(item["id"]) for item in contest_games if item.get("id") is not None
    }
    return PickemReconciliation(
        matched_game_ids=tuple(sorted(model_ids & contest_ids)),
        unsupported_contest_game_ids=tuple(sorted(contest_ids - model_ids)),
        unavailable_model_game_ids=tuple(sorted(model_ids - contest_ids)),
    )


def submit_picks_to_api(
    payload: Iterable[dict[str, float | int]],
    token: str,
    api_url: str = PICKEM_API_URL,
    *,
    request_delay_seconds: float = 0.25,
) -> list[Any]:
    """Submit already-reconciled picks one at a time, with bounded pacing."""
    items = list(payload)
    responses = []
    for index, item in enumerate(items):
        if set(item) != {"gameId", "pick"}:
            raise ValueError(
                "Each Pick'em request must contain exactly gameId and pick."
            )
        responses.append(_request(api_url, token, method="POST", payload=dict(item)))
        if request_delay_seconds and index < len(items) - 1:
            time.sleep(request_delay_seconds)
    return responses


def _input_path(year: int, week: int, supplied: Path | None) -> Path:
    if supplied is not None:
        return supplied
    candidates = (
        local_prediction_path(year, week),
        Path(f"data/production/predictions/{year}/CFB_week{week}_bets.csv"),
        Path(f"artifacts/production/predictions/year={year}/CFB_week{week}_bets.csv"),
        Path(f"artifacts/preview/predictions/year={year}/CFB_week{week}_bets.csv"),
    )
    return next((path for path in candidates if path.exists()), candidates[0])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--week", type=int, default=0)
    parser.add_argument("--input-csv", type=Path)
    parser.add_argument("--output-csv", type=Path)
    parser.add_argument("--validate-api", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--submit-api", action="store_true")
    parser.add_argument("--api-url", default=PICKEM_API_URL)
    parser.add_argument("--request-delay-seconds", type=float, default=0.25)
    args = parser.parse_args()

    input_path = _input_path(args.year, args.week, args.input_csv)
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input predictions file not found: {input_path}. Generate a validated run first."
        )
    pickem_df = format_cfbd_pickem_dataframe(pd.read_csv(input_path))
    output_path = args.output_csv or Path(
        f"artifacts/preview/pickem/cfbd_pickem_{args.year}_w{args.week}.csv"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pickem_df.to_csv(output_path, index=False)
    print(f"Exported {len(pickem_df)} Model Pick'em rows to {output_path}")

    if not (args.validate_api or args.dry_run or args.submit_api):
        return
    token = os.getenv(PREDICTION_TOKEN_ENV, "")
    contest_games = fetch_pickem_games(token, args.api_url)
    reconciliation = reconcile_pickem_games(pickem_df, contest_games)
    print(json.dumps(reconciliation.to_dict(), indent=2, sort_keys=True))
    if args.dry_run or not args.submit_api:
        return
    matched = pickem_df[pickem_df["gameId"].isin(reconciliation.matched_game_ids)]
    responses = submit_picks_to_api(
        build_api_payload(matched),
        token,
        args.api_url,
        request_delay_seconds=args.request_delay_seconds,
    )
    print(f"Submitted {len(responses)} CFBD Model Pick'em picks.")


if __name__ == "__main__":
    main()
