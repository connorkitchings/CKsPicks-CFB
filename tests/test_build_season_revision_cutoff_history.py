"""Completed-week cutoffs must match the certified manifest unless corrected."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.pipeline import build_season_revision as builder

AS_OF = datetime(2026, 10, 25, 15, tzinfo=timezone.utc)
PRE = datetime(2026, 10, 25, 20, 52, tzinfo=timezone.utc)
CONF = Path("conf/season/2026")


def manifest(week8_pre: str) -> dict:
    return {
        "revision_id": "season-2026-w8-preview-r3",
        "pre_week_cutoffs": {"7": "2026-10-13T18:00:00Z", "8": week8_pre},
        "post_week_cutoffs": {"6": "2026-10-11T15:00:00Z", "7": "2026-10-18T14:00:00Z"},
    }


CERTIFIED = manifest("2026-10-20T14:39:00Z")
STALE = manifest("2026-10-20T18:00:00Z")
FIX_WEEK_8 = {("pre", "8"): datetime(2026, 10, 20, 14, 39, tzinfo=timezone.utc)}


def cutoffs(previous: dict, corrections=None):
    return builder.revision_cutoffs(
        previous, week=9, as_of=AS_OF, pre_week_cutoff=PRE, corrections=corrections
    )


def test_matching_completed_week_cutoffs_pass():
    pre, post = cutoffs(CERTIFIED)

    builder.check_completed_week_cutoffs(pre, post, CERTIFIED, week=9)

    assert pre["9"] == "2026-10-25T20:52:00Z"
    assert post["8"] == "2026-10-25T15:00:00Z"


def test_stale_week_8_pre_week_cutoff_is_refused():
    pre, post = cutoffs(STALE)

    with pytest.raises(ValueError, match=r"pre_week_cutoffs\[8\].*14:39:00Z"):
        builder.check_completed_week_cutoffs(pre, post, CERTIFIED, week=9)


def test_explicit_correction_fixes_stale_cutoff_and_passes():
    pre, post = cutoffs(STALE, FIX_WEEK_8)

    builder.check_completed_week_cutoffs(
        pre, post, CERTIFIED, week=9, corrections=FIX_WEEK_8
    )

    assert pre["8"] == "2026-10-20T14:39:00Z"


def test_correction_does_not_exempt_other_cutoffs():
    drifted = manifest("2026-10-20T14:39:00Z")
    drifted["post_week_cutoffs"]["6"] = "2026-10-11T16:00:00Z"
    pre, post = cutoffs(drifted, FIX_WEEK_8)

    with pytest.raises(ValueError, match=r"post_week_cutoffs\[6\]"):
        builder.check_completed_week_cutoffs(
            pre, post, CERTIFIED, week=9, corrections=FIX_WEEK_8
        )


def test_correction_of_missing_week_raises():
    with pytest.raises(ValueError, match="no pre-week cutoff for week 3"):
        cutoffs(CERTIFIED, {("pre", "3"): AS_OF})


def test_parse_cutoff_correction():
    assert builder.parse_cutoff_correction("8:pre=2026-10-20T14:39:00Z") == (
        ("pre", "8"),
        datetime(2026, 10, 20, 14, 39, tzinfo=timezone.utc),
    )
    with pytest.raises(ValueError, match="WEEK:pre"):
        builder.parse_cutoff_correction("8=2026-10-20T14:39:00Z")


def test_committed_w9_manifest_is_the_known_stale_case():
    certified = json.loads((CONF / "revision_manifest_w8_v3.json").read_text())
    w9 = json.loads((CONF / "revision_manifest_w9_v2.json").read_text())

    with pytest.raises(ValueError, match=r"pre_week_cutoffs\[8\]"):
        builder.check_completed_week_cutoffs(
            w9["pre_week_cutoffs"], w9["post_week_cutoffs"], certified, week=9
        )
