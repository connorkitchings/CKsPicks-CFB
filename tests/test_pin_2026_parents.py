"""Pinning the 2026 Silver parents from explicitly named versions."""

from __future__ import annotations

import json

import pytest

from scripts.pipeline.pin_6a_silver_parents import PARENTS_2026, pin_2026_from_versions


class FakeStorage:
    def __init__(self, objects):
        self.objects = objects

    def exists(self, key):
        return key in self.objects

    def read_bytes(self, key):
        return self.objects[key]


def _manifest(dataset, version, **extra):
    return {
        "schema_version": f"{dataset}_v1",
        "content_sha": (dataset[0] * 64),
        "uri": f"lake/silver/dataset={dataset}/version={version}/data.parquet",
        "row_count": 10,
        **extra,
    }


def _storage(parents=PARENTS_2026):
    objects = {}
    parent_versions = []
    for index, dataset in enumerate(PARENTS_2026):
        version = f"p{index}"
        if dataset in parents:
            objects[
                f"lake/silver/dataset={dataset}/version={version}/manifest.json"
            ] = json.dumps(_manifest(dataset, version)).encode()
            parent_versions.append(version)
    for dataset, version in (
        ("byplay", "bp1"),
        ("game_outcomes", "go1"),
        ("reconciled_team_game", "rt1"),
    ):
        extra = (
            {
                "parent_versions": parent_versions,
                "as_of": "2026-10-05T00:00:00+00:00",
                "code_sha": "c" * 40,
            }
            if dataset == "byplay"
            else {}
        )
        objects[f"lake/silver/dataset={dataset}/version={version}/manifest.json"] = (
            json.dumps(_manifest(dataset, version, **extra)).encode()
        )
    return FakeStorage(objects)


def _pin(storage):
    return pin_2026_from_versions(
        storage,
        byplay_version="bp1",
        game_outcomes_version="go1",
        reconciled_team_game_version="rt1",
        source="test pin",
    )


def test_parents_are_the_four_datasets_of_the_named_byplay_in_order():
    pin = _pin(_storage())
    assert [p["dataset"] for p in pin["parents"]] == list(PARENTS_2026)
    assert pin["schema_version"] == "rebuild_6a_silver_2026_parents_v1"
    assert pin["game_outcomes"]["version_id"] == "go1"
    assert pin["legacy_comparison"]["byplay"]["version_id"] == "bp1"
    assert pin["legacy_comparison"]["reconciled_team_game"]["version_id"] == "rt1"
    assert pin["legacy_byplay_as_of"] == "2026-10-05T00:00:00+00:00"
    assert pin["source"] == "test pin"


def test_a_byplay_with_a_different_parent_set_is_refused():
    with pytest.raises(SystemExit, match="unexpected parent set"):
        _pin(_storage(parents=("plays", "games", "teams")))


def test_a_missing_version_is_refused_not_replaced_by_latest():
    storage = _storage()
    del storage.objects["lake/silver/dataset=game_outcomes/version=go1/manifest.json"]
    with pytest.raises(SystemExit, match="parent manifest not found"):
        _pin(storage)
