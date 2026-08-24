"""CLI integration tests for build_rating_measurements.py (Task 4)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest
from helpers import AS_OF, simple_league

from cks_picks_cfb.data.lake import BuildRequest, DatasetRef, build_dataset_version
from cks_picks_cfb.data.storage.local import LocalStorage
from cks_picks_cfb.ratings.contracts import load_measurement_config
from scripts.pipeline import build_rating_measurements as cli
from scripts.pipeline import build_rating_team_states as state_cli

CONFIG_PATH = "conf/ratings/measurement_baseline_v1.yaml"


def _seed_parents(storage: LocalStorage) -> dict[str, list[str]]:
    league = simple_league()
    frames = {
        "byplay": ("byplay_v1", league["byplay"]),
        "drives": ("drives_v1", league["drives"]),
        "games": ("games_v2", league["games"]),
        "game_outcomes": ("game_outcomes_v1", league["outcomes"]),
        "reconciled_team_game": ("team_game_v1", league["reconciled_team_game"]),
    }
    uris: dict[str, list[str]] = {}
    cutoff = AS_OF
    for dataset, (schema_version, frame) in frames.items():
        ref, manifest = build_dataset_version(
            storage,
            build=BuildRequest(
                dataset=dataset,
                parent_refs=(),
                code_sha="seed",
                config_sha="seed",
                as_of=cutoff,
                schema_version=schema_version,
                tier="silver",
            ),
            records=frame.to_dict("records"),
        )
        uri = f"artifacts/test/parents/{dataset}.json"
        storage.write_bytes(json.dumps(asdict(ref), sort_keys=True).encode(), uri)
        uris[dataset] = [uri]
    return uris


def _argv(storage_uris, tmp_path: Path, design_id: str, as_of=None) -> list[str]:
    prefix = f"artifacts/research/rating-successor/measurements/{design_id}"
    return [
        "--environment",
        "preview",
        "--measurement-config",
        CONFIG_PATH,
        "--as-of",
        as_of or AS_OF.isoformat(),
        "--byplay-ref-uri",
        storage_uris["byplay"][0],
        "--drives-ref-uri",
        storage_uris["drives"][0],
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
