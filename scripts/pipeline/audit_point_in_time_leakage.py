#!/usr/bin/env python3
"""Read immutable R2 evidence and audit the unified 2026 V5 record. No cloud writes."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.audit.point_in_time import run_audit, violation
from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.models.late_quotes import validate_late_evidence
from cks_picks_cfb.ratings_lab.artifacts import canonical_json

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.pipeline.audit_corrected_replay_chain import (  # noqa: E402
    ReadOnlyEvidence,
    sha,
)

ROOT = "artifacts/research/data-first-football-v1"
RATING_ROOT = ROOT + "/possession-v1/intended-update-2026/runs/"
DEFAULT_BRIDGE = (
    ROOT
    + "/forecasts/intended-update/runs/v5-intended-update-corrected-w5-r1/bridge-manifest.json"
)


class Evidence(ReadOnlyEvidence):
    def checked(self, uri, digest):
        raw = self.read_bytes(uri)
        if not digest or sha(raw) != digest:
            raise ValueError(f"checksum differs: {uri}")
        return raw

    def document(self, uri, digest=None, signed=False):
        raw = self.checked(uri, digest) if digest else self.read_bytes(uri)
        obj = json.loads(raw)
        if signed:
            verify_signed_payload(obj, label=uri)
        return obj

    def frame(self, ref):
        raw = self.checked(ref["uri"], ref.get("raw_sha256", ref.get("content_sha")))
        return (
            pd.read_csv(io.BytesIO(raw))
            if ref["uri"].endswith(".csv")
            else pd.read_parquet(io.BytesIO(raw))
        )


def load_week(source, *, manifest_uri, lock, rating_uri, bridge):
    manifest = source.document(manifest_uri)
    week = int(manifest["week"])
    if (
        manifest.get("season") != 2026
        or f"week={week}/run_id={manifest['run_id']}/" not in manifest_uri
    ):
        raise ValueError("run manifest identity differs from requested artifact")
    predictions = source.frame(
        {"uri": manifest["artifact_uri"], "raw_sha256": manifest["artifact_sha256"]}
    )
    if (
        predictions.game_id.duplicated().any()
        or len(predictions) != manifest["expected_games"]
    ):
        raise ValueError("prediction coverage differs")
    forecast = source.document(
        manifest["v5_live_forecast_manifest_uri"],
        manifest["v5_live_forecast_manifest_sha256"],
        signed=True,
    )
    forecast_rows = source.frame(forecast["prediction_ref"])
    if (
        set(forecast_rows.game_id) != set(predictions.game_id)
        or forecast_rows.duplicated(["game_id", "target"]).any()
        or len(forecast_rows) != 2 * len(predictions)
    ):
        raise ValueError("forecast target coverage differs")
    rating = source.document(
        rating_uri, manifest["v5_rating_replay_manifest_sha256"], signed=True
    )
    if forecast["parents"]["bridge_manifest_raw_sha256"] != sha(
        source.read_bytes(bridge["uri"])
    ):
        raise ValueError("bridge parent differs")
    if forecast["parents"]["source_lock_sha256"] != lock["_audit_raw_sha256"]:
        raise ValueError("forecast source lock differs")
    roles = source.frame(rating["output_refs"]["pregame_roles"])
    schedule = pd.DataFrame(lock["games"]["rows"], columns=lock["games"]["columns"])
    slate = schedule[schedule.game_id.isin(predictions.game_id)].copy()
    if len(slate) != len(predictions):
        raise ValueError("schedule coverage differs")
    slate = slate.rename(columns={"start_date": "kickoff_utc"})
    states, history, forecasts = [], [], []
    source_games = schedule.set_index("game_id")
    for game in slate.itertuples():
        selected = roles[roles.game_id.eq(game.game_id)]
        if len(selected) != 4 or selected.duplicated(["team", "unit_role"]).any():
            raise ValueError("rating role coverage differs")
        state_ref = f"rating:{manifest['v5_rating_replay_manifest_sha256']}#pregame:{int(game.game_id)}"
        if set(
            forecast_rows.loc[forecast_rows.game_id.eq(game.game_id), "state_ref"]
        ) != {state_ref}:
            raise ValueError("forecast state binding differs")
        cutoffs = pd.to_datetime(selected.cutoff_utc, utc=True).unique()
        if len(cutoffs) != 1:
            raise ValueError("teams have different state cutoffs")
        cutoff = forecast.get("live", {}).get(
            "as_of", pd.Timestamp(cutoffs[0]).isoformat()
        )
        forecasts.append(
            {
                "game_id": int(game.game_id),
                "run_id": manifest["run_id"],
                "forecast_as_of": cutoff,
                "market_as_of": manifest["data_as_of"],
            }
        )
        for role in selected.itertuples():
            states.append(
                {
                    "game_id": int(game.game_id),
                    "team": role.team,
                    "state_cutoff_utc": role.cutoff_utc,
                }
            )
            for source_id in json.loads(role.source_game_ids):
                if int(source_id) not in source_games.index:
                    raise ValueError("rating history source has no schedule")
                origin = source_games.loc[int(source_id)]
                history.append(
                    {
                        "game_id": int(game.game_id),
                        "team": role.team,
                        "source_game_id": int(source_id),
                        "source_week": int(origin.week),
                        "source_kickoff_utc": origin.start_date,
                    }
                )
    snapshot_ref = next(
        ref
        for ref in manifest["input_dataset_refs"]
        if ref["dataset"] == "market_snapshots"
    )
    snapshots = source.frame(snapshot_ref)
    snapshots = snapshots[snapshots.game_id.isin(predictions.game_id)]
    if len(snapshots) != len(predictions) or snapshots.game_id.duplicated().any():
        raise ValueError("market snapshot coverage differs")
    snapshot_by_game = snapshots.set_index("game_id")
    quote_ref = next(
        ref
        for ref in manifest["input_dataset_refs"]
        if ref["dataset"] == "market_quotes"
    )
    quotes = source.frame(quote_ref).set_index("quote_id")
    selected_quotes = []
    for row in predictions.to_dict("records"):
        for target in ["spread", "total"]:
            quote_id = row.get(target + "_market_quote_id")
            if pd.isna(quote_id):
                continue
            quote = quotes.loc[str(quote_id)]
            snapshot = snapshot_by_game.loc[int(row["game_id"])]
            linked = snapshot["source_quote_ids"]
            linked = json.loads(linked) if isinstance(linked, str) else linked
            if str(quote_id) not in {str(item) for item in linked}:
                raise ValueError(
                    "selected quote is not linked to the canonical snapshot"
                )
            if int(quote.game_id) != int(row["game_id"]):
                raise ValueError("selected quote game differs")
            selected_quotes.append(
                {
                    "game_id": int(row["game_id"]),
                    "target": target,
                    "quote_id": str(quote_id),
                    "captured_at": quote.captured_at,
                    "provider": quote.get("__capture_provider"),
                    "entity": "betting_lines"
                    if quote.get("__capture_provider") == "cfbd"
                    else "unknown",
                }
            )
    f = pd.DataFrame(forecasts)
    run = {
        "week": week,
        "run_id": manifest["run_id"],
        "forecast_as_of": min(pd.to_datetime(f.forecast_as_of, utc=True)).isoformat(),
        "market_as_of": manifest["data_as_of"],
        "market_snapshot_captured_at": sorted(
            {pd.Timestamp(stamp).isoformat() for stamp in snapshots.market_captured_at}
        ),
        "display_only": manifest.get("display_only", False),
        "per_game_cutoffs": "live" not in forecast,
        "evidence_class": manifest["evidence_class"],
    }
    return slate, f, states, history, selected_quotes, run, manifest


def audit_statistics(cur, source, *, through_week):
    """Rebuild serving snapshots after independently removing all same/later-week rows."""
    from cks_picks_cfb.data.team_stats import build_team_season_stats
    from scripts.pipeline.publish_team_stats import _silver_ref

    cur.execute(
        "SELECT team, as_of_week, role, metric, value, n, games, rank, cohort_size, source_versions "
        "FROM team_season_stats WHERE season = 2026 AND as_of_week <= %s "
        "ORDER BY as_of_week, team, role, metric",
        (through_week,),
    )
    actual = pd.DataFrame(
        cur.fetchall(),
        columns=[
            "team",
            "as_of_week",
            "role",
            "metric",
            "value",
            "n",
            "games",
            "rank",
            "cohort_size",
            "source_versions",
        ],
    )
    evidence, violations = [], []
    for week, rows in actual.groupby("as_of_week"):
        versions = {json.dumps(item, sort_keys=True) for item in rows.source_versions}
        if len(versions) != 1:
            violations.append(
                violation(
                    "f_team_stats", None, int(week), "snapshot mixes source versions"
                )
            )
            continue
        pins = json.loads(next(iter(versions)))
        frames = {}
        for name in ["byplay", "drives", "games", "game_outcomes", "teams"]:
            if name not in pins:
                raise ValueError("team statistics lack pinned " + name + " provenance")
            ref = _silver_ref(cur, name, 2026, pins[name])
            frames[name] = source.frame(
                {"uri": ref.uri, "content_sha": ref.content_sha}
            )
        games = frames["games"]
        eligible = games[
            games.season.eq(2026) & pd.to_numeric(games.week).lt(int(week))
        ]
        source_ids = set(eligible.game_id.astype(int))
        for name in ["byplay", "drives", "game_outcomes"]:
            frames[name] = frames[name][frames[name].game_id.isin(source_ids)]
        teams = frames["teams"]
        fbs = set(
            teams.loc[
                teams.classification.astype(str).str.lower().eq("fbs"), "team"
            ].astype(str)
        )
        rebuilt = build_team_season_stats(
            byplay=frames["byplay"],
            drives=frames["drives"],
            games=eligible,
            outcomes=frames["game_outcomes"],
            fbs_teams=fbs,
            season=2026,
            as_of_week=int(week),
        ).frame
        keys = ["team", "role", "metric"]
        left = rows.set_index(keys)
        right = rebuilt.set_index(keys)
        same = set(left.index) == set(right.index)
        if same:
            right = right.reindex(left.index)
            for column in ["value", "n", "games", "rank", "cohort_size"]:
                a = pd.to_numeric(left[column], errors="coerce")
                b = pd.to_numeric(right[column], errors="coerce")
                if not ((a.isna() & b.isna()) | ((a - b).abs() <= 1e-9)).all():
                    same = False
                    break
        if not same:
            violations.append(
                violation(
                    "f_team_stats",
                    None,
                    int(week),
                    "serving stats differ from independently time-trimmed source rebuild",
                )
            )
        evidence.append(
            {
                "as_of_week": int(week),
                "source_versions": pins,
                "serving_rows": len(rows),
                "source_game_weeks": [
                    (int(g.game_id), int(g.week)) for g in eligible.itertuples()
                ],
                "time_trimmed_rebuild_matches": same,
            }
        )
    return (
        [(str(row.team), int(row.as_of_week)) for row in actual.itertuples()],
        evidence,
        violations,
    )


def audit(
    source,
    *,
    environment,
    through_week,
    locks,
    rating_uris,
    bridge_uri,
    runs,
    stats_rows,
    stats_evidence=(),
    stats_violations=(),
):
    for lock in locks.values():
        for market in lock["market_sources"].values():
            validate_late_evidence(
                market.get("accepted_late_quotes", []),
                market.get("cfbd_comparison_receipt"),
            )
    bridge = source.document(bridge_uri, signed=True)
    bundle_ref = bridge["output_refs"]["inference_bundle"]
    bundle = source.document(bundle_ref["uri"], bundle_ref["raw_sha256"])
    frames, forecasts, states, history, quotes, run_rows, violations = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for week in range(through_week + 1):
        uri = f"artifacts/{environment}/predictions/year=2026/week={week}/run_id={runs[week]}/manifest.json"
        g, f, s, h, q, r, m = load_week(
            source,
            manifest_uri=uri,
            lock=locks[week],
            rating_uri=rating_uris[week],
            bridge={"uri": bridge_uri},
        )
        frames.append(g)
        forecasts.append(f)
        states.extend(s)
        history.extend(h)
        quotes.extend(q)
        run_rows.append(r)
        if m["inference_bundle_sha256"] != bundle_ref["raw_sha256"]:
            violations.append(
                violation(
                    "e_model_parameters",
                    None,
                    week,
                    "run bundle differs from audited bundle",
                )
            )
        if not r["per_game_cutoffs"]:
            # A display/live run forecasts its slate from one as_of; it must precede
            # the slate's first scheduled kickoff. Replays are checked per game on
            # event time by run_audit.
            lock = locks[week]
            schedule = pd.DataFrame(
                lock["games"]["rows"], columns=lock["games"]["columns"]
            )
            first_kickoff = pd.to_datetime(
                schedule.loc[schedule.week.astype(int).eq(week), "start_date"], utc=True
            ).min()
            if (pd.to_datetime(f.forecast_as_of, utc=True) >= first_kickoff).any():
                violations.append(
                    violation(
                        "c_forecast_time",
                        None,
                        week,
                        f"display/live forecast must precede the slate's first kickoff "
                        f"{first_kickoff.isoformat()}",
                    )
                )
        if week == 6 and len(g) != 58:
            violations.append(
                violation(
                    "g_cutoff_coherence",
                    None,
                    week,
                    "Week 6 complete-slate receipt requires all 58 games",
                )
            )
    violations.extend(stats_violations)
    games = pd.concat(frames, ignore_index=True)
    # This is the web query's actual per-game statistics lookup: latest snapshot <= game week.
    usage = []
    for game in games.itertuples():
        available = [
            int(r[1])
            for r in stats_rows
            if int(r[1]) == int(game.week) and r[0] in (game.home_team, game.away_team)
        ]
        if available:
            usage.append(
                {"game_id": int(game.game_id), "stats_as_of_week": max(available)}
            )
    receipt = run_audit(
        games=games,
        forecasts=pd.concat(forecasts, ignore_index=True),
        runs=pd.DataFrame(run_rows),
        history=pd.DataFrame(
            history,
            columns=[
                "game_id",
                "team",
                "source_game_id",
                "source_week",
                "source_kickoff_utc",
            ],
        ),
        states=pd.DataFrame(states),
        quotes=pd.DataFrame(
            quotes,
            columns=[
                "game_id",
                "target",
                "quote_id",
                "captured_at",
                "provider",
                "entity",
            ],
        ),
        accepted_late=[
            item
            for w in locks.values()
            for market in w["market_sources"].values()
            for item in market.get("accepted_late_quotes", [])
        ],
        bundle=bundle,
        declared_bundle_sha256=bundle_ref["raw_sha256"],
        bundle_file_sha256=sha(source.read_bytes(bundle_ref["uri"])),
        team_stats_usage=pd.DataFrame(usage, columns=["game_id", "stats_as_of_week"]),
        environment=environment,
        inputs={
            "objects": {uri: sha(raw) for uri, raw in sorted(source.raw.items())},
            "cutoffs": run_rows,
            "team_stats_snapshots": stats_rows,
            "team_stats_membership": list(stats_evidence),
            "team_stats_builder_sha256": sha(
                Path("src/cks_picks_cfb/data/team_stats.py").read_bytes()
            ),
            "limits": [
                "Statistics are compared with a rebuild from the recorded source versions after independently excluding every same/later-week game."
            ],
        },
    )
    for item in violations:
        for game in receipt["games"]:
            if item["game_id"] == game["game_id"] or (
                item["game_id"] is None
                and (item["week"] is None or item["week"] == game["week"])
            ):
                game["passed"] = False
    if violations:
        receipt.pop("manifest_sha256")
        receipt["violations"].extend(violations)
        for item in violations:
            receipt["violation_counts"][item["rule"]] += 1
        receipt["state"] = "failed"
        receipt = signed_payload(receipt)
    return receipt


MAX_WEEK = 7
# Corrected replay runs that already pass the audit; later weeks must be named with --run.
DEFAULT_REPLAY_RUN_WEEKS = range(6)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--environment", choices=["preview", "production"], required=True)
    p.add_argument("--season", type=int, choices=[2026], required=True)
    p.add_argument(
        "--through-week", type=int, choices=range(MAX_WEEK + 1), required=True
    )
    p.add_argument(
        "--source-lock",
        type=Path,
        default=Path("conf/rebuild/successor_lock_w5_v1.json"),
    )
    p.add_argument("--bridge-uri", default=DEFAULT_BRIDGE)
    p.add_argument(
        "--rating-uri",
        default=RATING_ROOT
        + "v5-intended-update-2026-corrected-w5-r1/rating-manifest.json",
    )
    p.add_argument(
        "--live-week",
        type=int,
        choices=range(MAX_WEEK + 1),
        help="week audited with --live-source-lock/--live-rating-uri (default: none)",
    )
    p.add_argument("--live-source-lock", type=Path)
    p.add_argument("--live-rating-uri")
    p.add_argument(
        "--run", action="append", default=[], help="override exact WEEK=RUN_ID"
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/audit/leakage_audit_receipt_2026.json"),
    )
    args = p.parse_args(argv)
    weeks = range(args.through_week + 1)
    args.runs = {
        w: f"2026w{w}-v5repair-20261008-c2"
        for w in weeks
        if w in DEFAULT_REPLAY_RUN_WEEKS
    }
    for item in args.run:
        week, sep, run = item.partition("=")
        if not sep or not week.isdigit() or int(week) not in weeks or not run:
            p.error(f"--run must be WEEK=RUN_ID with WEEK in 0..{args.through_week}")
        args.runs[int(week)] = run
    if missing := [w for w in weeks if w not in args.runs]:
        p.error(f"--run WEEK=RUN_ID required for week(s) {missing}")
    if args.live_week is not None:
        if args.live_week not in weeks:
            p.error("--live-week must be within --through-week")
        if args.live_source_lock is None or args.live_rating_uri is None:
            p.error("--live-week requires --live-source-lock and --live-rating-uri")
    return args


def week_inputs(args):
    """Each audited week's source lock and rating URI; only --live-week uses the live pair."""
    locks, ratings = {}, {}
    for week in args.runs:
        live = week == args.live_week
        raw = (args.live_source_lock if live else args.source_lock).read_bytes()
        locks[week] = {**json.loads(raw), "_audit_raw_sha256": sha(raw)}
        ratings[week] = args.live_rating_uri if live else args.rating_uri
    return locks, ratings


def main():
    load_dotenv()
    args = parse_args()
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("audit requires explicit R2 backend")
    if Path("data").resolve() in [
        args.output.resolve(),
        *args.output.resolve().parents,
    ]:
        raise SystemExit("audit output cannot be repository ./data")
    runs = args.runs
    locks, ratings = week_inputs(args)
    url = os.getenv(
        "PREVIEW_DATABASE_URL" if args.environment == "preview" else "DATABASE_URL"
    )
    if not url:
        raise SystemExit("serving database URL required for statistics verification")
    source = Evidence(get_storage(environment=args.environment))
    with psycopg.connect(url, options="-c default_transaction_read_only=on") as conn:
        with conn.cursor() as cur:
            stats, stats_evidence, stats_violations = audit_statistics(
                cur, source, through_week=args.through_week
            )
    receipt = audit(
        source,
        environment=args.environment,
        through_week=args.through_week,
        locks=locks,
        rating_uris=ratings,
        bridge_uri=args.bridge_uri,
        runs=runs,
        stats_rows=stats,
        stats_evidence=stats_evidence,
        stats_violations=stats_violations,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as out:
        out.write(canonical_json(receipt))
    print(
        json.dumps(
            {
                key: receipt[key]
                for key in ["state", "games_checked", "violation_counts"]
            }
        )
    )
    return 0 if receipt["state"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
