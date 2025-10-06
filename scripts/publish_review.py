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
from typing import List, Tuple

import pandas as pd
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape


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
        args.report_dir, str(args.year), f"CFB_week{args.week}_bets_scored.csv"
    )
    if not os.path.exists(bets_file):
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
    all_games_df["game_datetime_utc"] = pd.to_datetime(
        all_games_df["Date"] + " " + all_games_df["Time"], utc=True
    )
    all_games_df["game_datetime_et"] = all_games_df["game_datetime_utc"].dt.tz_convert(
        "US/Eastern"
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

    bets = []
    for _, row in all_games_df.iterrows():
        if (
            row["Spread Bet"] in ["home", "away"]
            and row["Spread Bet Result"] != "Pending"
        ):
            if row["Spread Bet"] == "home":
                bet_team = row["home_team"]
                line = row["home_team_spread_line"]
                bet_string = f"{bet_team} {line:+.1f}"
            else:
                bet_team = row["away_team"]
                line = -row["home_team_spread_line"]
                bet_string = f"{bet_team} {line:+.1f}"
            bets.append(
                {
                    "game": row["Game"],
                    "bet": bet_string,
                    "result": row["Spread Bet Result"],
                    "final_score": f"{row['away_points']} - {row['home_points']}",
                    "date": row["date_display"],
                    "time": row["time_display"],
                    "prediction": row["Spread Prediction"],
                }
            )
        if (
            row["Total Bet"] in ["over", "under"]
            and row["Total Bet Result"] != "Pending"
        ):
            bets.append(
                {
                    "game": row["Game"],
                    "bet": f"{row['Total Bet'].capitalize()} {row['Over/Under']}",
                    "result": row["Total Bet Result"],
                    "final_score": f"{row['away_points']} - {row['home_points']}",
                    "date": row["date_display"],
                    "time": row["time_display"],
                    "prediction": row["Total Prediction"],
                }
            )

    repo_root = Path(__file__).resolve().parents[1]
    template_dir = repo_root / "templates"

    context = {
        "year": args.year,
        "week": args.week,
        "generated_at": datetime.now().strftime("%m/%d/%Y %I:%M %p"),
        "summary": summary,
        "bets": bets,
        "docs_url": "https://github.com/connorkitchings/cfb_model",
    }

    html = render_email_html(template_dir, context)
    text = "Please enable HTML to view this email."

    # --- 4. Send ---
    subject = f"CK's CFB Picks: {args.year} Week {args.week} Review"
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
            f"Successfully sent review for Week {args.week} to {', '.join(recipients)}."
        )
    except Exception as e:
        print(f"Error sending email: {e}")


if __name__ == "__main__":
    main()
