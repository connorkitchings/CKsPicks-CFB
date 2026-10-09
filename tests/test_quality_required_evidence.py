"""Independent expected-request inventory and fail-closed release checks."""

import copy
import hashlib
import io
import json

import pandas as pd
import pytest

from cks_picks_cfb.data.week_policy import WeekAssignment, WeekPolicySpec
from cks_picks_cfb.quality import checks as q
from cks_picks_cfb.quality.__main__ import main as cli_main
from cks_picks_cfb.quality.loaders import (
    build_ingest_context,
    capture_requests,
    request_key,
)
from cks_picks_cfb.quality.request_inventory import (
    build_expected_request_inventory,
    expected_request_keys,
    read_pinned_schedule,
    verify_expected_request_inventory,
)
from tests.test_quality_loaders import RunsCursor, _request


def inventory():
    return {
        "schema_version": "cfbd_expected_requests_v1",
        "season": 2026,
        "schedule_ref": {"version_id": "pinned", "content_sha": "a" * 64},
        "requests": [
            {
                "provider": "cfbd",
                "entity": "plays",
                "parameters": {"year": 2026, "week": w},
            }
            for w in [0, 1]
        ],
    }


def test_inventory_is_independent_of_attempts_and_binds_week_mapping():
    kickoff = pd.Timestamp("2026-08-29T18:00:00Z")
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 10,
                "provider_week": 1,
                "kickoff_utc": kickoff,
                "completed": True,
            },
            {
                "season": 2026,
                "game_id": 11,
                "provider_week": 1,
                "kickoff_utc": kickoff,
                "completed": False,
            },
        ]
    )
    policy = WeekPolicySpec(
        "test-v1",
        2026,
        (
            WeekAssignment(10, kickoff, 0),
            WeekAssignment(11, kickoff, 0),
        ),
    )
    result = build_expected_request_inventory(
        schedule,
        schedule_ref={"version_id": "g1", "content_sha": "a" * 64},
        policy=policy,
        season=2026,
        canonical_week=0,
    )
    assert len(result["requests"]) == 2
    assert all(r["parameters"]["week"] == 1 for r in result["requests"])
    assert all(r["parameters"]["canonical_week"] == 0 for r in result["requests"])
    assert all(
        r["parameters"]["expected_game_ids"] == [10, 11] for r in result["requests"]
    )
    assert all(r["required_completed_game_ids"] == [10] for r in result["requests"])
    assert len(expected_request_keys(result, 2026)) == 2
    with pytest.raises(ValueError, match="duplicate game"):
        build_expected_request_inventory(
            pd.concat([schedule, schedule.iloc[:1]]),
            schedule_ref=result["schedule_ref"],
            policy=policy,
            season=2026,
            canonical_week=0,
        )


def test_inventory_readback_recomputes_request_population(monkeypatch):
    import cks_picks_cfb.data.week_policy as week_policy
    import cks_picks_cfb.quality.loaders as loaders

    kickoff = pd.Timestamp("2026-08-29T18:00:00Z")
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 10,
                "provider_week": 1,
                "kickoff_utc": kickoff,
                "completed": True,
            }
        ]
    )
    policy = WeekPolicySpec("test-v1", 2026, (WeekAssignment(10, kickoff, 0),))
    ref = {
        "dataset": "games",
        "version_id": "g1",
        "schema_version": "games_v1",
        "content_sha": "a" * 64,
        "uri": "lake/games.parquet",
    }
    inventory = build_expected_request_inventory(
        schedule,
        schedule_ref=ref,
        policy=policy,
        season=2026,
        canonical_week=0,
    )
    inventory["week_policy_path"] = "conf/policy/test-v1.yaml"
    monkeypatch.setattr(week_policy, "load_week_policy_spec", lambda path: policy)
    monkeypatch.setattr(
        loaders, "read_quality_dataset", lambda storage, pinned: schedule
    )
    verify_expected_request_inventory(object(), inventory)
    inventory["requests"][0]["parameters"]["expected_game_ids"] = [10, 11]
    with pytest.raises(ValueError, match="differs from pinned requests"):
        verify_expected_request_inventory(object(), inventory)


def test_raw_schedule_pin_includes_fbs_fcs_and_rejects_changed_bytes():
    schedule = pd.DataFrame(
        [
            {
                "id": 10,
                "season": 2026,
                "season_type": "regular",
                "week": 5,
                "start_date": pd.Timestamp("2026-10-03T18:00:00Z"),
                "completed": True,
                "home_classification": "fbs",
                "away_classification": "fbs",
            },
            {
                "id": 11,
                "season": 2026,
                "season_type": "regular",
                "week": 5,
                "start_date": pd.Timestamp("2026-10-03T19:00:00Z"),
                "completed": True,
                "home_classification": "fbs",
                "away_classification": "fcs",
            },
            {
                "id": 12,
                "season": 2026,
                "season_type": "regular",
                "week": 5,
                "start_date": pd.Timestamp("2026-10-03T20:00:00Z"),
                "completed": True,
                "home_classification": "fcs",
                "away_classification": "fcs",
            },
        ]
    )
    buffer = io.BytesIO()
    schedule.to_parquet(buffer, index=False)
    raw = buffer.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    ref = {
        "dataset": "games",
        "schema_version": "raw_games_snapshot_v1",
        "version_id": digest[:24],
        "content_sha": digest,
        "uri": "raw/games/year=2026/part-0.parquet",
    }

    class Storage:
        def __init__(self, payload):
            self.payload = payload

        def read_bytes(self, uri):
            assert uri == ref["uri"]
            return self.payload

    normalized = read_pinned_schedule(Storage(raw), ref, season=2026)
    result = build_expected_request_inventory(
        normalized,
        schedule_ref=ref,
        policy=WeekPolicySpec("test", 2026, ()),
        season=2026,
        canonical_week=5,
    )
    assert all(
        item["parameters"]["expected_game_ids"] == [10, 11]
        for item in result["requests"]
    )
    with pytest.raises(ValueError, match="bytes differ"):
        read_pinned_schedule(Storage(raw + b"changed"), ref, season=2026)


def test_never_attempted_request_blocks_against_independent_inventory():
    cur = RunsCursor([("succeeded", _request("plays", year=2026, week=0))])
    context = build_ingest_context(
        cur, lambda _: None, year=2026, request_inventory=inventory()
    )
    run = q.run_stage(
        "ingest",
        context,
        prefix="ingest.capture_completeness",
        required_checks=["ingest.capture_completeness"],
    )
    assert run.blocked
    assert run.results[0].observed["missing"] == 1
    assert (
        request_key("plays", {"year": 2026, "week": 1})
        not in context["attempted_requests"]
    )


def test_attempt_ledger_alone_cannot_establish_completeness(tmp_path):
    cur = RunsCursor([("succeeded", _request("plays", year=2026, week=0))])
    context = build_ingest_context(cur, lambda _: None, year=2026)
    assert context["inputs"]["request_basis"] == "attempt_ledger"
    # The library can only warn on attempts; a required gate needs an inventory.
    with pytest.raises(SystemExit):
        cli_main(
            [
                "--stage",
                "ingest",
                "--require-check",
                "ingest.capture_completeness",
                "--output",
                str(tmp_path),
            ]
        )


def test_environment_quality_run_rechecks_inventory_bytes_before_catalog(
    monkeypatch, tmp_path
):
    import cks_picks_cfb.quality.__main__ as quality_cli
    import cks_picks_cfb.quality.request_inventory as inventory_module

    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(inventory()))
    monkeypatch.setattr(
        quality_cli,
        "load_ingest_context",
        lambda *_args, **_kwargs: pytest.fail(
            "catalog read before inventory verification"
        ),
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.storage.get_storage", lambda **_kwargs: object()
    )
    monkeypatch.setattr(
        inventory_module,
        "verify_expected_request_inventory",
        lambda *_args: (_ for _ in ()).throw(ValueError("tampered schedule")),
    )
    with pytest.raises(ValueError, match="tampered schedule"):
        cli_main(
            [
                "--stage",
                "ingest",
                "--year",
                "2026",
                "--environment",
                "preview",
                "--request-inventory",
                str(path),
                "--output",
                str(tmp_path),
            ]
        )


def test_complete_inventory_passes_and_mixed_season_attempts_do_not_leak():
    req = inventory()["requests"]
    mixed = {
        "requests": [*req, {"entity": "plays", "parameters": {"year": 2025, "week": 2}}]
    }
    attempted, completed = capture_requests(RunsCursor([("succeeded", mixed)]), 2026)
    assert attempted == completed == expected_request_keys(inventory(), 2026)
    assert not q.run_stage(
        "ingest",
        {"expected_requests": attempted, "completed_requests": completed},
        prefix="ingest.capture_completeness",
        required_checks=["ingest.capture_completeness"],
    ).blocked


@pytest.mark.parametrize("fault", ["empty", "duplicate", "year", "unbound"])
def test_invalid_inventory_is_rejected(fault):
    manifest = copy.deepcopy(inventory())
    if fault == "empty":
        manifest["requests"] = []
    if fault == "duplicate":
        manifest["requests"].append(manifest["requests"][0])
    if fault == "year":
        manifest["season"] = 2025
    if fault == "unbound":
        manifest["schedule_ref"] = {}
    with pytest.raises(ValueError):
        expected_request_keys(manifest, 2026)


def test_required_check_cannot_disappear_or_move_stages():
    with pytest.raises(ValueError, match="out-of-stage"):
        q.run_stage("silver", {}, required_checks=["ingest.capture_completeness"])
    empty = q.CheckSpec("gold.empty", "gold", q.WARN, "no outcomes", lambda _: [])
    assert q.run_stage(
        "gold", {}, registry={empty.check_id: empty}, required_checks=[empty.check_id]
    ).blocked
