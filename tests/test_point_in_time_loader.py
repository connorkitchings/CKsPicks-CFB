"""Exercise the artifact loader with checksummed, signed in-memory evidence."""

import io
import json

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from scripts.pipeline.audit_corrected_replay_chain import sha
from scripts.pipeline.audit_point_in_time_leakage import (
    Evidence,
    audit,
    load_week,
    parse_args,
    week_inputs,
)
from scripts.pipeline.verify_cfbd_closing_lines import compare_lines


class Storage:
    def __init__(self):
        self.objects = {}

    def read_bytes(self, uri):
        return self.objects[uri]

    def put(self, uri, value):
        raw = json.dumps(value).encode()
        self.objects[uri] = raw
        return sha(raw)

    def frame(self, uri, rows):
        frame = pd.DataFrame(rows)
        if uri.endswith(".csv"):
            raw = frame.to_csv(index=False).encode()
        else:
            out = io.BytesIO()
            frame.to_parquet(out, index=False)
            raw = out.getvalue()
        self.objects[uri] = raw
        return {"uri": uri, "raw_sha256": sha(raw)}


def kickoff(week, index=0):
    return (
        pd.Timestamp("2026-08-29T00:00:00Z") + pd.Timedelta(days=7 * week, hours=index)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def add_week(storage, week, *, games, bundle_hash, live_as_of=None):
    """One checksummed run for ``week``; a ``live_as_of`` makes it a display/live run."""
    suffix = "" if week == 0 else str(week)
    ids = [week * 100 + index + 1 for index in range(games)]
    state_cutoff = {
        game_id: live_as_of or kickoff(week, index) for index, game_id in enumerate(ids)
    }
    roles = storage.frame(
        f"roles{suffix}.parquet",
        [
            {
                "game_id": game_id,
                "team": f"{team}{game_id}",
                "unit_role": role,
                "cutoff_utc": state_cutoff[game_id],
                "source_game_ids": "[]",
            }
            for game_id in ids
            for team in ["A", "B"]
            for role in ["offense", "defense"]
        ],
    )
    rating_hash = storage.put(
        f"rating{suffix}.json",
        signed_payload({"output_refs": {"pregame_roles": roles}}),
    )
    forecasts = storage.frame(
        f"forecast{suffix}.csv",
        [
            {
                "game_id": game_id,
                "target": target,
                "state_ref": f"rating:{rating_hash}#pregame:{game_id}",
            }
            for game_id in ids
            for target in ["margin", "total"]
        ],
    )
    forecast_manifest = {
        "parents": {
            "bridge_manifest_raw_sha256": sha(storage.objects["bridge.json"]),
            "source_lock_sha256": "lock",
        },
        "prediction_ref": forecasts,
    }
    if live_as_of:
        forecast_manifest["live"] = {"as_of": live_as_of, "display_only": True}
    forecast_hash = storage.put(
        f"forecast{suffix}.json", signed_payload(forecast_manifest)
    )
    captured = kickoff(week - 1) if week else "2026-08-20T00:00:00Z"
    quotes = storage.frame(
        f"quotes{suffix}.parquet",
        [
            {
                "game_id": game_id,
                "quote_id": f"q{game_id}",
                "captured_at": captured,
                "__capture_provider": "cfbd",
            }
            for game_id in ids
        ],
    )
    snapshots = storage.frame(
        f"snapshots{suffix}.parquet",
        [
            {
                "game_id": game_id,
                "source_quote_ids": f'["q{game_id}"]',
                "market_captured_at": captured,
            }
            for game_id in ids
        ],
    )
    predictions = storage.frame(
        f"predictions{suffix}.csv",
        [
            {
                "game_id": game_id,
                "spread_market_quote_id": f"q{game_id}",
                "total_market_quote_id": None,
            }
            for game_id in ids
        ],
    )
    run_id = "run" if week == 0 else f"run{week}"
    uri = (
        f"artifacts/preview/predictions/year=2026/week={week}/run_id={run_id}/"
        "manifest.json"
    )
    storage.put(
        uri,
        {
            "season": 2026,
            "week": week,
            "run_id": run_id,
            "expected_games": games,
            "artifact_uri": f"predictions{suffix}.csv",
            "artifact_sha256": predictions["raw_sha256"],
            "v5_live_forecast_manifest_uri": f"forecast{suffix}.json",
            "v5_live_forecast_manifest_sha256": forecast_hash,
            "v5_rating_replay_manifest_sha256": rating_hash,
            "input_dataset_refs": [
                dict(quotes, dataset="market_quotes"),
                dict(snapshots, dataset="market_snapshots"),
            ],
            "data_as_of": live_as_of
            or (pd.Timestamp(captured) + pd.Timedelta(days=3)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "inference_bundle_sha256": bundle_hash,
            "evidence_class": "live" if live_as_of else "replay",
            **({"display_only": True} if live_as_of else {}),
        },
    )
    schedule = [
        [game_id, week, f"A{game_id}", f"B{game_id}", kickoff(week, index)]
        for index, game_id in enumerate(ids)
    ]
    return uri, run_id, schedule


def evidence_weeks(games, live=None):
    """Evidence for every week in ``games`` (week -> slate size); ``live`` maps week -> as_of."""
    storage = Storage()
    bundle_hash = storage.put(
        "bundle.json", {"development_seasons": [2019, 2021, 2025]}
    )
    storage.put(
        "bridge.json",
        signed_payload(
            {
                "output_refs": {
                    "inference_bundle": {
                        "uri": "bundle.json",
                        "raw_sha256": bundle_hash,
                    }
                }
            }
        ),
    )
    uris, runs, rows = {}, {}, []
    for week, count in games.items():
        uris[week], runs[week], schedule = add_week(
            storage,
            week,
            games=count,
            bundle_hash=bundle_hash,
            live_as_of=(live or {}).get(week),
        )
        rows.extend(schedule)
    lock = {
        "_audit_raw_sha256": "lock",
        "games": {
            "columns": ["game_id", "week", "home_team", "away_team", "start_date"],
            "rows": rows,
        },
        "market_sources": {},
    }
    return Evidence(storage), uris, runs, lock


def evidence():
    source, uris, _, lock = evidence_weeks({0: 1})
    return source, uris[0], lock


def audit_weeks(source, runs, lock):
    return audit(
        source,
        environment="preview",
        through_week=max(runs),
        locks={week: lock for week in runs},
        rating_uris={week: f"rating{week or ''}.json" for week in runs},
        bridge_uri="bridge.json",
        runs=runs,
        stats_rows=[],
    )


def run(source, lock):
    return audit(
        source,
        environment="preview",
        through_week=0,
        locks={0: lock},
        rating_uris={0: "rating.json"},
        bridge_uri="bridge.json",
        runs={0: "run"},
        stats_rows=[],
    )


def test_loader_records_distinct_replay_forecast_and_market_cutoffs():
    source, _, lock = evidence()
    receipt = run(source, lock)
    assert receipt["state"] == "passed"
    verify_signed_payload(receipt)
    assert (
        receipt["inputs"]["cutoffs"][0]["forecast_as_of"] == "2026-08-29T00:00:00+00:00"
    )
    assert receipt["inputs"]["cutoffs"][0]["market_as_of"] == "2026-08-23T00:00:00Z"
    assert receipt["inputs"]["objects"]["roles.parquet"]


def test_loader_rejects_tampered_frame():
    source, _, lock = evidence()
    source.storage.objects["roles.parquet"] += b"bad"
    with pytest.raises(ValueError, match="checksum"):
        run(source, lock)


def test_loader_rejects_foreign_source_lock():
    source, _, lock = evidence()
    lock["_audit_raw_sha256"] = "foreign"
    with pytest.raises(ValueError, match="source lock"):
        run(source, lock)


def test_loader_rejects_incomplete_schedule():
    source, uri, lock = evidence()
    lock["games"]["rows"] = []
    with pytest.raises(ValueError, match="schedule coverage"):
        load_week(
            source,
            manifest_uri=uri,
            lock=lock,
            rating_uri="rating.json",
            bridge={"uri": "bridge.json"},
        )


def test_team_stat_violation_marks_entire_week_failed_and_resigns():
    from cks_picks_cfb.audit.point_in_time import violation

    source, _, lock = evidence()
    receipt = audit(
        source,
        environment="preview",
        through_week=0,
        locks={0: lock},
        rating_uris={0: "rating.json"},
        bridge_uri="bridge.json",
        runs={0: "run"},
        stats_rows=[],
        stats_violations=[violation("f_team_stats", None, 0, "bad membership")],
    )
    assert receipt["state"] == "failed"
    assert receipt["games"][0]["passed"] is False
    verify_signed_payload(receipt)


def test_cfbd_comparison_preserves_provider_target_and_pre_kickoff_scope():
    schedule = pd.DataFrame([{"game_id": 1, "start_date": "2026-08-29T00:00:00Z"}])
    quotes = pd.DataFrame(
        [
            {
                "game_id": 1,
                "quote_id": "q",
                "provider": "Book",
                "__capture_provider": "cfbd",
                "captured_at": "2026-08-28T00:00:00Z",
                "spread": -3,
                "total": 50,
            },
            {
                "game_id": 1,
                "quote_id": "late",
                "provider": "Book",
                "__capture_provider": "cfbd",
                "captured_at": "2026-08-30T00:00:00Z",
                "spread": -3,
                "total": 50,
            },
        ]
    )
    current = [
        {"id": 1, "lines": [{"provider": "Book", "spread": -3, "overUnder": 51}]}
    ]
    rows = compare_lines(quotes, current, schedule)
    assert [row["matches"] for row in rows] == [True, False]
    assert {row["quote_id"] for row in rows} == {"q"}
    assert not any(row["matches"] for row in compare_lines(quotes, [], schedule))


def test_future_model_development_seasons_fail():
    from cks_picks_cfb.audit.point_in_time import check_model_parameters

    assert check_model_parameters(
        {"development_seasons": [2027]}, declared_sha256="same", file_sha256="same"
    )


def test_replay_market_capture_may_precede_per_game_forecast_cutoff():
    from cks_picks_cfb.audit.point_in_time import check_cutoff_coherence

    games = pd.DataFrame(
        [{"game_id": 1, "week": 0, "kickoff_utc": "2026-08-29T00:00:00Z"}]
    )
    runs = pd.DataFrame(
        [
            {
                "week": 0,
                "run_id": "run",
                "forecast_as_of": "2026-08-29T00:00:00Z",
                "market_as_of": "2026-08-20T00:00:00Z",
                "per_game_cutoffs": True,
            }
        ]
    )
    assert check_cutoff_coherence(games, runs) == []
    runs.loc[0, "market_as_of"] = None
    assert check_cutoff_coherence(games, runs)


WEEK6_SLATE = {**{week: 1 for week in range(6)}, 6: 58}


def test_week6_replay_is_audited_per_game_on_kickoff_and_passes():
    source, _, runs, lock = evidence_weeks(WEEK6_SLATE)
    receipt = audit_weeks(source, runs, lock)
    assert receipt["state"] == "passed", receipt["violations"]
    week6 = [c for c in receipt["inputs"]["cutoffs"] if c["week"] == 6][0]
    assert week6["per_game_cutoffs"] is True
    assert week6["forecast_as_of"] == "2026-10-10T00:00:00+00:00"


@pytest.mark.parametrize(
    "as_of, passed",
    [("2026-10-09T23:00:00Z", True), ("2026-10-10T00:00:00Z", False)],
)
def test_week6_live_run_must_precede_the_slates_first_kickoff(as_of, passed):
    source, _, runs, lock = evidence_weeks(WEEK6_SLATE, live={6: as_of})
    receipt = audit_weeks(source, runs, lock)
    assert (receipt["state"] == "passed") is passed, receipt["violations"]
    rules = {(v["rule"], v["week"]) for v in receipt["violations"]}
    assert (("c_forecast_time", 6) in rules) is not passed


def _args(tmp_path, *extra):
    for name in ["replay", "live"]:
        (tmp_path / f"{name}.json").write_text(json.dumps({"name": name}))
    return parse_args(
        [
            "--environment",
            "preview",
            "--season",
            "2026",
            "--source-lock",
            str(tmp_path / "replay.json"),
            "--rating-uri",
            "replay-rating",
            *extra,
        ]
    )


def test_live_week_alone_uses_the_live_lock_and_rating(tmp_path):
    args = _args(
        tmp_path,
        "--through-week",
        "7",
        "--run",
        "6=r6",
        "--run",
        "7=r7",
        "--live-week",
        "7",
        "--live-source-lock",
        str(tmp_path / "live.json"),
        "--live-rating-uri",
        "live-rating",
    )
    locks, ratings = week_inputs(args)
    assert sorted(locks) == list(range(8))
    assert {w for w, lock in locks.items() if lock["name"] == "live"} == {7}
    assert {w for w, uri in ratings.items() if uri == "live-rating"} == {7}
    assert args.runs[6] == "r6" and args.runs[0].endswith("-c2")


def test_without_live_week_every_week_uses_the_replay_inputs(tmp_path):
    args = _args(tmp_path, "--through-week", "6", "--run", "6=r6")
    locks, ratings = week_inputs(args)
    assert {lock["name"] for lock in locks.values()} == {"replay"}
    assert set(ratings.values()) == {"replay-rating"}


@pytest.mark.parametrize(
    "extra",
    [
        ["--through-week", "8"],
        ["--through-week", "6"],  # Week 6 has no default run.
        ["--through-week", "5", "--run", "6=r6"],
        ["--through-week", "6", "--run", "6=r6", "--live-week", "6"],
    ],
)
def test_invalid_week_routing_is_refused(tmp_path, extra):
    with pytest.raises(SystemExit):
        _args(tmp_path, *extra)
