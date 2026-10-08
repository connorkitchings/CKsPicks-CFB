"""The corrected team-stats payload builder takes its published run as an argument."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from scripts.pipeline import build_corrected_publication_payloads as build


def test_week_lists_parse_ranges_and_singles():
    assert build.parse_weeks("1-5") == [1, 2, 3, 4, 5]
    assert build.parse_weeks("6") == [6]
    assert build.parse_weeks("1-2, 6") == [1, 2, 6]


@pytest.mark.parametrize("bad", ["", "0", "a", "3-", "-2", "1;2"])
def test_bad_week_lists_are_refused(bad):
    with pytest.raises(ValueError):
        build.parse_weeks(bad)


class _Storage:
    def __init__(self, raw: bytes):
        self.raw = raw

    def read_bytes(self, key: str) -> bytes:
        assert key == "rebuild/6a/run-x/root-manifest.json"
        return self.raw


def test_a_changed_root_manifest_is_refused_whatever_the_run():
    raw = json.dumps({"run_id": "run-x"}).encode()
    with pytest.raises(SystemExit, match="run-x changed"):
        build.open_published_run(
            _Storage(raw), "run-x", hashlib.sha256(b"other").hexdigest()
        )


def _run_with_silver(versions: dict[str, str]):
    objects = {}
    manifests = {}
    for dataset, version in versions.items():
        key = f"lake/silver/dataset={dataset}/version={version}/manifest.json"
        objects[key] = "h"
        manifests[key] = json.dumps({"partitions": {"seasons": [2026]}}).encode()
    return SimpleNamespace(objects=objects, read=lambda key: manifests[key])


def test_source_versions_name_the_run_and_its_root_not_a_fixed_lineage():
    run = _run_with_silver({"byplay": "b1", "drives": "d1"})
    pins = {
        "parents": [
            {"dataset": "games", "version_id": "g1"},
            {"dataset": "teams", "version_id": "t1"},
        ],
        "game_outcomes": {"version_id": "o1"},
    }
    versions = build.corrected_source_versions(run, pins, "run-x", "f" * 64)
    assert versions == {
        "lineage": "corrected:run-x",
        "rebuild_root_sha256": "f" * 64,
        "byplay": "b1",
        "drives": "d1",
        "games": "g1",
        "game_outcomes": "o1",
        "teams": "t1",
    }
