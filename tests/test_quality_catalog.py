"""The checks catalog and the registry must agree, so CI fails on drift."""

from __future__ import annotations

import re
from pathlib import Path

from cks_picks_cfb.quality import REGISTRY

CATALOG = (
    Path(__file__).resolve().parents[1] / "docs" / "data" / "data_quality_checks.md"
)
ROW = re.compile(r"^\| `([a-z_.]+)` \| (block|warn|info) \| (.+?) \| (.+?) \|$", re.M)


def _catalog():
    return {m.group(1): m for m in ROW.finditer(CATALOG.read_text())}


def test_every_registered_check_is_catalogued_and_nothing_extra():
    catalogued = set(_catalog())
    registered = set(REGISTRY)
    assert registered - catalogued == set(), (
        "add these checks to docs/data/data_quality_checks.md"
    )
    assert catalogued - registered == set(), (
        "remove these stale checks from the catalog"
    )


def test_catalog_severity_matches_the_registry():
    for check_id, match in _catalog().items():
        assert match.group(2) == REGISTRY[check_id].severity, check_id


def test_catalog_sections_match_each_check_stage():
    text = CATALOG.read_text()
    sections = {
        "ingest": text.split("## Ingest")[1].split("## Silver")[0],
        "silver": text.split("## Silver")[1].split("## Publish")[0],
        "publish": text.split("## Publish")[1].split("## Web")[0],
    }
    for check_id, spec in REGISTRY.items():
        assert f"`{check_id}`" in sections[spec.stage], (
            f"{check_id} is under the wrong section"
        )


def test_every_row_explains_why_and_what_it_prevents():
    for check_id, match in _catalog().items():
        assert len(match.group(3).strip()) > 10 and len(match.group(4).strip()) > 10, (
            check_id
        )
