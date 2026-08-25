"""Bounded season-scoped materialization tests for the Phase 1 builder."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from helpers import (
    AS_OF,
    HISTORICAL_SEASONS,
    multi_season_league,
    stage_rating_parents,
)

from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
)
from cks_picks_cfb.data.storage.local import LocalStorage
from cks_picks_cfb.ratings.contracts import load_measurement_config
from cks_picks_cfb.ratings.observations import build_measurement_observations
from scripts.pipeline import build_rating_measurements as cli

CONFIG_PATH = "conf/ratings/measurement_baseline_v1.yaml"


class _ReadRecordingStorage:
    """Delegate storage wrapper counting raw parquet data reads."""

    def __init__(self, inner):
        self._inner = inner
        self.data_reads = 0

    def read_bytes(self, uri: str) -> bytes:
        if uri.endswith("/data.parquet"):
            self.data_reads += 1
        return self._inner.read_bytes(uri)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _staged(tmp_path: Path, **league_kwargs):
    storage = LocalStorage(tmp_path)
    uris = stage_rating_parents(storage, multi_season_league(**league_kwargs))
    return storage, uris


def _refs(storage, uris):
    byplay = tuple(cli._ref(storage, uri) for uri in uris["byplay"])
    drives = tuple(cli._ref(storage, uri) for uri in uris["drives"])
    games = tuple(cli._ref(storage, uri) for uri in uris["games"])
    outcomes = tuple(cli._ref(storage, uri) for uri in uris["game_outcomes"])
    team_game = tuple(cli._ref(storage, uri) for uri in uris["reconciled_team_game"])
    return byplay, drives, games, outcomes, team_game


def _scoped_build(storage, uris, config, progress=None):
    byplay_refs, drives_refs, games_refs, outcome_refs, team_game_refs = _refs(
        storage, uris
    )
    byplay_by_season, drives_by_season = cli._season_parent_maps(
        storage, byplay_refs, drives_refs, config
    )
    return cli._build_observations_season_scoped(
        storage=storage,
        config=config,
        byplay_by_season=byplay_by_season,
        drives_by_season=drives_by_season,
        games=cli._concat_frames(storage, games_refs),
        outcomes=cli._concat_frames(storage, outcome_refs),
        reconciled_team_game=cli._concat_frames(storage, team_game_refs),
        as_of=AS_OF,
        code_sha="codesha",
        config_sha="configsha",
        parent_ref_shas="aaa;bbb",
        progress=progress,
    )


def test_season_scoped_output_matches_all_at_once_builder(tmp_path):
    """The refactored builder reproduces the all-at-once path exactly."""
    config = load_measurement_config(CONFIG_PATH)
    storage, uris = _staged(tmp_path, include_completed_2026=False)
    scoped_frame, merged_audit, execution = _scoped_build(storage, uris, config)

    byplay_refs, drives_refs, games_refs, outcome_refs, team_game_refs = _refs(
        storage, uris
    )
    all_at_once = build_measurement_observations(
        byplay=cli._concat_frames(storage, byplay_refs),
        drives=cli._concat_frames(storage, drives_refs),
        games=cli._concat_frames(storage, games_refs),
        outcomes=cli._concat_frames(storage, outcome_refs),
        reconciled_team_game=cli._concat_frames(storage, team_game_refs),
        config=config,
        as_of=AS_OF,
        code_sha="codesha",
        config_sha="configsha",
        parent_ref_shas="aaa;bbb",
    )
    assert scoped_frame.equals(all_at_once.frame)
    historical_exclusions = [
        entry
        for entry in all_at_once.audit["excluded_games"]
        if entry["season"] in HISTORICAL_SEASONS
    ]
    assert merged_audit["excluded_games"] == historical_exclusions
    assert (
        merged_audit["quality_flag_counts"] == all_at_once.audit["quality_flag_counts"]
    )
    assert merged_audit["season_counts"] == all_at_once.audit["season_counts"]
    assert (
        merged_audit["out_of_scope_season_games"]
        == all_at_once.audit["out_of_scope_season_games"]
    )
    assert execution["raw_seasons_processed"] == list(HISTORICAL_SEASONS)
    assert execution["observation_rows_by_season"] == {
        season: 4 * 26 for season in HISTORICAL_SEASONS
    }
    assert execution["raw_input_rows"]["byplay"] == {
        season: 16 for season in HISTORICAL_SEASONS
    }
    assert execution["raw_input_rows"]["drives"] == {
        season: 8 for season in HISTORICAL_SEASONS
    }


def test_one_season_at_a_time_processing(tmp_path):
    """Each season's raw parents are read and built before the next loads."""
    config = load_measurement_config(CONFIG_PATH)
    storage, uris = _staged(tmp_path)
    events: list[str] = []
    _scoped_build(storage, uris, config, progress=events.append)
    for index, season in enumerate(HISTORICAL_SEASONS):
        byplay_read = events.index(f"read:byplay:{season}")
        drives_read = events.index(f"read:drives:{season}")
        built = events.index(f"build:{season}")
        assert byplay_read < drives_read < built
        if index + 1 < len(HISTORICAL_SEASONS):
            assert built < events.index(f"read:byplay:{HISTORICAL_SEASONS[index + 1]}")
    assert len(events) == 3 * len(HISTORICAL_SEASONS)


def _drop_flag_value(argv: list[str], flag: str, value: str) -> list[str]:
    """Remove exactly one flag/value pair matching the given value."""
    pruned: list[str] = []
    removed = False
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == flag and index + 1 < len(argv):
            if not removed and argv[index + 1] == value:
                removed = True
                index += 2
                continue
            pruned.extend([item, argv[index + 1]])
            index += 2
            continue
        pruned.append(item)
        index += 1
    if not removed:
        raise AssertionError(f"{flag} {value} not found in argv")
    return pruned


def test_missing_season_parent_fails_before_raw_reads(tmp_path, capsys):
    storage = LocalStorage(tmp_path)
    uris = stage_rating_parents(storage, multi_season_league())
    design_id = load_measurement_config(CONFIG_PATH).design_id
    argv = _cli_argv(uris, design_id)
    dropped = uris["byplay"][HISTORICAL_SEASONS.index(2023)]
    argv = _drop_flag_value(argv, "--byplay-ref-uri", dropped)
    assert argv.count("--byplay-ref-uri") == len(HISTORICAL_SEASONS) - 1
    recorder = _ReadRecordingStorage(storage)
    with (
        patch.object(cli, "get_storage", return_value=recorder),
        patch.object(cli, "_require_committed_code", return_value="test-code-sha"),
    ):
        with pytest.raises(ValueError, match="Missing raw parent refs.*2023"):
            cli.main(argv)
    assert recorder.data_reads == 0


def test_duplicate_season_parent_fails_before_raw_reads(tmp_path):
    storage = LocalStorage(tmp_path)
    uris = stage_rating_parents(storage, multi_season_league())
    design_id = load_measurement_config(CONFIG_PATH).design_id
    argv = _cli_argv(uris, design_id)
    argv.extend(["--byplay-ref-uri", uris["byplay"][0]])
    recorder = _ReadRecordingStorage(storage)
    with (
        patch.object(cli, "get_storage", return_value=recorder),
        patch.object(cli, "_require_committed_code", return_value="test-code-sha"),
    ):
        with pytest.raises(ValueError, match="Duplicate byplay parent for season 2021"):
            cli.main(argv)
    assert recorder.data_reads == 0


def test_extra_protected_season_parent_fails_before_raw_reads(tmp_path):
    storage = LocalStorage(tmp_path)
    uris = stage_rating_parents(storage, multi_season_league())
    design_id = load_measurement_config(CONFIG_PATH).design_id
    league = multi_season_league()
    protected_byplay = league["byplay"][
        pd.to_numeric(league["byplay"]["season"]) == 2026
    ]
    assert not protected_byplay.empty
    ref, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="byplay",
            parent_refs=(),
            code_sha="seed",
            config_sha="seed",
            as_of=AS_OF,
            schema_version="byplay_v1",
            tier="silver",
        ),
        records=protected_byplay.to_dict("records"),
        partitions={"seasons": [2026]},
    )
    extra_uri = "artifacts/test/parents/byplay-2026.json"
    storage.write_bytes(json.dumps(ref.__dict__, sort_keys=True).encode(), extra_uri)
    argv = _cli_argv(uris, design_id) + ["--byplay-ref-uri", extra_uri]
    recorder = _ReadRecordingStorage(storage)
    with (
        patch.object(cli, "get_storage", return_value=recorder),
        patch.object(cli, "_require_committed_code", return_value="test-code-sha"),
    ):
        with pytest.raises(ValueError, match="non-historical seasons \\[2026\\]"):
            cli.main(argv)
    assert recorder.data_reads == 0


def test_cli_materializes_season_scoped_with_prior_only_2026_states(tmp_path, capsys):
    """End-to-end bounded build keeps 2026 snapshots strictly prior-only."""
    storage = LocalStorage(tmp_path)
    uris = stage_rating_parents(storage, multi_season_league())
    design_id = load_measurement_config(CONFIG_PATH).design_id
    argv = _cli_argv(uris, design_id)
    with (
        patch.object(cli, "get_storage", return_value=storage),
        patch.object(cli, "_require_committed_code", return_value="test-code-sha"),
    ):
        cli.main(argv)
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "built"
    assert payload["all_checks_passed"] is True

    prefix = f"artifacts/research/rating-successor/measurements/{design_id}"
    report = json.loads(storage.read_bytes(f"{prefix}/audit/report.json"))
    execution = report["execution"]
    assert execution["materialization"] == "season_scoped_v1"
    assert execution["raw_seasons_processed"] == list(HISTORICAL_SEASONS)
    assert execution["observation_rows_by_season"] == {
        str(season): 4 * 26 for season in HISTORICAL_SEASONS
    }
    assert set(execution["timing_by_stage_ms"]) == {
        "read",
        "observation_build",
        "snapshot_build",
        "terminal_build",
        "audit",
    }

    observations = read_dataset(
        storage,
        DatasetRef(**json.loads(storage.read_bytes(f"{prefix}/observations/ref.json"))),
    )
    assert set(observations["season"].astype(int)) == set(HISTORICAL_SEASONS)

    snapshots = read_dataset(
        storage,
        DatasetRef(**json.loads(storage.read_bytes(f"{prefix}/snapshots/ref.json"))),
    )
    snapshots_2026 = snapshots[snapshots["season"].astype(int) == 2026]
    assert snapshots_2026["as_of_game_id"].nunique() == 2
    assert len(snapshots_2026) == 2 * 26
    assert (snapshots_2026["coverage_status"] == "missing").all()
    assert (snapshots_2026["missing_reason"] == "no_eligible_evidence").all()
    assert (snapshots_2026["games_exposure"] == 0).all()
    assert snapshots_2026["evidence_max_kickoff_utc"].isna().all()


def test_report_identity_excludes_timing_diagnostics():
    report = {
        "execution": {"timing_by_stage_ms": {"read": 1, "audit": 2}},
        "checks": {},
    }
    identity = cli._report_identity(report)
    assert "timing_by_stage_ms" not in identity["execution"]
    assert report["execution"]["timing_by_stage_ms"] == {"read": 1, "audit": 2}


def _cli_argv(uris, design_id: str) -> list[str]:
    prefix = f"artifacts/research/rating-successor/measurements/{design_id}"
    argv = [
        "--environment",
        "preview",
        "--measurement-config",
        CONFIG_PATH,
        "--as-of",
        AS_OF.isoformat(),
    ]
    for uri in uris["byplay"]:
        argv.extend(["--byplay-ref-uri", uri])
    for uri in uris["drives"]:
        argv.extend(["--drives-ref-uri", uri])
    argv.extend(
        [
            "--games-ref-uri",
            uris["games"][0],
            "--outcomes-ref-uri",
            uris["game_outcomes"][0],
            "--team-game-ref-uri",
            uris["reconciled_team_game"][0],
            "--observations-ref-uri",
            f"{prefix}/observations/ref.json",
            "--snapshots-ref-uri",
            f"{prefix}/snapshots/ref.json",
            "--terminal-snapshots-ref-uri",
            f"{prefix}/terminal/ref.json",
            "--report-uri",
            f"{prefix}/audit/report.json",
        ]
    )
    return argv
