"""Filesystem-only regression tests for local validation utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from cks_picks_cfb.utils.validation import (
    DataValidationService,
    validate_entity,
    validate_manifest_counts,
    validate_partition_duplicates,
    validate_raw_season,
)


class _Storage:
    def __init__(self, root: Path):
        self._root = root

    def root(self) -> Path:
        return self._root


class _Logger:
    def __init__(self):
        self.events = []
        self.errors = []

    def log_event(self, name, payload):
        self.events.append((name, payload))

    def log_error(self, name, message, payload):
        self.errors.append((name, message, payload))


def _partition(
    root: Path, *, rows: list[dict], manifest_rows: int | None = None
) -> Path:
    root.mkdir(parents=True)
    if rows:
        pd.DataFrame(rows).to_csv(root / "data.csv", index=False)
    (root / "manifest.json").write_text(
        json.dumps({"rows": len(rows) if manifest_rows is None else manifest_rows})
    )
    return root


def test_manifest_and_duplicate_validation_cover_missing_mismatch_and_empty_cases(
    tmp_path,
):
    missing = validate_manifest_counts(tmp_path / "missing", "games")
    assert missing[0].level == "ERROR"

    empty = _partition(tmp_path / "empty", rows=[])
    assert validate_manifest_counts(empty, "games") == []

    mismatch = _partition(tmp_path / "mismatch", rows=[{"id": 1}], manifest_rows=2)
    assert (
        "Manifest row count" in validate_manifest_counts(mismatch, "games")[0].message
    )

    duplicate = _partition(tmp_path / "duplicate", rows=[{"id": 1}, {"id": 1}])
    assert (
        "duplicate rows"
        in validate_partition_duplicates(duplicate, "games", ["id"])[0].message
    )
    assert (
        validate_partition_duplicates(duplicate, "games", ["missing"])[0].level
        == "WARN"
    )


def test_entity_and_raw_validation_find_partition_issues_without_external_storage(
    tmp_path,
):
    storage = _Storage(tmp_path)
    part = _partition(
        tmp_path / "team_game" / "year=2026" / "week=1",
        rows=[{"game_id": 1, "team": "A"}, {"game_id": 1, "team": "A"}],
    )
    logger = _Logger()
    issues = validate_entity(
        storage, 2026, "team_game", ["game_id", "team"], logger=logger
    )
    assert any(issue.level == "ERROR" for issue in issues)
    assert logger.events[0][0] == "validation_entity_partitions"

    raw_root = tmp_path / "games" / "2026"
    _partition(raw_root, rows=[{"id": 1}, {"id": 1}])
    raw_issues = validate_raw_season(storage, 2026, logger=logger)
    assert any("duplicate" in issue.message for issue in raw_issues)
    assert part.exists()


def test_configured_schema_validation_reports_domain_failures_and_short_circuits(
    tmp_path,
):
    storage = _Storage(tmp_path)
    logger = _Logger()
    config = tmp_path / "validation.yaml"
    config.write_text(
        """validation:
  games:
    required_columns: [game_id, score]
    null_checks:
      critical_null_checks: [game_id]
      warning_null_checks: {score: 25}
    range_checks:
      score: {min: 0, max: 100}
    uniqueness_columns: [game_id]
"""
    )
    service = DataValidationService(storage, config_path=config, logger=logger)
    frame = pd.DataFrame({"game_id": [1, 1, None], "score": [-1, None, 101]})
    issues = service.validate_schema(frame, "games")
    assert {issue.level for issue in issues} == {"ERROR", "WARN"}
    assert any("duplicate" in issue.message for issue in issues)
    assert (
        service.validate_schema(pd.DataFrame({"game_id": [1]}), "games")[0].level
        == "ERROR"
    )
    assert service.validate_schema(frame, "missing")[0].level == "WARN"

    partition = _partition(
        tmp_path / "games" / "year=2026" / "week=1",
        rows=[{"game_id": 1, "score": 7}],
    )
    service_issues = service.validate_entity(
        2026, "games", ["game_id"], schema_only=False
    )
    assert service_issues == []
    assert any(event[0] == "validation_entity_complete" for event in logger.events)
    assert partition.exists()
