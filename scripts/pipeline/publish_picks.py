"""
Publisher script to format and email the weekly picks report.

This version renders an HTML email from a Jinja2 template, includes only
recommended bets (spread and totals), highlights a single Best Bet, and
attaches the full weekly CSV schedule to the email. A plain-text fallback
is included for compatibility with clients that block HTML.

Configuration via environment variables:
- PUBLISHER_SMTP_SERVER: e.g., 'smtp.gmail.com'
- PUBLISHER_SMTP_PORT: e.g., 587
- PUBLISHER_EMAIL_SENDER: From address
- PUBLISHER_EMAIL_PASSWORD: App-specific password (or account password)
- PUBLISHER_EMAIL_RECIPIENT: To address
"""

from __future__ import annotations

import argparse
import json as json_lib
import os
import smtplib
import sys
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, List, Tuple

import pandas as pd
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Add project root to path
sys.path.append(os.getcwd())
# noqa: E402
from src.config import PREDICTIONS_SUBDIR, REPORTS_DIR, SCORED_SUBDIR

TEAM_LOGO_MAP = {
    "Sam Houston": "Sam Houston State",
    "UL Monroe": "Louisiana Monroe",
    "Massachusetts": "UMass",
    "App State": "Appalachian State",
    "San José State": "San Jose State",
    "UTSA": "UT San Antonio",
    "Hawai'i": "Hawai_i",
    "Hawaii": "Hawai_i",
    "Hawai i": "Hawai_i",
    "UConn": "Connecticut",
    "Southern Miss": "Southern Mississippi",
    "Texas A&M": "Texas A&M",
}


def _season_subdir(report_dir: Path, year: int, subdir: str) -> Path:
    # Redirect to production data
    if subdir == "scored":
        return Path(f"data/production/scored/{year}")
    elif subdir == "predictions":
        return Path(f"data/production/predictions/{year}")

    preferred = report_dir / str(year) / subdir
    if preferred.exists():
        return preferred
    return report_dir / str(year)


def _logo_cid_for(name: str) -> str:
    """Return a normalized CID for a team name using TEAM_LOGO_MAP normalization.

    Ensures accents/aliases map to the actual logo filename and stabilizes CIDs.
    Ampersands are replaced with __AMP__ for safe CID usage.
    """
    mapped = TEAM_LOGO_MAP.get(name, name)
    # Replace & with __AMP__ for safe CID (won't conflict with team names), spaces with underscores
    safe_cid = str(mapped).replace("&", "__AMP__").replace(" ", "_")
    return f"logo_{safe_cid}"


def _safe_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        v = float(x)
        if pd.isna(v):
            return None
        return v
    except Exception:
        return None


def _compute_displays(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Ensure Date/Time parsing and derived displays
    if "game_date_dt" not in df.columns and {"Date", "Time"}.issubset(df.columns):
        df["game_date_dt"] = pd.to_datetime(
            df["Date"].astype(str) + " " + df["Time"].astype(str), errors="coerce"
        )
    if "game_date_dt" in df.columns:
        df["date_display"] = df["game_date_dt"].dt.strftime("%m/%d/%Y")
        df["time_display"] = df["game_date_dt"].dt.strftime("%I:%M %p")
        df["datetime_display"] = df["game_date_dt"].dt.strftime("%A, %I:%M %p")
    else:
        df["date_display"] = df.get("Date", "").astype(str)
        df["time_display"] = df.get("Time", "").astype(str)
        df["datetime_display"] = ""

    # Derive home/away from Game if missing
    if "home_team" not in df.columns or "away_team" not in df.columns:
        if "Game" in df.columns:
            parts = df["Game"].astype(str).str.split(" @ ", n=1, expand=True)
            if parts.shape[1] == 2:
                df["away_team"] = df.get("away_team", parts[0]).fillna(parts[0])
                df["home_team"] = df.get("home_team", parts[1]).fillna(parts[1])
    if "Game" not in df.columns and {"away_team", "home_team"}.issubset(df.columns):
        df["Game"] = df["away_team"].astype(str) + " @ " + df["home_team"].astype(str)

    # Parse line fields if numeric not present
    # total_line: from numeric 'total_line' or Over/Under string
    if "total_line" not in df.columns and "Over/Under" in df.columns:

        def _parse_ou(val):
            try:
                return float(val)
            except Exception:
                return None

        df["total_line"] = df["Over/Under"].apply(_parse_ou)

    # home_team_spread_line: from numeric or 'Spread' text like "HomeTeam -3.5" or "AwayTeam +2.0"
    if (
        "home_team_spread_line" not in df.columns
        and "Spread" in df.columns
        and "home_team" in df.columns
        and "away_team" in df.columns
    ):

        def _parse_spread(row):
            txt = str(row.get("Spread", ""))
            home = str(row.get("home_team", ""))
            away = str(row.get("away_team", ""))
            if not txt or txt.lower() in ("nan", "none"):
                return None
            if txt.strip().upper() in ("PK", "PICK", "PICKEM"):
                return 0.0
            # Expect format: "Team +/-N.N"
            try:
                team_part, num_part = txt.rsplit(" ", 1)
                num = float(num_part.replace("+", ""))
                # If team listed equals home, home_team_spread_line = num with sign
                if team_part.strip() == home:
                    return num
                elif team_part.strip() == away:
                    return -num
                else:
                    # Fallback: if home team name appears in text
                    if home in txt:
                        return (
                            num
                            if "+" in num_part or num_part.startswith("0")
                            else -abs(num)
                        )
                    if away in txt:
                        return (
                            -num
                            if "+" in num_part or num_part.startswith("0")
                            else abs(num)
                        )
            except Exception:
                pass
            return None

        df["home_team_spread_line"] = df.apply(_parse_spread, axis=1)

    # Compute edges
    # Spread: model is home margin; expected margin = -home_team_spread_line
    if {"Spread Prediction", "home_team_spread_line"}.issubset(df.columns):
        df["edge_spread"] = (
            df["Spread Prediction"].astype(float)
            - (-df["home_team_spread_line"].astype(float))
        ).abs()
    elif {"model_spread", "home_team_spread_line"}.issubset(df.columns):
        df["edge_spread"] = (
            df["model_spread"].astype(float)
            - (-df["home_team_spread_line"].astype(float))
        ).abs()

    # Totals edge
    if {"Total Prediction", "total_line"}.issubset(df.columns):
        df["edge_total"] = (
            df["Total Prediction"].astype(float) - df["total_line"].astype(float)
        ).abs()
    elif {"model_total", "total_line"}.issubset(df.columns):
        df["edge_total"] = (
            df["model_total"].astype(float) - df["total_line"].astype(float)
        ).abs()

    # Display strings
    if "Spread" in df.columns and df["Spread"].notna().any():
        df["spread_line_display"] = df["Spread"].fillna("")
    elif "home_team_spread_line" in df.columns and "home_team" in df.columns:
        df["spread_line_display"] = df.apply(
            lambda r: f"{r['home_team']} {r['home_team_spread_line']:+.1f}"
            if pd.notna(r.get("home_team_spread_line"))
            else "",
            axis=1,
        )
    else:
        df["spread_line_display"] = ""

    return df


def _prepare_recommended(
    df: pd.DataFrame, spread_threshold: float, total_threshold: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    """Return (spreads, totals, best_bet) from the weekly CSV rows with recommended bets only."""
    df = _compute_displays(df)
    df = (
        df.sort_values(["game_date_dt", "Game"]) if "game_date_dt" in df.columns else df
    )

    # Normalize bet columns for filtering
    if "Spread Bet" in df.columns:
        df["Spread Bet"] = df["Spread Bet"].astype(str).str.lower().str.strip()
    if "Total Bet" in df.columns:
        df["Total Bet"] = df["Total Bet"].astype(str).str.lower().str.strip()

    # Build spreads list
    spreads_df = (
        df[
            df["Spread Bet"].astype(str).str.lower().str.strip().isin(["home", "away"])
            & (df["edge_spread"] >= spread_threshold)
        ].copy()
        if "Spread Bet" in df.columns
        else df.iloc[0:0]
    )
    spreads = []
    for _, r in spreads_df.iterrows():
        bet_side = str(r.get("Spread Bet", "")).lower()
        home_team = r.get("home_team")
        away_team = r.get("away_team")
        bet_spread_team = (
            home_team if bet_side == "home" else away_team if bet_side == "away" else ""
        )

        consider_moneyline = False
        vegas_spread = r.get("home_team_spread_line")
        model_spread = r.get("Spread Prediction")

        if pd.notna(vegas_spread) and pd.notna(model_spread):
            # Condition 1: Vegas favors the home team, but the model confidently predicts the away team will win.
            if vegas_spread < 0 and model_spread <= -3:
                consider_moneyline = True
            # Condition 2: Vegas favors the away team, but the model confidently predicts the home team will win.
            elif vegas_spread > 0 and model_spread >= 3:
                consider_moneyline = True

        spreads.append(
            {
                "date_display": r.get("date_display", ""),
                "time_display": r.get("time_display", ""),
                "datetime_display": r.get("datetime_display", ""),
                "game": r.get("Game", ""),
                "home_team": home_team,
                "away_team": away_team,
                "home_team_logo_cid": _logo_cid_for(home_team)
                if pd.notna(home_team)
                else "",
                "away_team_logo_cid": _logo_cid_for(away_team)
                if pd.notna(away_team)
                else "",
                "spread_line_display": r.get("spread_line_display", ""),
                "line_logo_cid": _logo_cid_for(home_team)
                if pd.notna(home_team)
                else "",
                "line_num_display": (
                    f"{float(r.get('home_team_spread_line')):+.1f}"
                    if pd.notna(r.get("home_team_spread_line"))
                    else ""
                ),
                "predicted_spread": float(r.get("Spread Prediction", float("nan")))
                if pd.notna(r.get("Spread Prediction"))
                else None,
                "predicted_spread_std_dev": float(
                    r.get("predicted_spread_std_dev", float("nan"))
                )
                if pd.notna(r.get("predicted_spread_std_dev"))
                else None,
                "edge_spread": float(r.get("edge_spread", 0.0))
                if pd.notna(r.get("edge_spread"))
                else 0.0,
                "bet_spread_team": bet_spread_team,
                "consider_moneyline": "✅" if consider_moneyline else "",
            }
        )

    # Build totals list
    totals_df = (
        df[
            df["Total Bet"].isin(["over", "under"])
            & (df["edge_total"] >= total_threshold)
        ].copy()
        if "Total Bet" in df.columns
        else df.iloc[0:0]
    )
    totals = []
    for _, r in totals_df.iterrows():
        home_team = r.get("home_team")
        away_team = r.get("away_team")
        totals.append(
            {
                "date_display": r.get("date_display", ""),
                "time_display": r.get("time_display", ""),
                "datetime_display": r.get("datetime_display", ""),
                "game": r.get("Game", ""),
                "home_team": home_team,
                "away_team": away_team,
                "home_team_logo_cid": _logo_cid_for(home_team)
                if pd.notna(home_team)
                else "",
                "away_team_logo_cid": _logo_cid_for(away_team)
                if pd.notna(away_team)
                else "",
                "total_line": float(r.get("total_line", float("nan")))
                if pd.notna(r.get("total_line"))
                else None,
                "predicted_total": float(r.get("Total Prediction", float("nan")))
                if pd.notna(r.get("Total Prediction"))
                else None,
                "predicted_total_std_dev": float(
                    r.get("predicted_total_std_dev", float("nan"))
                )
                if pd.notna(r.get("predicted_total_std_dev"))
                else None,
                "edge_total": float(r.get("edge_total", 0.0))
                if pd.notna(r.get("edge_total"))
                else 0.0,
                "bet_total": str(r.get("Total Bet", "")).title(),
            }
        )

    # Determine a single Best Bet
    best_bet = None
    if spreads:
        best_spread = max(spreads, key=lambda x: x.get("edge_spread", 0.0))
        bb = best_spread.copy()
        bb.update(
            {
                "category": "Spread",
                "edge": best_spread.get("edge_spread", 0.0),
                "line_display": best_spread.get("spread_line_display", ""),
                "prediction": best_spread.get("predicted_spread"),
                "bet": best_spread.get("bet_spread_team"),
                "std_dev": best_spread.get("predicted_spread_std_dev"),
            }
        )
        best_bet = bb
    if totals:
        best_total = max(totals, key=lambda x: x.get("edge_total", 0.0))
        bt = best_total.copy()
        bt.update(
            {
                "category": "Total",
                "edge": best_total.get("edge_total", 0.0),
                "line_display": (
                    f"O/U {best_total.get('total_line'):.1f}"
                    if best_total.get("total_line") is not None
                    else "O/U N/A"
                ),
                "prediction": best_total.get("predicted_total"),
                "bet": best_total.get("bet_total"),
                "std_dev": best_total.get("predicted_total_std_dev"),
            }
        )
        if best_bet is None or bt.get("edge", 0.0) > best_bet.get("edge", 0.0):
            best_bet = bt

    return spreads, totals, best_bet


def compute_hit_rates(
    year: int,
    up_to_week: int | None,
    report_dir: Path,
    spread_threshold: float = 0.0,
    total_threshold: float = 0.0,
) -> tuple[float | None, float | None, int, int, int, int]:
    """
    Compute spread/total hit rates, counts, and wins for a year by re-evaluating bets.
    Returns: (spr_rate, tot_rate, spr_count, tot_count, spr_wins, tot_wins)
    """
    import glob

    import numpy as np

    scored_dir = _season_subdir(report_dir, year, SCORED_SUBDIR)
    paths = [Path(p) for p in glob.glob(str(scored_dir / "CFB_week*_bets_scored.csv"))]
    if not paths:
        return None, None, 0, 0, 0, 0

    frames: list[pd.DataFrame] = []
    for p in paths:
        try:
            df = pd.read_csv(p)
            if df.empty:
                continue
            # Infer week from filename if missing
            # Filename format: CFB_week{N}_bets_scored.csv
            if "Week" not in df.columns and "week" not in df.columns:
                try:
                    # Extract N from ...weekN_...
                    name = p.name
                    if "_week" in name:
                        w_part = name.split("_week")[1].split("_")[0]
                        df["Week"] = int(w_part)
                except Exception:
                    pass
            # Normalize columns (coalesce if target exists)
            if "Spread Edge" in df.columns:
                if "edge_spread" in df.columns:
                    df["edge_spread"] = df["edge_spread"].fillna(df["Spread Edge"])
                    df.drop(columns=["Spread Edge"], inplace=True)
                else:
                    df.rename(columns={"Spread Edge": "edge_spread"}, inplace=True)

            if "Total Edge" in df.columns:
                if "edge_total" in df.columns:
                    df["edge_total"] = df["edge_total"].fillna(df["Total Edge"])
                    df.drop(columns=["Total Edge"], inplace=True)
                else:
                    df.rename(columns={"Total Edge": "edge_total"}, inplace=True)

            if "Model Spread" in df.columns:
                if "Spread Prediction" in df.columns:
                    df["Spread Prediction"] = df["Spread Prediction"].fillna(
                        df["Model Spread"]
                    )
                    df.drop(columns=["Model Spread"], inplace=True)
                else:
                    df.rename(
                        columns={"Model Spread": "Spread Prediction"}, inplace=True
                    )

            if "Model Total" in df.columns:
                if "Total Prediction" in df.columns:
                    df["Total Prediction"] = df["Total Prediction"].fillna(
                        df["Model Total"]
                    )
                    df.drop(columns=["Model Total"], inplace=True)
                else:
                    df.rename(columns={"Model Total": "Total Prediction"}, inplace=True)

            frames.append(df)
        except Exception:
            continue
    if not frames:
        return None, None, 0, 0, 0, 0

    scored = pd.concat(frames, ignore_index=True)

    # Coalesce Week and week
    if "Week" in scored.columns and "week" in scored.columns:
        scored["Week"] = scored["Week"].fillna(scored["week"])

    if up_to_week is not None:
        week_col = "Week" if "Week" in scored.columns else "week"
        if week_col in scored.columns:
            week_numeric = pd.to_numeric(scored[week_col], errors="coerce")
            scored = scored[week_numeric <= up_to_week]

    # --- Spread Logic ---
    # Ensure numeric columns
    for col in [
        "Spread Prediction",
        "home_team_spread_line",
        "home_points",
        "away_points",
    ]:
        if col in scored.columns:
            scored[col] = pd.to_numeric(scored[col], errors="coerce")

    # Convert edge columns to numeric
    for col in ["edge_spread", "edge_total"]:
        if col in scored.columns:
            scored[col] = pd.to_numeric(scored[col], errors="coerce")

    # Calculate Edge if missing or re-calc
    if "edge_spread" not in scored.columns:
        scored["edge_spread"] = abs(
            scored["Spread Prediction"] - (-scored["home_team_spread_line"])
        )

    # Determine Bet Side: Pred > -Line => Home
    scored["bet_side_spread"] = np.where(
        scored["Spread Prediction"] > -scored["home_team_spread_line"], "home", "away"
    )

    # Determine Result
    scored["margin"] = scored["home_points"] - scored["away_points"]
    scored["cover_margin"] = scored["margin"] + scored["home_team_spread_line"]

    conditions = [
        (scored["bet_side_spread"] == "home") & (scored["cover_margin"] > 0),
        (scored["bet_side_spread"] == "home") & (scored["cover_margin"] < 0),
        (scored["bet_side_spread"] == "away") & (scored["cover_margin"] < 0),
        (scored["bet_side_spread"] == "away") & (scored["cover_margin"] > 0),
    ]
    choices = ["Win", "Loss", "Win", "Loss"]
    scored["sim_spread_result"] = np.select(conditions, choices, default="Push")

    # Filter and Count (excluding pushes from count)
    spread_bets = scored[scored["edge_spread"] >= spread_threshold]
    spr_wins = len(spread_bets[spread_bets["sim_spread_result"] == "Win"])
    spr_losses = len(spread_bets[spread_bets["sim_spread_result"] == "Loss"])
    spr_n = spr_wins + spr_losses  # Exclude pushes from count
    spr = spr_wins / spr_n if spr_n > 0 else 0.0

    # --- Total Logic ---
    for col in ["Total Prediction", "total_line"]:
        if col in scored.columns:
            scored[col] = pd.to_numeric(scored[col], errors="coerce")

    if "edge_total" not in scored.columns:
        scored["edge_total"] = abs(scored["Total Prediction"] - scored["total_line"])

    scored["bet_side_total"] = np.where(
        scored["Total Prediction"] > scored["total_line"], "over", "under"
    )

    scored["total_score"] = scored["home_points"] + scored["away_points"]

    conditions_t = [
        (scored["bet_side_total"] == "over")
        & (scored["total_score"] > scored["total_line"]),
        (scored["bet_side_total"] == "over")
        & (scored["total_score"] < scored["total_line"]),
        (scored["bet_side_total"] == "under")
        & (scored["total_score"] < scored["total_line"]),
        (scored["bet_side_total"] == "under")
        & (scored["total_score"] > scored["total_line"]),
    ]
    choices_t = ["Win", "Loss", "Win", "Loss"]
    scored["sim_total_result"] = np.select(conditions_t, choices_t, default="Push")

    total_bets = scored[scored["edge_total"] >= total_threshold]
    tot_wins = len(total_bets[total_bets["sim_total_result"] == "Win"])
    tot_losses = len(total_bets[total_bets["sim_total_result"] == "Loss"])
    tot_n = tot_wins + tot_losses  # Exclude pushes from count
    tot = tot_wins / tot_n if tot_n > 0 else 0.0

    return spr, tot, spr_n, tot_n, spr_wins, tot_wins


def compute_week_hit_rates(
    year: int,
    week: int,
    report_dir: Path,
    spread_threshold: float = 0.0,
    total_threshold: float = 0.0,
) -> tuple[float | None, float | None, int, int, int, int]:
    """
    Compute spread/total hit rates, counts, and wins for a specific week by re-evaluating bets.
    Returns: (spr_rate, tot_rate, spr_count, tot_count, spr_wins, tot_wins)
    """
    import glob

    import numpy as np

    scored_dir = _season_subdir(report_dir, year, SCORED_SUBDIR)
    weekly_path = scored_dir / f"CFB_week{week}_bets_scored.csv"
    frames: list[pd.DataFrame] = []
    if weekly_path.exists():
        try:
            frames.append(pd.read_csv(weekly_path))
        except Exception:
            pass
    else:
        season_combined = scored_dir / f"CFB_season_{year}_all_bets_scored.csv"
        if season_combined.exists():
            try:
                df = pd.read_csv(season_combined)
                frames.append(df)
            except Exception:
                pass
        else:
            for p in glob.glob(str(scored_dir / "CFB_week*_bets_scored.csv")):
                try:
                    frames.append(pd.read_csv(p))
                except Exception:
                    continue

    if not frames:
        return None, None, 0, 0, 0, 0

    df = pd.concat(frames, ignore_index=True)

    # Coalesce Week and week
    if "Week" in df.columns and "week" in df.columns:
        df["Week"] = df["Week"].fillna(df["week"])

    week_col = "Week" if "Week" in df.columns else "week"
    if week_col in df.columns:
        week_numeric = pd.to_numeric(df[week_col], errors="coerce")
        df = df[week_numeric == week]

    if df.empty:
        return None, None, 0, 0, 0, 0

    # --- Spread Logic ---
    for col in [
        "Spread Prediction",
        "home_team_spread_line",
        "home_points",
        "away_points",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "edge_spread" not in df.columns:
        df["edge_spread"] = abs(
            df["Spread Prediction"] - (-df["home_team_spread_line"])
        )

    df["bet_side_spread"] = np.where(
        df["Spread Prediction"] > -df["home_team_spread_line"], "home", "away"
    )

    df["margin"] = df["home_points"] - df["away_points"]
    df["cover_margin"] = df["margin"] + df["home_team_spread_line"]

    conditions = [
        (df["bet_side_spread"] == "home") & (df["cover_margin"] > 0),
        (df["bet_side_spread"] == "home") & (df["cover_margin"] < 0),
        (df["bet_side_spread"] == "away") & (df["cover_margin"] < 0),
        (df["bet_side_spread"] == "away") & (df["cover_margin"] > 0),
    ]
    choices = ["Win", "Loss", "Win", "Loss"]
    df["sim_spread_result"] = np.select(conditions, choices, default="Push")

    spread_bets = df[df["edge_spread"] >= spread_threshold]
    spr_wins = len(spread_bets[spread_bets["sim_spread_result"] == "Win"])
    spr_losses = len(spread_bets[spread_bets["sim_spread_result"] == "Loss"])
    spr_n = spr_wins + spr_losses  # Exclude pushes from count
    spr = spr_wins / spr_n if spr_n > 0 else 0.0

    # --- Total Logic ---
    for col in ["Total Prediction", "total_line"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "edge_total" not in df.columns:
        df["edge_total"] = abs(df["Total Prediction"] - df["total_line"])

    df["bet_side_total"] = np.where(
        df["Total Prediction"] > df["total_line"], "over", "under"
    )

    df["total_score"] = df["home_points"] + df["away_points"]

    conditions_t = [
        (df["bet_side_total"] == "over") & (df["total_score"] > df["total_line"]),
        (df["bet_side_total"] == "over") & (df["total_score"] < df["total_line"]),
        (df["bet_side_total"] == "under") & (df["total_score"] < df["total_line"]),
        (df["bet_side_total"] == "under") & (df["total_score"] > df["total_line"]),
    ]
    choices_t = ["Win", "Loss", "Win", "Loss"]
    df["sim_total_result"] = np.select(conditions_t, choices_t, default="Push")

    total_bets = df[df["edge_total"] >= total_threshold]
    tot_wins = len(total_bets[total_bets["sim_total_result"] == "Win"])
    tot_losses = len(total_bets[total_bets["sim_total_result"] == "Loss"])
    tot_n = tot_wins + tot_losses  # Exclude pushes from count
    tot = tot_wins / tot_n if tot_n > 0 else 0.0

    return spr, tot, spr_n, tot_n, spr_wins, tot_wins


def render_email_html(template_dir: Path, context):
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tmpl = env.get_template("email_weekly_picks_v3.html")
    return tmpl.render(**context)


def build_plain_text(context):
    # Simple plaintext fallback summarizing the bets
    lines = []
    lines.append(f"CK's CFB Picks — {context['year']} Week {context['week']}")
    lines.append(
        f"Generated {context['generated_at']} | Thresholds: spread ≥ {context['spread_threshold']}, total ≥ {context['total_threshold']}"
    )
    lines.append("")
    bb = context.get("best_bet")
    if bb:
        lines.append("Best Bet:")
        lines.append(
            f"  {bb.get('datetime_display', '')} | {bb.get('game', '')} | {bb.get('category')} | {bb.get('line_display', '')} | Pred: {bb.get('prediction', '')} | Edge: {bb.get('edge', '')} | Bet: {bb.get('bet', '')} | Std Dev: {bb.get('std_dev', '')}"
        )
        lines.append("")

    spreads = context.get("spreads", [])
    totals = context.get("totals", [])

    if spreads:
        lines.append("Spread Bets:")
        for r in spreads:
            lines.append(
                f"  {r.get('datetime_display', '')} | {r.get('game', '')} | {r.get('spread_line_display', '')} | Pred: {r.get('predicted_spread', '')} | Edge: {r.get('edge_spread', '')} | Bet: {r.get('bet_spread_team', '')} | Std Dev: {r.get('predicted_spread_std_dev', '')}"
            )
        lines.append("")
    if totals:
        lines.append("Totals Bets:")
        for r in totals:
            lines.append(
                f"  {r.get('datetime_display', '')} | {r.get('game', '')} | O/U: {r.get('total_line', '')} | Pred: {r.get('predicted_total', '')} | Edge: {r.get('edge_total', '')} | Bet: {r.get('bet_total', '')} | Std Dev: {r.get('predicted_total_std_dev', '')}"
            )
        lines.append("")

    lines.append("Full report attached as CSV.")
    return "\n".join(lines)


def send_email(
    subject: str,
    html_content: str,
    text_content: str,
    sender: str,
    recipients: List[str],
    password: str,
    server: str,
    port: int,
    attachments: List[Tuple[str, bytes, str]] | None = None,
    image_attachments: List[MIMEImage] | None = None,
) -> None:
    """Send an email using SMTP with HTML, plaintext, and optional attachments."""
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(text_content, "plain"))
    alt_part.attach(MIMEText(html_content, "html"))
    msg.attach(alt_part)

    # Attach images
    for img in image_attachments or []:
        msg.attach(img)

    # Attach files
    for filename, content_bytes, mime_type in attachments or []:
        maintype, subtype = (mime_type.split("/", 1) + ["octet-stream"])[:2]
        part = MIMEBase(maintype, subtype)
        part.set_payload(content_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    print(f"\nConnecting to SMTP server {server}:{port}...", flush=True)
    with smtplib.SMTP(server, port) as s:
        print("Securing connection with STARTTLS...", flush=True)
        s.starttls()
        print("STARTTLS connection secured.", flush=True)

        print("Logging in to SMTP server...", flush=True)
        s.login(sender, password)
        print("Login successful.", flush=True)

        print("Sending email...", flush=True)
        s.sendmail(sender, recipients, msg.as_string())
        print("Email sent.", flush=True)


def main() -> None:
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Format and email weekly picks (recommended bets only)."
    )
    parser.add_argument("--year", type=int, required=True, help="The season year.")
    parser.add_argument(
        "--week", type=int, required=True, help="The week of the report."
    )
    parser.add_argument(
        "--report-dir",
        default=str(REPORTS_DIR),
        help="Directory where reports are stored.",
    )
    parser.add_argument(
        "--mode",
        choices=["test", "prod"],
        default="test",
        help="Select email recipient mode (test sends to TEST_EMAIL_RECIPIENT; prod sends to PROD_EMAIL_RECIPIENTS).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render the email preview files instead of sending via SMTP.",
    )
    args = parser.parse_args()

    # --- Load Config from Environment ---
    try:
        smtp_server = os.environ["PUBLISHER_SMTP_SERVER"]
        smtp_port = int(os.environ["PUBLISHER_SMTP_PORT"])
        sender_email = os.environ["PUBLISHER_EMAIL_SENDER"]
        sender_password = os.environ["PUBLISHER_EMAIL_PASSWORD"]
    except KeyError as e:
        print(f"Error: Missing required environment variable: {e}")
        print("Please set all PUBLISHER_* environment variables.")
        return

    # Resolve recipients based on mode
    recipients: List[str] = []
    if args.mode == "test":
        test_recipient = os.environ.get("TEST_EMAIL_RECIPIENT")
        if not test_recipient:
            print("Error: TEST_EMAIL_RECIPIENT not set in environment")
            return
        recipients = [test_recipient]
    else:
        raw = os.environ.get("PROD_EMAIL_RECIPIENTS", "")
        if not raw:
            print("Error: PROD_EMAIL_RECIPIENTS not set in environment")
            return
        try:
            import ast
            import json

            # Try parsing as Python literal (handles single quotes) first
            try:
                parsed = ast.literal_eval(raw)
            except (ValueError, SyntaxError):
                # Try JSON (handles double quotes)
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None

            if isinstance(parsed, list):
                recipients = [str(x).strip() for x in parsed if str(x).strip()]
            else:
                # Fallback: manual splitting
                # Remove outer brackets if present
                cleaned = raw.strip()
                if cleaned.startswith("[") and cleaned.endswith("]"):
                    cleaned = cleaned[1:-1]
                # Split by comma and strip quotes/whitespace
                recipients = [
                    s.strip().strip("'").strip('"')
                    for s in cleaned.split(",")
                    if s.strip()
                ]
        except Exception:
            print("Error parsing PROD_EMAIL_RECIPIENTS, using raw split fallback.")
            recipients = [s.strip() for s in str(raw).split(",") if s.strip()]
        if not recipients:
            print("Error: Could not parse PROD_EMAIL_RECIPIENTS")
            return

    # --- 2. Load the Weekly Bets CSV ---
    report_dir_path = Path(args.report_dir)

    # Try production scored first, then production predictions
    prod_scored = Path(
        f"data/production/scored/{args.year}/CFB_week{args.week}_bets_scored.csv"
    )
    prod_preds = Path(
        f"data/production/predictions/{args.year}/CFB_week{args.week}_bets.csv"
    )

    if prod_scored.exists():
        bets_file = prod_scored
    elif prod_preds.exists():
        bets_file = prod_preds
    else:
        # Fallback to reports dir
        scored_dir = report_dir_path / str(args.year) / SCORED_SUBDIR
        if scored_dir.exists():
            bets_file = scored_dir / f"CFB_week{args.week}_bets_scored.csv"
        else:
            bets_file = (
                report_dir_path
                / str(args.year)
                / f"CFB_week{args.week}_bets_scored.csv"
            )
            if not bets_file.exists():
                # Try predictions
                pred_dir = report_dir_path / str(args.year) / PREDICTIONS_SUBDIR
                bets_file = pred_dir / f"CFB_week{args.week}_bets.csv"

    if not bets_file.exists():
        print(f"Error: Bets file not found at {bets_file}")
        return

    all_games_df = pd.read_csv(bets_file)

    # Normalize columns from CSV to internal names
    if (
        "Spread Line" in all_games_df.columns
        and "home_team_spread_line" not in all_games_df.columns
    ):
        all_games_df["home_team_spread_line"] = all_games_df["Spread Line"]
    if (
        "Total Line" in all_games_df.columns
        and "total_line" not in all_games_df.columns
    ):
        all_games_df["total_line"] = all_games_df["Total Line"]

    # Validation check for missing lines
    recommended_bets_df = all_games_df[
        (all_games_df["Spread Bet"].isin(["home", "away"]))
        | (all_games_df["Total Bet"].isin(["over", "under"]))
    ].copy()

    if not recommended_bets_df.empty:
        spread_missing = recommended_bets_df[
            recommended_bets_df["Spread Bet"].isin(["home", "away"])
            & recommended_bets_df["home_team_spread_line"].isnull()
        ]
        total_missing = recommended_bets_df[
            recommended_bets_df["Total Bet"].isin(["over", "under"])
            & recommended_bets_df["total_line"].isnull()
        ]
        if not spread_missing.empty or not total_missing.empty:
            print(
                "Error: Found recommended bets with missing line data. Aborting email."
            )
            if not spread_missing.empty:
                print("\nSpread bets with missing lines:")
                print(spread_missing[["Game", "Spread Bet"]])
            if not total_missing.empty:
                print("\nTotal bets with missing lines:")
                print(total_missing[["Game", "Total Bet"]])
            return

    # --- Prepare Email Content ---
    all_df = _compute_displays(all_games_df)
    all_df = (
        all_df.sort_values(["game_date_dt", "Game"])
        if "game_date_dt" in all_df.columns
        else all_df
    )

    min_date = all_df["game_date_dt"].min()
    max_date = all_df["game_date_dt"].max()
    if min_date.month == max_date.month:
        date_range = f"{min_date.strftime('%B %-d')} - {max_date.strftime('%-d')}"
    else:
        date_range = f"{min_date.strftime('%B %-d')} - {max_date.strftime('%B %-d')}"

    generated_at = datetime.now().strftime("%m/%d/%Y %I:%M %p")

    # Load thresholds from Hydra config
    from hydra import compose, initialize_config_dir

    config_dir = Path(__file__).resolve().parents[2] / "conf"
    with initialize_config_dir(version_base=None, config_dir=str(config_dir)):
        # Default to loading v2_champion for thresholds if not specified
        cfg = compose(config_name="config", overrides=["+weekly_bets=v2_champion"])

        if "spread_edge_threshold" in cfg.weekly_bets:
            # V2 Config Structure
            spread_threshold = cfg.weekly_bets.spread_edge_threshold
            total_threshold = cfg.weekly_bets.total_edge_threshold
        elif "betting" in cfg.weekly_bets:
            # V1 Config Structure
            spread_threshold = cfg.weekly_bets.betting.spread_threshold
            total_threshold = cfg.weekly_bets.betting.total_threshold
        else:
            # Fallback defaults
            spread_threshold = 0.0
            total_threshold = 0.0

    print(
        f"Using thresholds from config: spread={spread_threshold}, total={total_threshold}"
    )

    spreads, totals, best_bet = _prepare_recommended(
        all_df, spread_threshold, total_threshold
    )

    # Compute summary stats
    summary = {
        "n_spreads": len(spreads),
        "n_totals": len(totals),
        "n_best_bets": 1 if best_bet else 0,
    }
    repo_root = Path(__file__).resolve().parents[2]
    template_dir = repo_root / "templates"

    all_games: list[dict[str, Any]] = []
    for _, r in all_df.iterrows():
        bet_side = str(r.get("Spread Bet", "")).strip().lower()

        game_str = str(r.get("Game", ""))
        home_from_game, away_from_game = (game_str.split(" @ ", 1) + [None, None])[:2]
        home_name = r.get("home_team") or home_from_game or "home"
        away_name = r.get("away_team") or away_from_game or "away"

        spread_bet_display = (
            home_name
            if bet_side == "home"
            else away_name
            if bet_side == "away"
            else "No Bet"
        )
        total_bet_display = (
            str(r.get("Total Bet", "")).strip().title()
            if str(r.get("Total Bet", "")).strip().lower() in ("over", "under")
            else "No Bet"
        )

        all_games.append(
            {
                "date_display": r.get("date_display", ""),
                "time_display": r.get("time_display", ""),
                "datetime_display": r.get("datetime_display", ""),
                "game": r.get("Game", ""),
                "home_team": home_name,
                "away_team": away_name,
                "home_team_logo_cid": _logo_cid_for(home_name)
                if pd.notna(home_name)
                else "",
                "away_team_logo_cid": _logo_cid_for(away_name)
                if pd.notna(away_name)
                else "",
                "spread_line_display": r.get("spread_line_display", ""),
                "line_logo_cid": _logo_cid_for(home_name)
                if pd.notna(home_name)
                else "",
                "line_num_display": (
                    f"{float(r.get('home_team_spread_line')):+.1f}"
                    if pd.notna(r.get("home_team_spread_line"))
                    else ""
                ),
                "total_line": _safe_float(r.get("total_line")),
                "predicted_spread": _safe_float(r.get("Spread Prediction")),
                "predicted_total": _safe_float(r.get("Total Prediction")),
                "edge_spread": _safe_float(r.get("edge_spread")),
                "edge_total": _safe_float(r.get("edge_total")),
                "spread_bet_display": spread_bet_display,
                "total_bet_display": total_bet_display,
            }
        )

    (
        prev_spread,
        prev_total,
        prev_spread_n,
        prev_total_n,
        prev_spread_wins,
        prev_total_wins,
    ) = compute_hit_rates(
        args.year - 1, None, report_dir_path, spread_threshold, total_threshold
    )
    (
        curr_spread,
        curr_total,
        curr_spread_n,
        curr_total_n,
        curr_spread_wins,
        curr_total_wins,
    ) = compute_hit_rates(
        args.year, args.week, report_dir_path, spread_threshold, total_threshold
    )
    (
        lastyr_week_spr,
        lastyr_week_tot,
        lastyr_week_spr_n,
        lastyr_week_tot_n,
        lastyr_week_spr_wins,
        lastyr_week_tot_wins,
    ) = compute_week_hit_rates(
        args.year - 1,
        args.week,
        report_dir_path,
        spread_threshold,
        total_threshold,
    )

    # Load Validation History (Last Year)
    history_file = Path("data/production/system_stats.json")
    history_data = {}
    if history_file.exists():
        try:
            with open(history_file, "r") as f:
                history_data = json_lib.load(f)
        except Exception as e:
            print(f"Error loading validation history: {e}")

    # Parse Standard Validation History
    # Structure:
    # {
    #   "2024_full": {spread: {}, total: {}},
    #   "2025_ytd": {spread: {}, total: {}},
    #   "2024_week_16": {spread: {}, total: {}}
    # }

    # 2024 Full
    stats_24 = history_data.get("2024_full", {})
    prev_spr = stats_24.get("spread", {})
    prev_tot = stats_24.get("total", {})

    # 2025 YTD (System Record)
    # Prefer this over live record for "System Info" consistency if available
    stats_25 = history_data.get("2025_ytd", {})
    curr_spr = stats_25.get("spread", {})
    curr_tot = stats_25.get("total", {})

    # If 2025 YTD missing, fall back to live counted (which we already computed in vars curr_spread, etc.)
    # But usually we want to override.
    use_system_ytd = bool(stats_25)

    # 2024 Specific Week
    wk_key = f"2024_week_{args.week}"
    stats_24_wk = history_data.get(wk_key, {})
    prev_wk_spr = stats_24_wk.get("spread", {})
    prev_wk_tot = stats_24_wk.get("total", {})

    # Load System Metadata
    system_name = cfg.get("weekly_bets", {}).get("system_name", "Model: Chimera-v1")
    model_id = cfg.get("weekly_bets", {}).get("model_id", "HYBRID-2025")

    model_context = {
        "prev_year": args.year - 1,
        "prev_spread": prev_spr.get("roi", 0.0),
        "prev_total": prev_tot.get("roi", 0.0),
        "prev_spread_count": prev_spr.get("bets", 0),
        "prev_total_count": prev_tot.get("bets", 0),
        "prev_spread_wins": prev_spr.get("wins", 0),
        "prev_total_wins": prev_tot.get("wins", 0),
        "model_name": system_name,
        "model_id": model_id,
        "curr_year": args.year,
        "curr_through_week": args.week,
        # Override with System YTD if available
        "curr_spread": curr_spr.get("roi", 0.0)
        if use_system_ytd
        else (curr_spread or 0.0),
        "curr_total": curr_tot.get("roi", 0.0)
        if use_system_ytd
        else (curr_total or 0.0),
        "curr_spread_count": curr_spr.get("bets", 0)
        if use_system_ytd
        else (curr_spread_n or 0),
        "curr_total_count": curr_tot.get("bets", 0)
        if use_system_ytd
        else (curr_total_n or 0),
        "curr_spread_wins": curr_spr.get("wins", 0)
        if use_system_ytd
        else (curr_spread_wins or 0),
        "curr_total_wins": curr_tot.get("wins", 0)
        if use_system_ytd
        else (curr_total_wins or 0),
        "last_year_week_spread": prev_wk_spr.get("roi", 0.0),
        "last_year_week_total": prev_wk_tot.get("roi", 0.0),
        "last_year_week_spread_count": prev_wk_spr.get("bets", 0),
        "last_year_week_total_count": prev_wk_tot.get("bets", 0),
        "last_year_week_spread_wins": prev_wk_spr.get("wins", 0),
        "last_year_week_total_wins": prev_wk_tot.get("wins", 0),
    }

    # Get Best Bet History
    best_bet_record = "N/A"

    context = {
        "year": args.year,
        "week": args.week,
        "date_range": date_range,
        "generated_at": generated_at,
        "spread_threshold": spread_threshold,
        "total_threshold": total_threshold,
        "spreads": spreads,
        "totals": totals,
        "best_bet": best_bet,
        "best_bet_record": best_bet_record,
        "summary": summary,
        "model_context": model_context,
        "all_games": all_games,
        "docs_url": "https://github.com/connorkitchings/cfb_model",
        "strong_spread_edge": spread_threshold + 2.0,
        "strong_total_edge": total_threshold + 2.0,
    }

    html = render_email_html(template_dir, context)
    text = build_plain_text(context)

    # Save HTML to file for review
    output_html_path = report_dir_path / f"week_{args.week}_email.html"
    with open(output_html_path, "w") as f:
        f.write(html)
    print(f"Saved email HTML to {output_html_path}")

    # --- Attach Logos (only those actually referenced in HTML) ---
    # Extract all cid: references used in the rendered HTML
    import re

    cids_in_html = set(re.findall(r"cid:([^\"']+)", html))

    image_attachments = []
    logo_dir = repo_root / "Logos"

    # Attach exactly the CIDs referenced in HTML, mapping to logo files via TEAM_LOGO_MAP
    for cid in sorted(cids_in_html):
        if not cid.startswith("logo_"):
            continue
        # Reverse the CID sanitization: replace __AMP__ back to &
        name_part = cid[len("logo_") :].replace("__AMP__", "&").replace("_", " ")
        logo_name = TEAM_LOGO_MAP.get(name_part, name_part)
        logo_path = logo_dir / f"{logo_name}.png"
        if not logo_path.exists():
            continue
        with open(logo_path, "rb") as f:
            img_data = f.read()
        img = MIMEImage(img_data)
        img.add_header("Content-ID", f"<{cid}>")
        # Hint to clients to render inline rather than as a separate attachment
        img.add_header("Content-Disposition", "inline", filename=logo_path.name)
        image_attachments.append(img)

    # --- Attach and Send Email ---
    # CSV attachment removed per user request
    # --- 4. Send or preview ---
    subject = f"CK's CFB Picks: {args.year} Week {args.week}"
    if args.dry_run:
        preview_dir = report_dir_path / str(args.year) / "email_previews"
        preview_dir.mkdir(parents=True, exist_ok=True)
        html_path = preview_dir / f"week_{args.week:02d}_picks.html"
        text_path = preview_dir / f"week_{args.week:02d}_picks.txt"
        html_path.write_text(html, encoding="utf-8")
        text_path.write_text(text, encoding="utf-8")
        print(
            f"Dry run enabled; wrote HTML preview to {html_path} and text preview to {text_path}."
        )
        return

    attachments = []

    try:
        send_email(
            subject,
            html,
            text,
            sender_email,
            recipients,
            sender_password,
            smtp_server,
            smtp_port,
            attachments=attachments,
            image_attachments=image_attachments,
        )
        print(
            f"Successfully sent picks for Week {args.week} to {', '.join(recipients)}."
        )
    except Exception as e:
        print(f"Error sending email: {e}")


if __name__ == "__main__":
    main()
