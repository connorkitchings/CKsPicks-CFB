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
import json
import os
import re
import smtplib
import sys
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Tuple

import pandas as pd
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.config import PREDICTIONS_SUBDIR, REPORTS_DIR, SCORED_SUBDIR  # noqa: E402

TEAM_LOGO_MAP = {
    "Sam Houston": "Sam Houston State",
    "UL Monroe": "Louisiana Monroe",
    "Massachusetts": "UMass",
    "App State": "Appalachian State",
    "San José State": "San Jose State",
    "UTSA": "UT San Antonio",
    "Hawai'i": "Hawai_i",
    "UConn": "Connecticut",
    "Southern Miss": "Southern Mississippi",
}


def _logo_cid_for(name: str | None) -> str:
    if not name:
        return ""
    mapped = TEAM_LOGO_MAP.get(name, name)
    return f"logo_{str(mapped).replace(' ', '_')}"


def render_email_html(template_dir: Path, context):
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tmpl = env.get_template("email_last_week_review.html")
    return tmpl.render(**context)


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
    """Send an email using SMTP with HTML, plaintext, and optional attachments.

    attachments: list of (filename, bytes_content, mime_type)
    """
    # related container for inline images with an alternative part for text/html
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(text_content, "plain"))
    alt_part.attach(MIMEText(html_content, "html"))
    msg.attach(alt_part)

    # Attach inline images
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
                return num if "+" in num_part or num_part.startswith("0") else -abs(num)
            if away in txt:
                return -num if "+" in num_part or num_part.startswith("0") else abs(num)
    except Exception:
        pass
    return None


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
    # Try production scored first
    prod_scored = Path(
        f"data/production/scored/{args.year}/CFB_week{args.week}_bets_scored.csv"
    )

    if prod_scored.exists():
        bets_file = prod_scored
    else:
        # Fallback to reports dir
        report_dir_path = Path(args.report_dir)
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
        print(f"Error: Bets file not found at {bets_file}")
        return

    all_games_df = pd.read_csv(bets_file)
    game_parts = all_games_df["Game"].str.split(" @ ", expand=True)
    all_games_df["away_team"] = game_parts[0]
    all_games_df["home_team"] = game_parts[1]
    all_games_df["home_team_spread_line"] = all_games_df.apply(_parse_spread, axis=1)
    all_games_df["home_points"] = (
        all_games_df["Spread Result"] + all_games_df["Total Result"]
    ) / 2
    all_games_df["away_points"] = (
        all_games_df["Total Result"] - all_games_df["Spread Result"]
    ) / 2
    # Interpret the report's Date/Time as Eastern Time (not UTC)
    # The report times are already in ET; localize instead of converting from UTC
    dt_naive = pd.to_datetime(
        all_games_df["Date"] + " " + all_games_df["Time"], errors="coerce"
    )
    all_games_df["game_datetime_et"] = dt_naive.dt.tz_localize(
        "US/Eastern", ambiguous="infer"
    )
    all_games_df["date_display"] = all_games_df["game_datetime_et"].dt.strftime(
        "%m/%d/%Y"
    )
    all_games_df["time_display"] = all_games_df["game_datetime_et"].dt.strftime(
        "%I:%M %p"
    )
    all_games_df = all_games_df.sort_values(by="game_datetime_et")

    # --- 3. Process Data for Email ---
    spread_bets = all_games_df[all_games_df["Spread Bet"].isin(["home", "away"])].copy()
    total_bets = all_games_df[all_games_df["Total Bet"].isin(["over", "under"])].copy()

    spread_wins = (spread_bets["Spread Bet Result"] == "Win").sum()
    spread_losses = (spread_bets["Spread Bet Result"] == "Loss").sum()
    spread_hit_rate = (
        spread_wins / (spread_wins + spread_losses)
        if (spread_wins + spread_losses) > 0
        else 0
    )

    total_wins = (total_bets["Total Bet Result"] == "Win").sum()
    total_losses = (total_bets["Total Bet Result"] == "Loss").sum()
    total_hit_rate = (
        total_wins / (total_wins + total_losses)
        if (total_wins + total_losses) > 0
        else 0
    )

    summary = {
        "spread_wins": spread_wins,
        "spread_losses": spread_losses,
        "spread_hit_rate": spread_hit_rate,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "total_hit_rate": total_hit_rate,
    }

    # --- Season-to-date Summary (up to supplied week) ---
    season_summary = None
    season_frames: list[pd.DataFrame] = []
    season_root = report_dir_path / str(args.year)
    season_files = sorted(
        season_root.rglob("CFB_week*_bets_scored.csv"),
        key=lambda p: p.name,
    )
    for scored_path in season_files:
        match = re.search(r"CFB_week(\d+)_bets_scored\.csv", scored_path.name)
        if not match:
            continue
        week_num = int(match.group(1))
        if week_num > args.week:
            continue
        season_frames.append(pd.read_csv(scored_path))

    if season_frames:
        season_df = pd.concat(season_frames, ignore_index=True)

        def _record(
            df: pd.DataFrame, bet_col: str, result_col: str
        ) -> tuple[int, int, float]:
            mask = (
                df[bet_col].isin(["home", "away"])
                if bet_col == "Spread Bet"
                else df[bet_col].isin(["over", "under"])
            )
            outcomes = df.loc[mask & df[result_col].isin(["Win", "Loss"]), result_col]
            wins = int((outcomes == "Win").sum())
            losses = int((outcomes == "Loss").sum())
            hit_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0
            return wins, losses, hit_rate

        season_spread_wins, season_spread_losses, season_spread_hit = _record(
            season_df, "Spread Bet", "Spread Bet Result"
        )
        season_total_wins, season_total_losses, season_total_hit = _record(
            season_df, "Total Bet", "Total Bet Result"
        )

        season_summary = {
            "spread_wins": season_spread_wins,
            "spread_losses": season_spread_losses,
            "spread_hit_rate": season_spread_hit,
            "total_wins": season_total_wins,
            "total_losses": season_total_losses,
            "total_hit_rate": season_total_hit,
        }

    # Remove only full row duplicates (same game with identical bet types)
    all_games_df = all_games_df.drop_duplicates()

    bets = []
    for _, row in all_games_df.iterrows():
        home_team = row.get("home_team")
        away_team = row.get("away_team")
        home_logo_cid = _logo_cid_for(home_team) if pd.notna(home_team) else ""
        away_logo_cid = _logo_cid_for(away_team) if pd.notna(away_team) else ""

        # Spread bet row (if present)
        if row["Spread Bet"] in ["home", "away"]:
            # Line column (spread text from report)
            line_text = (
                row.get("Spread") if isinstance(row.get("Spread"), str) else None
            )
            # Bet text (team + signed number)
            if row["Spread Bet"] == "home":
                bet_team = row["home_team"]
                bet_text = f"{bet_team}" if bet_team else ""
            else:
                bet_team = row["away_team"]
                bet_text = f"{bet_team}" if bet_team else ""
            # Final score and final result (spread margin)
            final_score = (
                f"{int(row['away_points'])} - {int(row['home_points'])}"
                if pd.notna(row["home_points"]) and pd.notna(row["away_points"])
                else "Data Issue"
            )
            final_result = (
                float(row["Spread Result"])
                if pd.notna(row.get("Spread Result"))
                else None
            )
            line_display = (
                line_text
                if line_text
                else (
                    f"{row['home_team']} {row['home_team_spread_line']:+.1f}"
                    if pd.notna(row.get("home_team_spread_line"))
                    else ""
                )
            )
            bets.append(
                {
                    "date": row["date_display"],
                    "time": row["time_display"],
                    "game": row["Game"],
                    "line": line_display,
                    "prediction": float(row["Spread Prediction"])
                    if pd.notna(row.get("Spread Prediction"))
                    else None,
                    "bet": bet_text,
                    "final_score": final_score,
                    "final_result": final_result,
                    "bet_result": row["Spread Bet Result"],
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_team_logo_cid": home_logo_cid,
                    "away_team_logo_cid": away_logo_cid,
                }
            )

        # Total bet row (if present)
        if row["Total Bet"] in ["over", "under"]:
            line_text = row.get("Over/Under")
            bet_text = f"{row['Total Bet'].capitalize()}"
            final_score = (
                f"{int(row['away_points'])} - {int(row['home_points'])}"
                if pd.notna(row["home_points"]) and pd.notna(row["away_points"])
                else "Data Issue"
            )
            final_result = (
                float(row["Total Result"])
                if pd.notna(row.get("Total Result"))
                else None
            )
            bets.append(
                {
                    "date": row["date_display"],
                    "time": row["time_display"],
                    "game": row["Game"],
                    "line": f"O/U {line_text}",
                    "prediction": float(row["Total Prediction"])
                    if pd.notna(row.get("Total Prediction"))
                    else None,
                    "bet": bet_text,
                    "final_score": final_score,
                    "final_result": final_result,
                    "bet_result": row["Total Bet Result"],
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_team_logo_cid": home_logo_cid,
                    "away_team_logo_cid": away_logo_cid,
                }
            )

    repo_root = Path(__file__).resolve().parents[2]
    template_dir = repo_root / "templates"

    metadata_dir = report_dir_path / str(args.year) / PREDICTIONS_SUBDIR
    metadata_file = metadata_dir / f"CFB_week{args.week}_bets_metadata.json"
    spread_threshold = None
    total_threshold = None
    if metadata_file.exists():
        try:
            with metadata_file.open("r", encoding="utf-8") as fh:
                metadata_payload = json.load(fh)
            thresholds = metadata_payload.get("betting_thresholds") or {}
            spread_threshold = thresholds.get("spread_edge")
            total_threshold = thresholds.get("total_edge")
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Warning: Unable to load metadata from {metadata_file}: {exc}")

    edge_thresholds = None
    if spread_threshold is not None or total_threshold is not None:
        edge_thresholds = {
            "spread": spread_threshold,
            "total": total_threshold,
        }

    context = {
        "year": args.year,
        "week": args.week,
        "generated_at": datetime.now().strftime("%m/%d/%Y %I:%M %p"),
        "summary": summary,
        "season_summary": season_summary,
        "bets": bets,
        "docs_url": "https://github.com/connorkitchings/cfb_model",
        "edge_thresholds": edge_thresholds,
    }

    html = render_email_html(template_dir, context)
    text = "Please enable HTML to view this email."

    # Inline logo images referenced by CID
    cids_in_html = set(re.findall(r"cid:([^\"']+)", html))
    image_attachments: List[MIMEImage] = []
    logo_dir = REPO_ROOT / "Logos"
    for cid in sorted(cids_in_html):
        if not cid.startswith("logo_"):
            continue
        name_part = cid[len("logo_") :].replace("_", " ")
        logo_name = TEAM_LOGO_MAP.get(name_part, name_part)
        logo_path = logo_dir / f"{logo_name}.png"
        if not logo_path.exists():
            continue
        with open(logo_path, "rb") as f:
            img_data = f.read()
        img = MIMEImage(img_data)
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline", filename=logo_path.name)
        image_attachments.append(img)

    # --- 4. Send or preview ---
    subject = f"CK's CFB Picks: {args.year} Week {args.week} Review"
    if args.dry_run:
        preview_dir = report_dir_path / str(args.year) / "email_previews"
        preview_dir.mkdir(parents=True, exist_ok=True)
        html_path = preview_dir / f"week_{args.week:02d}_review.html"
        text_path = preview_dir / f"week_{args.week:02d}_review.txt"
        html_path.write_text(html, encoding="utf-8")
        text_path.write_text(text, encoding="utf-8")
        print(
            f"Dry run enabled; wrote HTML preview to {html_path} and text preview to {text_path}."
        )
        return

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
            image_attachments=image_attachments,
        )
        print(
            f"Successfully sent review for Week {args.week} to {', '.join(recipients)}."
        )
    except Exception as e:
        print(f"Error sending email: {e}")


if __name__ == "__main__":
    main()
