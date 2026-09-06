from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2 import (
    active_pregame_request_plan,
    build_eligibility_manifest,
    coverage_gate,
    deduplicate_preseason_rows,
    execute_with_bounded_retries,
    historical_request_plan,
    merge_schedule_observations,
    validate_postseason_schedule_capture,
)


def test_historical_plan_counts_requests_and_requires_week_for_plays():
    schedule = pd.DataFrame(
        [
            {"season": 2019, "week": 1, "season_type": "regular"},
            {"season": 2019, "week": 2, "season_type": "regular"},
            {"season": 2019, "week": 1, "season_type": "postseason"},
        ]
    )
    requests = historical_request_plan(schedule)
    plays = [request for request in requests if request.entity == "plays"]
    # Every development season gets regular/postseason schedule requests and a
    # team request. Known weeks additionally get one plays and one stats call.
    assert len(requests) == 36
    assert all(
        {"year", "week", "season_type"} <= set(request.parameters) for request in plays
    )
    assert (
        len(
            historical_request_plan(
                schedule, existing_request_shas=[requests[0].request_sha]
            )
        )
        == 35
    )


def test_capture_plans_reject_2020_and_active_plan_is_seven_calls():
    with pytest.raises(ValueError, match="2020"):
        historical_request_plan(
            pd.DataFrame([{"season": 2020, "week": 1, "season_type": "regular"}])
        )
    assert len(active_pregame_request_plan(2026)) == 7


def test_supplemental_postseason_schedule_discovers_weekly_requests():
    regular = pd.DataFrame(
        [
            {
                "season": 2019,
                "week": 1,
                "season_type": "regular",
                "game_id": 1,
            }
        ]
    )
    postseason = pd.DataFrame(
        [
            {"year": 2019, "week": 1, "seasonType": "postseason", "id": 2},
            {"year": 2019, "week": 1, "seasonType": "postseason", "id": 2},
        ]
    )
    merged = merge_schedule_observations(regular, [postseason])
    requests = historical_request_plan(merged)
    postseason_weekly = [
        request
        for request in requests
        if request.parameters.get("year") == 2019
        and request.parameters.get("season_type") == "postseason"
        and request.entity in {"plays", "game_stats"}
    ]
    assert len(merged) == 2
    assert len(postseason_weekly) == 2


def test_supplemental_schedule_rejects_2020_and_identity_conflicts():
    base = pd.DataFrame(
        [
            {
                "season": 2019,
                "week": 1,
                "season_type": "regular",
                "game_id": 1,
            }
        ]
    )
    with pytest.raises(ValueError, match="2020"):
        merge_schedule_observations(
            base,
            [
                pd.DataFrame(
                    [
                        {
                            "season": 2020,
                            "week": 1,
                            "season_type": "postseason",
                            "game_id": 2,
                        }
                    ]
                )
            ],
        )
    with pytest.raises(ValueError, match="conflicting schedule observations"):
        merge_schedule_observations(
            base,
            [
                pd.DataFrame(
                    [
                        {
                            "season": 2019,
                            "week": 2,
                            "season_type": "regular",
                            "game_id": 1,
                        }
                    ]
                )
            ],
        )


def test_supplemental_capture_requires_registered_cfbd_postseason_provenance():
    valid = SimpleNamespace(
        capture_id="capture",
        state="registered",
        provider="cfbd",
        entity="data_first_games",
        request={
            "endpoint": "GamesApi.get_games",
            "parameters": {"year": 2019, "season_type": "postseason"},
        },
    )
    validate_postseason_schedule_capture(valid)

    invalid = SimpleNamespace(**(valid.__dict__ | {"entity": "games"}))
    with pytest.raises(ValueError, match="CFBD data_first_games"):
        validate_postseason_schedule_capture(invalid)


def test_bounded_retries_report_attempts_and_exhaustion_without_waiting():
    calls = 0
    waits = []

    def flaky():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError(f"temporary-{calls}")
        return ["ok"]

    value, attempts, errors = execute_with_bounded_retries(
        flaky, max_attempts=3, sleeper=waits.append
    )
    assert value == ["ok"]
    assert attempts == 3
    assert [row["attempt"] for row in errors] == [1, 2]
    assert waits == [1, 2]

    with pytest.raises(RuntimeError, match="exhausted 2 attempts"):
        execute_with_bounded_retries(
            lambda: (_ for _ in ()).throw(TimeoutError("still unavailable")),
            max_attempts=2,
            sleeper=lambda _: None,
        )


def test_preseason_repair_preserves_as_of_and_quarantines_conflicts():
    frame = pd.DataFrame(
        [
            {"season": 2025, "team": "A", "as_of": "2025-01-01", "value": 1},
            {"season": 2025, "team": "A", "as_of": "2025-01-01", "value": 1},
            {"season": 2025, "team": "A", "as_of": "2025-02-01", "value": 2},
            {"season": 2025, "team": "B", "as_of": "2025-01-01", "value": 1},
            {"season": 2025, "team": "B", "as_of": "2025-01-01", "value": 2},
        ]
    )
    clean, quarantine = deduplicate_preseason_rows(frame)
    assert clean[["team", "as_of"]].values.tolist() == [
        ["A", "2025-01-01"],
        ["A", "2025-02-01"],
    ]
    assert len(quarantine) == 2


def test_coverage_gates_each_slice_and_manifest_excludes_blocked_inputs():
    coverage = pd.DataFrame(
        [
            {
                "season": 2025,
                "season_type": "regular",
                "population": "fbs_fbs",
                "stage": "plays",
                "coverage_rate": 0.96,
            },
            {
                "season": 2025,
                "season_type": "postseason",
                "population": "fbs_fcs",
                "stage": "plays",
                "coverage_rate": 0.91,
            },
        ]
    )
    gate = coverage_gate(coverage)
    assert gate["passed"]
    dataset = {
        "dataset": "plays",
        "version_id": "v1",
        "schema_version": "plays_v2",
        "content_sha": "a" * 64,
        "uri": "lake/silver/plays.parquet",
    }
    manifest = build_eligibility_manifest(
        audit_summary={"run_id": "audit"},
        dataset_rows=[dataset],
        issues=[{"severity": "high", "affected_descendants": ["v1"]}],
        coverage_result=gate,
    )
    assert manifest["state"] == "blocked"
    assert not manifest["inputs"][0]["eligible"]
