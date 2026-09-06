"""Exact-source guards for 2019 legacy comparison evidence."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from cks_picks_cfb.data.history import HistoricalObjectRef, import_historical_object
from cks_picks_cfb.data.legacy_comparison import (
    LegacyArchiveSpec,
    LegacyComparisonRestoreConfig,
    find_and_verify_legacy_archives,
    load_legacy_comparison_restore_config,
)


class _Storage:
    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    def read_bytes(self, uri: str) -> bytes:
        return self.objects[uri]


def _item(uri: str, entity: str) -> HistoricalObjectRef:
    return HistoricalObjectRef(
        uri=uri,
        entity=entity,
        provider="legacy_cfbd_export",
        source_format="json",
        partitions={"year": "2019"},
        metadata={"last_modified": "2026-02-13T00:00:00Z"},
    )


def _config(games_sha: str, teams_sha: str) -> LegacyComparisonRestoreConfig:
    return LegacyComparisonRestoreConfig(
        version="legacy_comparison_2019_restore_v1",
        season=2019,
        output_prefix="artifacts/preview/legacy-comparison/2019",
        archives=(
            LegacyArchiveSpec("games", "raw/games/year=2019/data.json", games_sha),
            LegacyArchiveSpec("teams", "raw/teams/year=2019/data.json", teams_sha),
        ),
        sha256="config",
    )


def test_legacy_comparison_config_is_fixed_to_the_two_2019_archives():
    config = load_legacy_comparison_restore_config()
    assert config.season == 2019
    assert {item.entity for item in config.archives} == {"games", "teams"}
    assert config.output_prefix.startswith("artifacts/preview/legacy-comparison/")


def test_exact_legacy_archives_require_the_pinned_source_checksums():
    games = json.dumps([{"season": 2019, "id": 1}]).encode()
    teams = json.dumps([{"id": 1, "school": "Fixture"}]).encode()
    source = _Storage(
        {
            "raw/games/year=2019/data.json": games,
            "raw/teams/year=2019/data.json": teams,
        }
    )
    config = _config(
        hashlib.sha256(games).hexdigest(), hashlib.sha256(teams).hexdigest()
    )
    verified = find_and_verify_legacy_archives(
        source,
        config,
        [
            _item("raw/games/year=2019/data.json", "games"),
            _item("raw/teams/year=2019/data.json", "teams"),
        ],
    )
    assert [archive.entity for archive, _, _ in verified] == ["games", "teams"]

    altered = _config("0" * 64, hashlib.sha256(teams).hexdigest())
    with pytest.raises(ValueError, match="checksum changed"):
        find_and_verify_legacy_archives(
            source,
            altered,
            [
                _item("raw/games/year=2019/data.json", "games"),
                _item("raw/teams/year=2019/data.json", "teams"),
            ],
        )


def test_import_rejects_changed_source_before_preview_write():
    item = _item("raw/games/year=2019/data.json", "games")
    source = _Storage({item.uri: json.dumps([{"season": 2019, "id": 1}]).encode()})
    with pytest.raises(ValueError, match="checksum changed"):
        import_historical_object(
            source=source,
            destination=_Storage({}),
            conn_url="postgresql://fixture",
            item=item,
            expected_source_sha256="0" * 64,
        )


def test_legacy_comparison_silver_reader_accepts_only_complete_exact_set():
    path = Path(__file__).parents[1] / "scripts/pipeline/build_history_silver.py"
    spec = importlib.util.spec_from_file_location("history_silver", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    storage = _Storage(
        {
            "set.json": json.dumps(
                {
                    "contract_version": "legacy-comparison-2019-source-set-v1",
                    "state": "complete",
                    "season": 2019,
                    "entries": [{"entity": "games", "capture_ids": ["capture"]}],
                }
            ).encode()
        }
    )
    assert module._capture_ids_from_legacy_comparison_source_set(
        storage, "set.json", entity="games", season=2019
    ) == ["capture"]

    storage.objects["set.json"] = json.dumps(
        {
            "contract_version": "legacy-comparison-2019-source-set-v1",
            "state": "incomplete",
            "season": 2019,
            "entries": [{"entity": "games", "capture_ids": ["capture"]}],
        }
    ).encode()
    with pytest.raises(ValueError, match="complete 2019 comparison set"):
        module._capture_ids_from_legacy_comparison_source_set(
            storage, "set.json", entity="games", season=2019
        )
