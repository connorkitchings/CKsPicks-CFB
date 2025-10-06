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
import os
import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, List, Tuple

import pandas as pd
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape


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
    else:
        df["date_display"] = df.get("Date", "").astype(str)
        df["time_display"] = df.get("Time", "").astype(str)

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


def _prepare_recommended(all_games_df: pd.DataFrame):
    """Return (spreads, totals, best_bet) from the weekly CSV rows with recommended bets only."""
    df = _compute_displays(all_games_df)
    df = (
        df.sort_values(["game_date_dt", "Game"]) if "game_date_dt" in df.columns else df
    )

    # Build spreads list
    spreads_df = (
        df[df["Spread Bet"].isin(["home", "away"])].copy()
        if "Spread Bet" in df.columns
        else df.iloc[0:0]
    )
    spreads = []
    for _, r in spreads_df.iterrows():
        bet_side = str(r.get("Spread Bet", "")).lower()
        bet_spread_team = (
            r.get("home_team")
            if bet_side == "home"
            else r.get("away_team")
            if bet_side == "away"
            else ""
        )
        spreads.append(
            {
                "date_display": r.get("date_display", ""),
                "time_display": r.get("time_display", ""),
                "game": r.get("Game", ""),
                "home_team": r.get("home_team", ""),
                "spread_line_display": r.get("spread_line_display", ""),
                "predicted_spread": float(r.get("Spread Prediction", float("nan")))
                if pd.notna(r.get("Spread Prediction"))
                else None,
                "predicted_spread_std_dev": float(
                    r.get("predicted_spread_std_dev", float("nan"))
                )
                if pd.notna(r.get("predicted_spread_std_dev", float("nan")))
                else None,
                "edge_spread": float(r.get("edge_spread", 0.0))
                if pd.notna(r.get("edge_spread", 0.0))
                else 0.0,
                "bet_spread_team": bet_spread_team,
            }
        )

    # Build totals list
    totals_df = (
        df[df["Total Bet"].isin(["over", "under"])].copy()
        if "Total Bet" in df.columns
        else df.iloc[0:0]
    )
    totals = []
    for _, r in totals_df.iterrows():
        totals.append(
            {
                "date_display": r.get("date_display", ""),
                "time_display": r.get("time_display", ""),
                "game": r.get("Game", ""),
                "home_team": r.get("home_team", ""),
                "total_line": float(r.get("total_line", float("nan")))
                if pd.notna(r.get("total_line", float("nan")))
                else None,
                "predicted_total": float(r.get("Total Prediction", float("nan")))
                if pd.notna(r.get("Total Prediction"))
                else None,
                "predicted_total_std_dev": float(
                    r.get("predicted_total_std_dev", float("nan"))
                )
                if pd.notna(r.get("predicted_total_std_dev", float("nan")))
                else None,
                "edge_total": float(r.get("edge_total", 0.0))
                if pd.notna(r.get("edge_total", 0.0))
                else 0.0,
                "bet_total": str(r.get("Total Bet", "")).title(),
            }
        )

    # Determine a single Best Bet across spread and total by largest edge
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
    year: int, up_to_week: int | None, report_dir: Path
) -> tuple[float | None, float | None, float | None, float | None, int, int]:
    """
    Compute spread/total hit rates, ROI, and counts for a year.

    Assumes -110 juice (win 1 unit, risk 1.1 units).
    ROI is calculated as (total units won / total units risked).
    """
    import glob

    # 1) Prefer precomputed metrics if present
    metrics_path = report_dir / "metrics" / f"hit_rates_{year}.csv"
    if metrics_path.exists():
        try:
            mdf = pd.read_csv(metrics_path)
            row = mdf.iloc[0]
            spr = (
                float(row["spread_hit_rate"])
                if pd.notna(row.get("spread_hit_rate"))
                else None
            )
            tot = (
                float(row["total_hit_rate"])
                if pd.notna(row.get("total_hit_rate"))
                else None
            )
            spr_roi = (
                float(row["spread_roi"]) if pd.notna(row.get("spread_roi")) else None
            )
            tot_roi = (
                float(row["total_roi"]) if pd.notna(row.get("total_roi")) else None
            )
            spr_n = int(row.get("spread_count", 0))
            tot_n = int(row.get("total_count", 0))
            return spr, tot, spr_roi, tot_roi, spr_n, tot_n
        except Exception:
            pass

    # 2) Parse scored CSVs
    def _load_scored_paths(y: int) -> list[Path]:
        return [
            Path(p)
            for p in glob.glob(str(report_dir / str(y) / "CFB_week*_bets_scored.csv"))
        ]

    paths = _load_scored_paths(year)
    if not paths:
        return None, None, None, None, 0, 0

    frames: list[pd.DataFrame] = []
    for p in paths:
        try:
            df = pd.read_csv(p)
            frames.append(df)
        except Exception:
            continue
    if not frames:
        return None, None, None, None, 0, 0

    scored = pd.concat(frames, ignore_index=True)

    # Filter by week if applicable
    if up_to_week is not None:
        week_col = "Week" if "Week" in scored.columns else "week"
        if week_col in scored.columns:
            scored = scored[scored[week_col] <= up_to_week]

    # ROI calculation constants
    win_payout = 1.0
    risk_amount = 1.1

    def _calculate_metrics(
        df: pd.DataFrame, bet_col: str, result_col: str, valid_bets: list[str]
    ) -> tuple[float | None, float | None, int]:
        placed = df[df[bet_col].astype(str).str.lower().isin(valid_bets)]
        decided = placed[placed[result_col].isin(["Win", "Loss", 0, 1])]
        count = len(decided)
        if count == 0:
            return None, None, 0

        if result_col in ["pick_win", "total_pick_win"]:
            wins = decided[result_col].sum()
        else:
            wins = (decided[result_col] == "Win").sum()

        hit_rate = wins / count
        units_won = wins * win_payout
        units_risked = count * risk_amount
        roi = (
            (units_won - (count - wins) * risk_amount) / units_risked
            if units_risked > 0
            else 0.0
        )

        return hit_rate, roi, count

    # Spread
    spr, spr_roi, spr_n = _calculate_metrics(
        scored, "Spread Bet", "Spread Bet Result", ["home", "away"]
    )
    if spr_n == 0 and {"bet_spread", "pick_win"}.issubset(scored.columns):
        spr, spr_roi, spr_n = _calculate_metrics(
            scored, "bet_spread", "pick_win", ["home", "away"]
        )

    # Total
    tot, tot_roi, tot_n = _calculate_metrics(
        scored, "Total Bet", "Total Bet Result", ["over", "under"]
    )
    if tot_n == 0 and {"bet_total", "total_pick_win"}.issubset(scored.columns):
        tot, tot_roi, tot_n = _calculate_metrics(
            scored, "bet_total", "total_pick_win", ["over", "under"]
        )

    return spr, tot, spr_roi, tot_roi, spr_n, tot_n


def compute_week_hit_rates(
    year: int, week: int, report_dir: Path
) -> tuple[float | None, float | None, float | None, float | None, int, int]:
    """
    Compute spread/total hit rates, ROI, and counts for a specific week.
    """
    import glob

    # Prefer weekly file if available
    weekly_path = report_dir / str(year) / f"CFB_week{week}_bets_scored.csv"
    frames: list[pd.DataFrame] = []
    if weekly_path.exists():
        try:
            frames.append(pd.read_csv(weekly_path))
        except Exception:
            pass
    else:
        # Fallback to combined season if present
        season_combined = (
            report_dir / str(year) / f"CFB_season_{year}_all_bets_scored.csv"
        )
        if season_combined.exists():
            try:
                df = pd.read_csv(season_combined)
                frames.append(df)
            except Exception:
                pass
        else:
            # Try any weekly files and filter
            for p in glob.glob(
                str(report_dir / str(year) / "CFB_week*_bets_scored.csv")
            ):
                try:
                    frames.append(pd.read_csv(p))
                except Exception:
                    continue

    if not frames:
        return None, None, None, None, 0, 0

    df = pd.concat(frames, ignore_index=True)
    # Filter exact week
    week_col = "Week" if "Week" in df.columns else "week"
    if week_col in df.columns:
        df = df[df[week_col] == week]

    if df.empty:
        return None, None, None, None, 0, 0

    # ROI calculation constants
    win_payout = 1.0
    risk_amount = 1.1

    def _calculate_metrics(
        df: pd.DataFrame, bet_col: str, result_col: str, valid_bets: list[str]
    ) -> tuple[float | None, float | None, int]:
        placed = df[df[bet_col].astype(str).str.lower().isin(valid_bets)]
        decided = placed[placed[result_col].isin(["Win", "Loss", 0, 1])]
        count = len(decided)
        if count == 0:
            return None, None, 0

        if result_col in ["pick_win", "total_pick_win"]:
            wins = decided[result_col].sum()
        else:
            wins = (decided[result_col] == "Win").sum()

        hit_rate = wins / count
        units_won = wins * win_payout
        units_risked = count * risk_amount
        roi = (
            (units_won - (count - wins) * risk_amount) / units_risked
            if units_risked > 0
            else 0.0
        )

        return hit_rate, roi, count

    # Spread
    spr, spr_roi, spr_n = _calculate_metrics(
        df, "Spread Bet", "Spread Bet Result", ["home", "away"]
    )
    if spr_n == 0 and {"bet_spread", "pick_win"}.issubset(df.columns):
        spr, spr_roi, spr_n = _calculate_metrics(
            df, "bet_spread", "pick_win", ["home", "away"]
        )

    # Total
    tot, tot_roi, tot_n = _calculate_metrics(
        df, "Total Bet", "Total Bet Result", ["over", "under"]
    )
    if tot_n == 0 and {"bet_total", "total_pick_win"}.issubset(df.columns):
        tot, tot_roi, tot_n = _calculate_metrics(
            df, "bet_total", "total_pick_win", ["over", "under"]
        )

    return spr, tot, spr_roi, tot_roi, spr_n, tot_n


def render_email_html(template_dir: Path, context):
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tmpl = env.get_template("email_weekly_picks.html")
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
            f"  {bb.get('date_display', '')} {bb.get('time_display', '')} | {bb.get('game', '')} | {bb.get('category')} | {bb.get('line_display', '')} | Pred: {bb.get('prediction', '')} | Edge: {bb.get('edge', '')} | Bet: {bb.get('bet', '')} | Std Dev: {bb.get('std_dev', '')}"
        )
        lines.append("")

    spreads = context.get("spreads", [])
    totals = context.get("totals", [])

    if spreads:
        lines.append("Spread Bets:")
        for r in spreads:
            lines.append(
                f"  {r.get('date_display', '')} {r.get('time_display', '')} | {r.get('game', '')} | {r.get('spread_line_display', '')} | Pred: {r.get('predicted_spread', '')} | Edge: {r.get('edge_spread', '')} | Bet: {r.get('bet_spread_team', '')} | Std Dev: {r.get('predicted_spread_std_dev', '')}"
            )
        lines.append("")
    if totals:
        lines.append("Totals Bets:")
        for r in totals:
            lines.append(
                f"  {r.get('date_display', '')} {r.get('time_display', '')} | {r.get('game', '')} | O/U: {r.get('total_line', '')} | Pred: {r.get('predicted_total', '')} | Edge: {r.get('edge_total', '')} | Bet: {r.get('bet_total', '')} | Std Dev: {r.get('predicted_total_std_dev', '')}"
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
) -> None:
    """Send an email using SMTP with HTML, plaintext, and optional attachments.

    attachments: list of (filename, bytes_content, mime_type)
    """
    # mixed container for attachments with an alternative part for text/html
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(text_content, "plain"))
    alt_part.attach(MIMEText(html_content, "html"))
    msg.attach(alt_part)

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
        "--report-dir", default="./reports", help="Directory where reports are stored."
    )
    parser.add_argument(
        "--mode",
        choices=["test", "prod"],
        default="test",
        help="Select email recipient mode (test sends to TEST_EMAIL_RECIPIENT; prod sends to PROD_EMAIL_RECIPIENTS).",
    )
    args = parser.parse_args()

    # --- 1. Load Config from Environment ---
    try:
        smtp_server = os.environ["PUBLISHER_SMTP_SERVER"]
        smtp_port = int(os.environ["PUBLISHER_SMTP_PORT"])
        sender_email = os.environ["PUBLISHER_EMAIL_SENDER"]
        sender_password = os.environ["PUBLISHER_EMAIL_PASSWORD"]
    except KeyError as e:
        print(f"Error: Missing required environment variable: {e}")
        print("Please set all PUBLISHER_* environment variables.")
        return

    # Resolve recipients based on mode and new env vars
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
        # Accept JSON list (preferred) or comma-separated string
        try:
            import ast
            import json

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                recipients = [str(x).strip() for x in parsed if str(x).strip()]
            else:
                recipients = [s.strip() for s in str(raw).split(",") if s.strip()]
        except Exception:
            recipients = [s.strip() for s in str(raw).split(",") if s.strip()]
        if not recipients:
            print(
                "Error: Could not parse PROD_EMAIL_RECIPIENTS into a non-empty recipient list"
            )
            return

    # --- 2. Load the Weekly Bets CSV ---
    bets_file = os.path.join(
        args.report_dir, str(args.year), f"CFB_week{args.week}_bets.csv"
    )
    if not os.path.exists(bets_file):
        print(f"Error: Bets file not found at {bets_file}")
        return

    all_games_df = pd.read_csv(bets_file)

    # Prepare recommended sets and context
    spreads, totals, best_bet = _prepare_recommended(all_games_df)
    generated_at = datetime.now().strftime("%m/%d/%Y %I:%M %p")

    # Thresholds (defaults; keep consistent with generator defaults)
    spread_threshold = 6.0
    total_threshold = 6.0

    summary = {
        "spread_bets": len(spreads),
        "total_bets_only": len(totals),
        "total_bets": len(spreads) + len(totals),
        "total_units": None,  # units not included in CSV
        "portfolio_cap": None,
    }

    repo_root = Path(__file__).resolve().parents[1]
    template_dir = repo_root / "templates"

    # Build full schedule for bottom table
    all_df = _compute_displays(all_games_df)
    all_df = (
        all_df.sort_values(["game_date_dt", "Game"])
        if "game_date_dt" in all_df.columns
        else all_df
    )
    all_games: list[dict[str, Any]] = []
    for _, r in all_df.iterrows():
        bet_side = str(r.get("Spread Bet", "")).strip().lower()
        raw_spread_reason = r.get("spread_bet_reason", None)
        raw_total_reason = r.get("total_bet_reason", None)

        def _map_reason(reason: str, edge: float | None, threshold: float) -> str:
            if not isinstance(reason, str):
                reason = None
            if reason:
                if "Min Games" in reason:
                    return "No Bet - Not enough FBS games yet"
                if "Small Edge" in reason:
                    return "No Bet - Edge below threshold"
                if "Low Confidence" in reason:
                    return "No Bet - Prediction uncertainty too high"
                if reason != "No Bet":
                    return reason
            # Infer reason when not explicitly provided
            if edge is not None and not pd.isna(edge):
                if edge < threshold:
                    return "No Bet - Edge below threshold"
            return "No Bet - Edge below threshold"

        game_str = str(r.get("Game", ""))
        home_from_game = None
        away_from_game = None
        if " @ " in game_str:
            away_from_game, home_from_game = game_str.split(" @ ", 1)
        home_name = r.get("home_team") or home_from_game or "home"
        away_name = r.get("away_team") or away_from_game or "away"

        if bet_side == "home":
            spread_bet_display = home_name
        elif bet_side == "away":
            spread_bet_display = away_name
        else:
            es = r.get("edge_spread")
            spread_bet_display = _map_reason(raw_spread_reason, es, spread_threshold)

        tb = str(r.get("Total Bet", "")).strip().lower()
        if tb in ("over", "under"):
            total_bet_display = tb.title()
        else:
            et = r.get("edge_total")
            total_bet_display = _map_reason(raw_total_reason, et, total_threshold)
        all_games.append(
            {
                "date_display": r.get("date_display", ""),
                "time_display": r.get("time_display", ""),
                "game": r.get("Game", ""),
                "home_team": home_name,
                "away_team": away_name,
                "spread_line_display": r.get("spread_line_display", ""),
                "total_line": _safe_float(r.get("total_line")),
                "predicted_spread": _safe_float(r.get("Spread Prediction")),
                "predicted_total": _safe_float(r.get("Total Prediction")),
                "edge_spread": _safe_float(r.get("edge_spread")),
                "edge_total": _safe_float(r.get("edge_total")),
                "spread_bet_display": spread_bet_display,
                "total_bet_display": total_bet_display,
            }
        )

    # Model context (prev year vs current to date)
    report_dir_path = Path(args.report_dir)
    (
        prev_spread,
        prev_total,
        prev_spread_roi,
        prev_total_roi,
        prev_spread_n,
        prev_total_n,
    ) = compute_hit_rates(args.year - 1, None, report_dir_path)
    (
        curr_spread,
        curr_total,
        curr_spread_roi,
        curr_total_roi,
        curr_spread_n,
        curr_total_n,
    ) = compute_hit_rates(args.year, args.week, report_dir_path)
    (
        lastyr_week_spr,
        lastyr_week_tot,
        lastyr_week_spr_roi,
        lastyr_week_tot_roi,
        lastyr_week_spr_n,
        lastyr_week_tot_n,
    ) = compute_week_hit_rates(args.year - 1, args.week, report_dir_path)
    model_context = {
        "prev_year": args.year - 1,
        "prev_spread": prev_spread,
        "prev_total": prev_total,
        "prev_spread_roi": prev_spread_roi,
        "prev_total_roi": prev_total_roi,
        "prev_spread_count": prev_spread_n,
        "prev_total_count": prev_total_n,
        "curr_year": args.year,
        "curr_through_week": args.week,
        "curr_spread": curr_spread,
        "curr_total": curr_total,
        "curr_spread_roi": curr_spread_roi,
        "curr_total_roi": curr_total_roi,
        "curr_spread_count": curr_spread_n,
        "curr_total_count": curr_total_n,
        "last_year_week_spread": lastyr_week_spr,
        "last_year_week_total": lastyr_week_tot,
        "last_year_week_spread_roi": lastyr_week_spr_roi,
        "last_year_week_total_roi": lastyr_week_tot_roi,
        "last_year_week_spread_count": lastyr_week_spr_n,
        "last_year_week_total_count": lastyr_week_tot_n,
    }

    context = {
        "year": args.year,
        "week": args.week,
        "generated_at": generated_at,
        "spread_threshold": spread_threshold,
        "total_threshold": total_threshold,
        "spreads": spreads,
        "totals": totals,
        "best_bet": best_bet,
        "summary": summary,
        "model_context": model_context,
        "all_games": all_games,
        "docs_url": "https://github.com/connorkitchings/cfb_model",
        "strong_spread_edge": spread_threshold + 2.0,
        "strong_total_edge": total_threshold + 2.0,
    }

    html = render_email_html(template_dir, context)
    text = build_plain_text(context)

    # --- 3. Send ---
    subject = f"CK's CFB Picks: {args.year} Week {args.week}"
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
        )
        print(
            f"Successfully sent picks for Week {args.week} to {', '.join(recipients)}."
        )
    except Exception as e:
        print(f"Error sending email: {e}")


if __name__ == "__main__":
    main()
