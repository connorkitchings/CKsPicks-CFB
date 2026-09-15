"""Independence and observability safeguards for V5 possession verification."""

from __future__ import annotations

import ast
import io
import json
import threading
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pandas as pd

from cks_picks_cfb.data.research_progress import ResearchProgress
from cks_picks_cfb.ratings import possession_measurements as producer
from cks_picks_cfb.ratings.possession_verification import (
    reconstruct_measurements,
    reconstruct_replay_partitions,
)

ROOT = Path(__file__).resolve().parents[2]


def _population() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2025,
                "week": week,
                "game_id": week,
                "kickoff_utc": f"2025-09-{week:02d}T18:00:00Z",
                "home_team": "Southern Mississippi",
                "away_team": "Connecticut",
                "schedule_completed": True,
                "outcome_valid": True,
                "forecast_eligible": True,
                "measurement_usable": True,
                "population_disposition": "eligible_with_measurements",
                "measurement_disposition": "eligible_with_measurements",
                "missing_reason": None,
                "timing_class": "historically_reconstructed",
            }
            for week in (1, 2)
        ]
    )


def _plays() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for week in (1, 2):
        rows.extend(
            [
                {
                    "season": 2025,
                    "week": week,
                    "game_id": week,
                    "drive_number": 1,
                    "play_number": 1,
                    "offense": "Southern Miss",
                    "defense": "UConn",
                    "st": 0,
                    "penalty": 0,
                    "twopoint": 0,
                    "play_type": "Rush",
                    "garbage": 0,
                    "ppa": 0.2,
                    "quarter": 1,
                    "offense_score": 0,
                    "defense_score": 0,
                },
                {
                    "season": 2025,
                    "week": week,
                    "game_id": week,
                    "drive_number": 1,
                    "play_number": 2,
                    "offense": "Southern Miss",
                    "defense": "UConn",
                    "st": 0,
                    "penalty": 0,
                    "twopoint": 0,
                    "play_type": "Rush Touchdown",
                    "garbage": 0,
                    "ppa": 0.5,
                    "quarter": 1,
                    "offense_score": 7,
                    "defense_score": 0,
                },
                {
                    "season": 2025,
                    "week": week,
                    "game_id": week,
                    "drive_number": 2,
                    "play_number": 1,
                    "offense": "UConn",
                    "defense": "Southern Miss",
                    "st": 0,
                    "penalty": 0,
                    "twopoint": 0,
                    "play_type": "Field Goal",
                    "garbage": 0,
                    "ppa": 0.1,
                    "quarter": 1,
                    "offense_score": 3,
                    "defense_score": 7,
                },
            ]
        )
    return pd.DataFrame(rows)


def _outcomes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2025,
                "game_id": game_id,
                "home_points": 7,
                "away_points": 3,
            }
            for game_id in (1, 2)
        ]
    )


def test_verifier_import_boundary_excludes_producer_logic() -> None:
    paths = [
        ROOT / "scripts/research/verify_data_first_possession_measurements.py",
        ROOT / "src/cks_picks_cfb/ratings/possession_verification.py",
    ]
    banned = {
        "cks_picks_cfb.ratings.possession_measurements",
        "scripts.research.run_data_first_possession_measurements",
    }
    for path in paths:
        tree = ast.parse(path.read_text())
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imports.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not imports & banned


def test_independent_reconstruction_matches_contract_fixture() -> None:
    actual = reconstruct_measurements(
        byplay=_plays(), outcomes=_outcomes(), population=_population()
    )
    expected = producer.build_measurements(
        byplay=_plays(), outcomes=_outcomes(), population=_population()
    )
    for left, right in (
        (actual.possessions, expected.possessions),
        (actual.scoring_events, expected.scoring_events),
        (actual.observations, expected.observations),
        (actual.coverage, expected.coverage),
    ):
        pd.testing.assert_frame_equal(left, right, check_dtype=False)
    assert actual.final_reconciliation == expected.final_reconciliation


def test_producer_only_perturbation_does_not_change_independent_result(
    monkeypatch,
) -> None:
    baseline = reconstruct_measurements(
        byplay=_plays(), outcomes=_outcomes(), population=_population()
    )
    monkeypatch.setattr(producer, "_eligible_play", lambda _row: False)
    changed = producer.build_measurements(
        byplay=_plays(), outcomes=_outcomes(), population=_population()
    )
    repeated = reconstruct_measurements(
        byplay=_plays(), outcomes=_outcomes(), population=_population()
    )
    assert not changed.possessions["possession_eligible"].any()
    pd.testing.assert_frame_equal(baseline.possessions, repeated.possessions)


def test_independent_replay_is_partitioned_and_strictly_prior() -> None:
    rebuilt = reconstruct_measurements(
        byplay=_plays(), outcomes=_outcomes(), population=_population()
    )
    emitted: list[tuple[str, dict[str, int], pd.DataFrame]] = []
    reconstruct_replay_partitions(
        population=_population(),
        observations=rebuilt.observations,
        emit=lambda name, partition, frame: emitted.append((name, partition, frame)),
    )
    produced: list[tuple[str, dict[str, int], pd.DataFrame]] = []
    producer.replay_partitions(
        population=_population(),
        observations=rebuilt.observations,
        emit=lambda name, partition, frame: produced.append((name, partition, frame)),
    )
    assert [(name, partition) for name, partition, _ in emitted] == [
        (name, partition) for name, partition, _ in produced
    ]
    for (_, _, actual), (_, _, expected) in zip(emitted, produced, strict=True):
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False)
    snapshots = pd.DataFrame.from_records(
        [
            record
            for name, _, frame in emitted
            if name == "snapshots"
            for record in frame.to_dict("records")
        ]
    )
    assert snapshots.loc[snapshots["week"].eq(1), "source_game_count"].eq(0).all()
    assert snapshots.loc[snapshots["week"].eq(2), "source_game_count"].gt(0).any()
    assert all(
        name != "adjusted_history" or partition["week"] > 1
        for name, partition, _ in emitted
    )


def test_progress_is_jsonl_on_stderr_and_rate_limited(monkeypatch) -> None:
    ticks = iter((100.0, 100.0, 101.0, 131.0, 131.0))
    monkeypatch.setattr(
        "cks_picks_cfb.data.research_progress.time.monotonic", lambda: next(ticks)
    )
    stream = io.StringIO()
    with redirect_stderr(stream):
        progress = ResearchProgress(run_id="safe-run", interval_seconds=30.0)
        progress.emit("first")
        progress.emit("suppressed", credential="must-not-appear")
        progress.emit("heartbeat", completed=2, total=3)
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert [event["event"] for event in events] == ["first", "heartbeat"]
    assert all(event["run_id"] == "safe-run" for event in events)
    assert all("phase" in event for event in events)
    assert "must-not-appear" not in stream.getvalue()


def test_progress_heartbeat_is_flushed_and_stdout_stays_clean() -> None:
    class FlushProbe(io.StringIO):
        flushes = 0

        def flush(self) -> None:
            self.flushes += 1
            super().flush()

    stderr = FlushProbe()
    stdout = io.StringIO()
    with redirect_stderr(stderr), redirect_stdout(stdout):
        progress = ResearchProgress(run_id="heartbeat-run", interval_seconds=0.005)
        progress.emit(
            "partition_read",
            force=True,
            dataset="adjusted_history",
            completed=1,
            total=2,
            rows=10,
            api_token="must-not-appear",
        )
        progress.start()
        threading.Event().wait(0.03)
        progress.close()
    events = [json.loads(line) for line in stderr.getvalue().splitlines()]
    assert any(event["event"] == "heartbeat" for event in events)
    assert all(event["phase"] == "partition_read" for event in events)
    assert stderr.flushes >= len(events)
    assert stdout.getvalue() == ""
    assert "must-not-appear" not in stderr.getvalue()
