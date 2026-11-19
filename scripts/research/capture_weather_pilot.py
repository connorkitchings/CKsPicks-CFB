"""Capture NWS hourly forecast vintages for a bounded research slate."""

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkdtemp
from urllib.parse import urlsplit

import cfbd
import requests
from dotenv import load_dotenv

NWS = "https://api.weather.gov"


def utc_now():
    return datetime.now(timezone.utc)


def instant(value):
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("Timestamps must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def slate(week):
    config = cfbd.Configuration(access_token=os.environ["CFBD_API_KEY"])
    with cfbd.ApiClient(config) as client:
        games = cfbd.GamesApi(client).get_games(
            year=2026,
            week=week,
            season_type="regular",
            classification="fbs",
            _request_timeout=25,
        )
        venues = {
            venue.id: venue
            for venue in cfbd.VenuesApi(client).get_venues(_request_timeout=25)
        }
    rows = []
    for game in games:
        if (game.home_classification, game.away_classification) != ("fbs", "fbs"):
            continue
        venue = venues.get(game.venue_id)
        rows.append(
            {
                "game_id": game.id,
                "home_team": game.home_team,
                "away_team": game.away_team,
                "kickoff": game.start_date.isoformat(),
                "kickoff_tbd": game.start_time_tbd,
                "venue_id": game.venue_id,
                "venue": game.venue,
                "dome": venue.dome if venue else None,
                "latitude": venue.latitude if venue else None,
                "longitude": venue.longitude if venue else None,
            }
        )
    return sorted(rows, key=lambda row: (instant(row["kickoff"]), row["game_id"]))


def get_response(session, url, path):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "api.weather.gov":
        raise ValueError("Expected an NWS API URL")
    response = session.get(url, timeout=20, allow_redirects=False)
    retrieved = utc_now().isoformat()
    path.write_bytes(response.content)
    if response.status_code != 200:
        raise ValueError(f"NWS HTTP {response.status_code}")
    return response.json()["properties"], retrieved


def capture_game(session, row, output):
    kickoff = instant(row["kickoff"])
    if utc_now() >= kickoff:
        row["status"] = "already_started"
        return
    if row["latitude"] is None or row["longitude"] is None:
        row["status"] = "missing_coordinates"
        return
    game_id = row["game_id"]
    try:
        points, _ = get_response(
            session,
            f"{NWS}/points/{row['latitude']:.4f},{row['longitude']:.4f}",
            output / f"{game_id}_point.json",
        )
        forecast, retrieved = get_response(
            session,
            points["forecastHourly"],
            output / f"{game_id}_hourly.json",
        )
        row["retrieved_at"] = retrieved
        row["issued_at"] = forecast.get("updateTime")
        row["generated_at"] = forecast.get("generatedAt")
        if row["issued_at"] is not None:
            instant(row["issued_at"])
        row["forecast_hour"] = next(
            (
                period
                for period in forecast["periods"]
                if instant(period["startTime"]) <= kickoff < instant(period["endTime"])
            ),
            None,
        )
        row["status"] = "captured" if row["forecast_hour"] else "missing_forecast_hour"
    except (ValueError, KeyError, TypeError, requests.RequestException) as error:
        row["status"] = "forecast_error"
        row["error"] = str(error)


def coverage(rows, cutoff):
    counts = Counter(row["status"] for row in rows)
    counts["usable_at_issuance"] = 0
    for row in rows:
        if row["status"] != "captured":
            continue
        retrieved = instant(row["retrieved_at"])
        if cutoff < retrieved:
            counts["retrieved_after_cutoff"] += 1
        elif row["issued_at"] is None:
            counts["missing_issue_time"] += 1
        elif not instant(row["issued_at"]) <= retrieved < instant(row["kickoff"]):
            counts["invalid_forecast_timing"] += 1
        else:
            hour = row["forecast_hour"]
            precipitation = hour.get("probabilityOfPrecipitation") or {}
            if hour.get("windSpeed") and precipitation.get("value") is not None:
                counts["usable_at_issuance"] += 1
            else:
                counts["missing_weather_fields"] += 1
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture")
    capture.add_argument("--week", type=int, choices=(12, 13, 14), required=True)
    capture.add_argument("--output", type=Path, required=True)
    report = commands.add_parser("report")
    report.add_argument("receipt", type=Path)
    report.add_argument("revision", type=Path)
    args = parser.parse_args()
    if args.command == "report":
        receipt = json.loads(args.receipt.read_text())
        revision = json.loads(args.revision.read_text())
        week = receipt["week"]
        if revision["season"] != receipt["season"] or (
            week in (13, 14)
            and args.revision.name != f"revision_manifest_w{week}_v1.json"
        ):
            parser.error("use the initial rollover revision for the captured slate")
        cutoff = instant(revision["pre_week_cutoffs"][str(week)])
        print(json.dumps(coverage(receipt["games"], cutoff), indent=2, sort_keys=True))
        return

    load_dotenv(os.getenv("CFB_WEATHER_ENV_FILE") or None)
    if args.output.exists():
        parser.error("capture output already exists")
    slate_requested_at = utc_now().isoformat()
    rows = slate(args.week)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    attempt = Path(mkdtemp(prefix=f".{args.output.name}-", dir=args.output.parent))
    with requests.Session() as session:
        session.headers["User-Agent"] = "CKsPicks-CFB weather research pilot"
        selected = 0
        for row in rows:
            if args.week == 12 and instant(row["kickoff"]) <= utc_now():
                row["status"] = "already_started"
                continue
            if row["dome"] is False and not row["kickoff_tbd"] and selected < 10:
                selected += 1
                capture_game(session, row, attempt)
            else:
                row["status"] = (
                    "unknown_roof"
                    if row["dome"] is None
                    else "indoor"
                    if row["dome"]
                    else "kickoff_tbd"
                    if row["kickoff_tbd"]
                    else "outside_sample"
                )
    receipt = {
        "season": 2026,
        "week": args.week,
        "slate_requested_at": slate_requested_at,
        "status": "completed" if rows else "no_fbs_vs_fbs_schedule",
        "games": rows,
    }
    (attempt / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    attempt.rename(args.output)
    print(args.output / "receipt.json")
    print(receipt["status"])
    print(dict(Counter(row["status"] for row in rows)))


if __name__ == "__main__":
    main()
