"""Independent expected-request inventory and fail-closed release checks."""

import copy

import pytest

from cks_picks_cfb.quality import checks as q
from cks_picks_cfb.quality.__main__ import main as cli_main
from cks_picks_cfb.quality.loaders import (
    build_ingest_context,
    capture_requests,
    request_key,
)
from cks_picks_cfb.quality.request_inventory import expected_request_keys
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
