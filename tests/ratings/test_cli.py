"""CLI integration tests for build_rating_measurements.py (Task 4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import AS_OF, multi_season_league, stage_rating_parents

from cks_picks_cfb.data.lake import DatasetRef
from cks_picks_cfb.data.storage.local import LocalStorage
from cks_picks_cfb.ratings.contracts import load_measurement_config
from scripts.pipeline import build_rating_foundation_review as foundation_cli
from scripts.pipeline import build_rating_measurements as cli
from scripts.pipeline import build_rating_score_tournament as tournament_cli
from scripts.pipeline import build_rating_team_states as state_cli

CONFIG_PATH = "conf/ratings/measurement_baseline_v1.yaml"
V3_CONFIG_PATH = "conf/ratings/measurement_baseline_v3.yaml"


def _seed_parents(storage: LocalStorage) -> dict[str, list[str]]:
    return stage_rating_parents(storage, multi_season_league())


def _seed_true_ppso_parents(storage: LocalStorage) -> dict[str, list[str]]:
    """Stage historical parents with one reconciled 7-3 score stream per game."""
    league = multi_season_league()
    for game in league["games"].itertuples(index=False):
        if game.season not in (2021, 2022, 2023, 2024, 2025):
            continue
        game_mask = (league["byplay"]["season"] == game.season) & (
            league["byplay"]["game_id"] == game.game_id
        )
        rows = (
            league["byplay"]
            .loc[game_mask]
            .sort_values(["drive_number", "quarter", "play_number"], kind="mergesort")
        )
        for row in rows.itertuples():
            is_home = row.offense == game.home_team
            final_play = (
                row.play_number
                == rows[rows["drive_number"] == row.drive_number]["play_number"].max()
            )
            league["byplay"].loc[row.Index, "offense_score"] = (
                7 if is_home and final_play else 3 if final_play else 0
            )
            league["byplay"].loc[row.Index, "defense_score"] = 0 if is_home else 7
        outcome_mask = (league["outcomes"]["season"] == game.season) & (
            league["outcomes"]["game_id"] == game.game_id
        )
        league["outcomes"].loc[outcome_mask, ["home_points", "away_points"]] = [7, 3]
    return stage_rating_parents(storage, league)


def _argv(
    storage_uris,
    tmp_path: Path,
    design_id: str,
    as_of=None,
    config_path: str = CONFIG_PATH,
) -> list[str]:
    prefix = f"{load_measurement_config(config_path).research_prefix}/{design_id}"
    argv = [
        "--environment",
        "preview",
        "--measurement-config",
        config_path,
        "--as-of",
        as_of or AS_OF.isoformat(),
    ]
    for uri in storage_uris["byplay"]:
        argv.extend(["--byplay-ref-uri", uri])
    for uri in storage_uris["drives"]:
        argv.extend(["--drives-ref-uri", uri])
    argv.extend(
        [
            "--games-ref-uri",
            storage_uris["games"][0],
            "--outcomes-ref-uri",
            storage_uris["game_outcomes"][0],
            "--team-game-ref-uri",
            storage_uris["reconciled_team_game"][0],
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


@pytest.fixture()
def seeded_storage(tmp_path):
    storage = LocalStorage(tmp_path)
    uris = _seed_parents(storage)
    return storage, uris


def _run(storage, argv):
    captured = {}

    def fake_get_storage(*, environment=None, **kwargs):
        captured["environment"] = environment
        return storage

    from unittest.mock import patch

    with (
        patch.object(cli, "get_storage", side_effect=fake_get_storage),
        patch.object(cli, "_require_committed_code", return_value="test-code-sha"),
    ):
        cli.main(argv)
    return captured


def test_cli_builds_all_three_artifacts_and_passes_checks(seeded_storage, capsys):
    storage, uris = seeded_storage
    design_id = load_measurement_config(CONFIG_PATH).design_id
    _run(storage, _argv(uris, None, design_id))
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "built"
    assert payload["all_checks_passed"] is True

    prefix = f"artifacts/research/rating-successor/measurements/{design_id}"
    observations_ref = DatasetRef(
        **json.loads(storage.read_bytes(f"{prefix}/observations/ref.json"))
    )
    snapshots_ref = DatasetRef(
        **json.loads(storage.read_bytes(f"{prefix}/snapshots/ref.json"))
    )
    terminal_ref = DatasetRef(
        **json.loads(storage.read_bytes(f"{prefix}/terminal/ref.json"))
    )
    assert observations_ref.dataset == "rating_measurement_observations"
    assert snapshots_ref.dataset == "rating_adjusted_measurement_snapshots"
    assert terminal_ref.dataset == "rating_adjusted_measurement_terminal_snapshots"
    report = json.loads(storage.read_bytes(f"{prefix}/audit/report.json"))
    assert report["measurement_design_id"] == design_id
    assert report["all_checks_passed"] is True
    assert report["checks"]["future_rows_ok"] is True
    assert report["checks"]["two_team_symmetry_ok"] is True
    assert report["checks"]["market_free_ok"] is True
    assert report["checks"]["no_double_counting_ok"] is True
    assert report["lineage"]["observations_ref"]["version_id"] == (
        observations_ref.version_id
    )


def test_cli_rerun_is_idempotent(seeded_storage, capsys):
    storage, uris = seeded_storage
    design_id = load_measurement_config(CONFIG_PATH).design_id
    argv = _argv(uris, None, design_id)
    _run(storage, argv)
    first = json.loads(capsys.readouterr().out)
    _run(storage, argv)
    second = json.loads(capsys.readouterr().out)
    assert first["observations_ref"] == second["observations_ref"]
    assert first["snapshots_ref"] == second["snapshots_ref"]
    assert first["report_sha256"] == second["report_sha256"]


def test_cli_v3_true_ppso_builds_new_schemas_and_is_idempotent(tmp_path, capsys):
    storage = LocalStorage(tmp_path)
    uris = _seed_true_ppso_parents(storage)
    config = load_measurement_config(V3_CONFIG_PATH)
    argv = _argv(uris, tmp_path, config.design_id, config_path=V3_CONFIG_PATH)
    _run(storage, argv)
    first = json.loads(capsys.readouterr().out)
    _run(storage, argv)
    second = json.loads(capsys.readouterr().out)
    assert first["observations_ref"] == second["observations_ref"]
    assert first["report_sha256"] == second["report_sha256"]
    prefix = f"{config.research_prefix}/{config.design_id}"
    report = json.loads(storage.read_bytes(f"{prefix}/audit/report.json"))
    assert report["checks"]["score_stream_reconciliation_ok"] is True
    assert report["checks"]["ppso_terminal_means_ok"] is True
    assert report["observations"]["score_reconciliation"]
    assert all(
        values["exact_rate"] >= 0.94
        for values in report["observations"]["score_reconciliation"].values()
    )
    observations_ref = DatasetRef(
        **json.loads(storage.read_bytes(f"{prefix}/observations/ref.json"))
    )
    assert observations_ref.schema_version == "rating_measurement_observations_v3"


def test_cli_report_collision_fails_loudly(seeded_storage):
    storage, uris = seeded_storage
    design_id = load_measurement_config(CONFIG_PATH).design_id
    argv = _argv(uris, None, design_id)
    _run(storage, argv)
    prefix = f"artifacts/research/rating-successor/measurements/{design_id}"
    storage.write_bytes(b"tampered", f"{prefix}/audit/report.json")
    with pytest.raises(FileExistsError, match="Immutable artifact exists"):
        _run(storage, argv)


def test_cli_rejects_production(seeded_storage):
    storage, uris = seeded_storage
    design_id = load_measurement_config(CONFIG_PATH).design_id
    argv = _argv(uris, None, design_id)
    argv[argv.index("--environment") + 1] = "production"
    with pytest.raises(ValueError, match="only in preview"):
        _run(storage, argv)


def test_cli_rejects_outputs_outside_research_prefix(seeded_storage):
    storage, uris = seeded_storage
    design_id = load_measurement_config(CONFIG_PATH).design_id
    argv = _argv(uris, None, design_id)
    argv[argv.index("--report-uri") + 1] = "artifacts/production/week0/report.json"
    with pytest.raises(ValueError, match="research prefix"):
        _run(storage, argv)


def test_cli_rejects_design_id_mismatch(seeded_storage):
    storage, uris = seeded_storage
    design_id = load_measurement_config(CONFIG_PATH).design_id
    argv = _argv(uris, None, design_id) + ["--expected-design-id", "0" * 64]
    with pytest.raises(Exception, match="mismatch"):
        _run(storage, argv)


def test_cli_rejects_wrong_parent_dataset(seeded_storage):
    storage, uris = seeded_storage
    design_id = load_measurement_config(CONFIG_PATH).design_id
    argv = _argv(uris, None, design_id)
    argv[argv.index("--byplay-ref-uri") + 1] = uris["drives"][0]
    with pytest.raises(ValueError, match="incompatible dataset"):
        _run(storage, argv)


def test_state_cli_requires_passing_phase1_v2_refs_and_builds_states(
    seeded_storage, capsys
):
    storage, uris = seeded_storage
    design_id = load_measurement_config(CONFIG_PATH).design_id
    _run(storage, _argv(uris, None, design_id))
    capsys.readouterr()
    prefix = (
        "artifacts/research/rating-successor/states/"
        + state_cli.load_team_state_config(
            "conf/ratings/team_state_baseline_v1.yaml"
        ).design_id
    )
    argv = [
        "--environment",
        "preview",
        "--state-config",
        "conf/ratings/team_state_baseline_v1.yaml",
        "--as-of",
        AS_OF.isoformat(),
        "--observations-ref-uri",
        f"artifacts/research/rating-successor/measurements/{design_id}/observations/ref.json",
        "--snapshots-ref-uri",
        f"artifacts/research/rating-successor/measurements/{design_id}/snapshots/ref.json",
        "--terminal-snapshots-ref-uri",
        f"artifacts/research/rating-successor/measurements/{design_id}/terminal/ref.json",
        "--phase1-report-uri",
        f"artifacts/research/rating-successor/measurements/{design_id}/audit/report.json",
        "--measurement-states-ref-uri",
        f"{prefix}/measurement/ref.json",
        "--team-states-ref-uri",
        f"{prefix}/team/ref.json",
        "--report-uri",
        f"{prefix}/audit/report.json",
    ]
    from unittest.mock import patch

    with (
        patch.object(state_cli, "get_storage", return_value=storage),
        patch.object(state_cli, "_require_commit", return_value="test-code-sha"),
    ):
        state_cli.main(argv)
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "built"
    assert (
        DatasetRef(**json.loads(storage.read_bytes(f"{prefix}/team/ref.json"))).dataset
        == "rating_team_states"
    )


def test_rating_cli_defaults_point_at_current_lineage_configs():
    """Superseded v1/v2 research configs must never become implicit defaults."""
    assert cli.DEFAULT_CONFIG == (
        Path(__file__).resolve().parents[2]
        / "conf/ratings/measurement_baseline_v3.yaml"
    )
    assert state_cli.DEFAULT_CONFIG == (
        Path(__file__).resolve().parents[2] / "conf/ratings/team_state_baseline_v2.yaml"
    )
    assert foundation_cli.DEFAULT_CONFIG == (
        Path(__file__).resolve().parents[2] / "conf/ratings/foundation_review_v2.yaml"
    )
    assert tournament_cli.DEFAULT_CONFIG == (
        Path(__file__).resolve().parents[2]
        / "conf/ratings/score_model_tournament_v3.yaml"
    )
