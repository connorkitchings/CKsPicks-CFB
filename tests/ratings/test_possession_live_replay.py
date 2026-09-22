"""Contract tests for the isolated 2026 single-candidate rating replay."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.data_first_possession_v1 import (
    POSSESSION_DATASETS,
    POSSESSION_MANIFEST_SCHEMA,
)
from cks_picks_cfb.ratings import possession_live_replay_verification as verifier
from cks_picks_cfb.ratings.possession_live_replay import (
    FROZEN_CANDIDATE,
    LiveReplayError,
    LiveReplayInputs,
    build_live_replay,
)
from scripts.research import run_data_first_possession_rating_replay as runner


def _inputs() -> LiveReplayInputs:
    population: list[dict] = []
    observations: list[dict] = []
    snapshots: list[dict] = []
    for week, game_id in enumerate((100, 101, 102)):
        kickoff = f"2026-09-{week + 1:02d}T18:00:00Z"
        population.append(
            {
                "season": 2026,
                "week": week,
                "game_id": game_id,
                "kickoff_utc": kickoff,
                "home_team": "Alpha",
                "away_team": "Beta",
                "forecast_eligible": True,
                "schedule_completed": True,
                "outcome_valid": True,
                "timing_class": "live",
            }
        )
        for team, opponent in (("Alpha", "Beta"), ("Beta", "Alpha")):
            for role in ("offense", "defense"):
                observations.append(
                    {
                        "season": 2026,
                        "game_id": game_id,
                        "kickoff_utc": kickoff,
                        "team": team,
                        "measurement_id": "ppp",
                        "unit_role": role,
                        "denominator": 10.0,
                        "coverage_status": "observed",
                        "timing_class": "live",
                    }
                )
                snapshots.append(
                    {
                        "season": 2026,
                        "as_of_game_id": game_id,
                        "team": team,
                        "measurement_id": "ppp",
                        "unit_role": role,
                        "adjustment_iteration": 4,
                        "adjusted_value": 2.0
                        + week
                        + (0.5 if team == "Alpha" else -0.5),
                        "timing_class": "live",
                    }
                )
    terminal: list[dict] = []
    for team, value in (("Alpha", 3.0), ("Beta", 1.0)):
        for role in ("offense", "defense"):
            terminal.append(
                {
                    "season": 2025,
                    "team": team,
                    "measurement_id": "ppp",
                    "unit_role": role,
                    "adjusted_value": value,
                    "primary_exposure": 20.0,
                }
            )
    return LiveReplayInputs(
        population=pd.DataFrame(population),
        observations=pd.DataFrame(observations),
        snapshots=pd.DataFrame(snapshots),
        historical_terminal=pd.DataFrame(terminal),
    )


def test_replay_keeps_frozen_candidate_and_continuous_week_history() -> None:
    result = build_live_replay(_inputs())

    assert set(result.priors["candidate_id"]) == {FROZEN_CANDIDATE}
    assert result.diagnostics["weeks"] == [0, 1, 2]
    assert len(result.priors) == 4
    assert len(result.rating_states) == 12
    assert len(result.team_states) == 6
    assert result.diagnostics["source_observations"] == 8
    week_zero = result.rating_states[result.rating_states["week"].eq(0)]
    assert week_zero["completed_games"].eq(0).all()
    week_one = result.rating_states[result.rating_states["week"].eq(1)]
    assert week_one["completed_games"].eq(1).all()
    assert week_one["evidence_weight"].gt(0).all()


def test_future_snapshot_cannot_change_an_earlier_state() -> None:
    baseline = build_live_replay(_inputs())
    original = copy.deepcopy(_inputs())
    snapshots = original.snapshots.copy()
    snapshots.loc[snapshots["as_of_game_id"].eq(102), "adjusted_value"] += 100.0
    altered = LiveReplayInputs(
        population=original.population,
        observations=original.observations,
        snapshots=snapshots,
        historical_terminal=original.historical_terminal,
    )

    replayed = build_live_replay(altered)
    before = baseline.rating_states[baseline.rating_states["week"].lt(2)]
    after = replayed.rating_states[replayed.rating_states["week"].lt(2)]
    pd.testing.assert_frame_equal(
        before.reset_index(drop=True), after.reset_index(drop=True)
    )


def test_replay_rejects_a_gap_in_week_history() -> None:
    original = _inputs()
    inputs = LiveReplayInputs(
        population=original.population[~original.population["week"].eq(1)].copy(),
        observations=original.observations,
        snapshots=original.snapshots,
        historical_terminal=original.historical_terminal,
    )

    with pytest.raises(LiveReplayError, match="continuous"):
        build_live_replay(inputs)


def _verifier_inputs(inputs: LiveReplayInputs) -> verifier.VerifierInputs:
    return verifier.VerifierInputs(
        population=inputs.population,
        observations=inputs.observations,
        snapshots=inputs.snapshots,
        historical_terminal=inputs.historical_terminal,
    )


def test_independent_verifier_matches_all_producer_frames() -> None:
    inputs = _inputs()
    produced = build_live_replay(inputs)
    rebuilt = verifier.reconstruct_replay(_verifier_inputs(inputs))

    pd.testing.assert_frame_equal(produced.priors, rebuilt.frames["priors"])
    pd.testing.assert_frame_equal(
        produced.rating_states, rebuilt.frames["rating_states"]
    )
    pd.testing.assert_frame_equal(produced.team_states, rebuilt.frames["team_states"])


def test_independent_verifier_detects_parent_perturbation() -> None:
    inputs = _inputs()
    baseline = verifier.reconstruct_replay(_verifier_inputs(inputs))
    snapshots = inputs.snapshots.copy()
    snapshots.loc[snapshots["as_of_game_id"].eq(101), "adjusted_value"] += 5.0
    changed = verifier.reconstruct_replay(
        verifier.VerifierInputs(
            population=inputs.population,
            observations=inputs.observations,
            snapshots=snapshots,
            historical_terminal=inputs.historical_terminal,
        )
    )
    assert (
        baseline.plans["rating_states"]["records_sha"]
        != changed.plans["rating_states"]["records_sha"]
    )


def test_independent_verifier_import_boundary() -> None:
    paths = (
        Path(verifier.__file__),
        Path("scripts/research/verify_data_first_possession_rating_replay.py"),
    )
    forbidden = {
        "cks_picks_cfb.ratings.possession_live_replay",
        "cks_picks_cfb.ratings.possession_rating_materializer",
        "cks_picks_cfb.ratings.possession_rating_tournament",
        "scripts.research.run_data_first_possession_rating_replay",
        "scripts.research.run_data_first_possession_ratings",
    }
    for path in paths:
        tree = ast.parse(path.read_text())
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not imports & forbidden


def test_replay_parent_accepts_a_new_certified_contract07_run_id() -> None:
    uri = "measurement/week4/measurement-manifest.json"
    manifest = signed_payload(
        {
            "schema_version": POSSESSION_MANIFEST_SCHEMA,
            "identity": {
                "run_id": "possession-v1-measurements-week4-refresh",
                "environment": "preview",
                "development_seasons": [2026],
            },
            "certification_sha256": "signed-certification-digest",
            "output_refs": {name: {} for name in POSSESSION_DATASETS},
            "production_activation_authorized": False,
        }
    )
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()

    class Storage:
        def read_bytes(self, requested_uri: str) -> bytes:
            assert requested_uri == uri
            return raw

    loaded, loaded_raw = runner._measurement_parent(Storage(), uri)
    assert loaded["identity"]["run_id"] == "possession-v1-measurements-week4-refresh"
    assert loaded_raw == raw


def test_rating_replay_verifier_does_not_pin_the_old_contract07_run_id() -> None:
    old_run_id = "possession-v1-measurements-20260922-2026c"
    verifier_script = Path(
        "scripts/research/verify_data_first_possession_rating_replay.py"
    )
    runner_script = Path("scripts/research/run_data_first_possession_rating_replay.py")
    assert old_run_id not in verifier_script.read_text()
    assert old_run_id not in runner_script.read_text()


def test_replay_parent_rejects_uncertified_or_historical_measurements() -> None:
    base = {
        "schema_version": POSSESSION_MANIFEST_SCHEMA,
        "identity": {
            "run_id": "possession-v1-measurements-week4-refresh",
            "environment": "preview",
            "development_seasons": [2026],
        },
        "certification_sha256": "signed-certification-digest",
        "output_refs": {name: {} for name in POSSESSION_DATASETS},
        "production_activation_authorized": False,
    }

    class Storage:
        def __init__(self, payload: dict) -> None:
            self.raw = json.dumps(
                signed_payload(payload), sort_keys=True, separators=(",", ":")
            ).encode()

        def read_bytes(self, _uri: str) -> bytes:
            return self.raw

    for patch in (
        {"certification_sha256": ""},
        {"identity": {**base["identity"], "development_seasons": [2015, 2025]}},
    ):
        payload = {**base, **patch}
        with pytest.raises(runner.RatingReplayRunError, match="certified Contract 07"):
            runner._measurement_parent(Storage(payload), "measurement.json")
