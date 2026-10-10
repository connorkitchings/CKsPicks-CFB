"""Exercise the artifact loader with checksummed, signed in-memory evidence."""

import io
import json

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from scripts.pipeline.audit_corrected_replay_chain import sha
from scripts.pipeline.audit_point_in_time_leakage import Evidence, audit, load_week
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


def evidence():
    storage = Storage()
    cutoff = "2026-08-29T00:00:00Z"
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
    roles = storage.frame(
        "roles.parquet",
        [
            {
                "game_id": 1,
                "team": team,
                "unit_role": role,
                "cutoff_utc": cutoff,
                "source_game_ids": "[]",
            }
            for team in ["A", "B"]
            for role in ["offense", "defense"]
        ],
    )
    rating_hash = storage.put(
        "rating.json", signed_payload({"output_refs": {"pregame_roles": roles}})
    )
    forecasts = storage.frame(
        "forecast.csv",
        [
            {
                "game_id": 1,
                "target": target,
                "state_ref": f"rating:{rating_hash}#pregame:1",
            }
            for target in ["margin", "total"]
        ],
    )
    forecast_hash = storage.put(
        "forecast.json",
        signed_payload(
            {
                "parents": {
                    "bridge_manifest_raw_sha256": sha(storage.objects["bridge.json"]),
                    "source_lock_sha256": "lock",
                },
                "prediction_ref": forecasts,
            }
        ),
    )
    quotes = storage.frame(
        "quotes.parquet",
        [
            {
                "game_id": 1,
                "quote_id": "q",
                "captured_at": "2026-08-20T00:00:00Z",
                "__capture_provider": "cfbd",
            }
        ],
    )
    snapshots = storage.frame(
        "snapshots.parquet",
        [
            {
                "game_id": 1,
                "source_quote_ids": '["q"]',
                "market_captured_at": "2026-08-20T00:00:00Z",
            }
        ],
    )
    predictions = storage.frame(
        "predictions.csv",
        [{"game_id": 1, "spread_market_quote_id": "q", "total_market_quote_id": None}],
    )
    uri = "artifacts/preview/predictions/year=2026/week=0/run_id=run/manifest.json"
    storage.put(
        uri,
        {
            "season": 2026,
            "week": 0,
            "run_id": "run",
            "expected_games": 1,
            "artifact_uri": "predictions.csv",
            "artifact_sha256": predictions["raw_sha256"],
            "v5_live_forecast_manifest_uri": "forecast.json",
            "v5_live_forecast_manifest_sha256": forecast_hash,
            "v5_rating_replay_manifest_sha256": rating_hash,
            "input_dataset_refs": [
                dict(quotes, dataset="market_quotes"),
                dict(snapshots, dataset="market_snapshots"),
            ],
            "data_as_of": "2026-08-23T00:00:00Z",
            "inference_bundle_sha256": bundle_hash,
            "evidence_class": "replay",
        },
    )
    lock = {
        "_audit_raw_sha256": "lock",
        "games": {
            "columns": ["game_id", "week", "home_team", "away_team", "start_date"],
            "rows": [[1, 0, "A", "B", cutoff]],
        },
        "market_sources": {},
    }
    return Evidence(storage), uri, lock


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
