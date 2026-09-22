"""Current V5 authority stays clear while dated evidence remains accessible."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs/modeling/v5_status.md"
INDEX = ROOT / "docs/plans/index.md"
ARCHIVE = ROOT / "docs/archive/v5-contracts"
METHODOLOGY = ROOT / "docs/modeling/possession_rating_methodology.md"

ENTRY_POINTS = (
    "README.md",
    "AGENTS.md",
    ".agent/CONTEXT.md",
    ".codex/QUICKSTART.md",
    "docs/index.md",
    "docs/planning/roadmap.md",
    "docs/planning/data-first-football-forecasting-roadmap.md",
    "docs/modeling/evaluation.md",
    "docs/modeling/possession_rating_methodology.md",
    "docs/plans/index.md",
)


def _plain(value: str) -> str:
    return " ".join(value.lower().replace("**", "").split())


@pytest.mark.parametrize("name", ENTRY_POINTS)
def test_current_entry_points_link_single_v5_guide(name: str):
    text = (ROOT / name).read_text()
    assert "v5_status.md" in text
    if name != "docs/modeling/v5_status.md":
        first = _plain(text)
        assert "v5" in first
        assert "week 4" in first or "week4" in first
        assert "v4" in first


def test_current_guide_separates_model_completion_and_site_activation():
    text = _plain(CURRENT.read_text())
    for required in (
        "model development: complete and accepted",
        "v4 remains active",
        "stabilized week 4 finals",
        "preview serving rehearsal",
        "rollback proof",
        "separate activation decision",
        "not a prerequisite",
        "like-for-like point-in-time v4 backtest",
        "2026 outcomes",
    ):
        assert required in text
    assert "they do not establish that v5 is superior to v4" in text


def test_only_live_contracts_remain_in_current_plans():
    names = {
        path.name
        for path in (ROOT / "docs/plans").rglob("*v5*.md")
        if path.name != "index.md"
    }
    assert names == {
        "06-v5-prospective-evidence-and-recommendation.md",
        "07-v5-2026-repair-and-measurement-extension.md",
        "08-v5-2026-rating-state-replay.md",
        "09-v5-2026-forecast-and-readiness.md",
        "04-v5-authority-simplification-and-site-cutover.md",
    }
    index = _plain(INDEX.read_text())
    assert "v5 contract archive" in index
    assert "six slates are not a launch prerequisite" in index
    assert "week 4 refresh awaits stabilized finals" in index


def test_archived_contracts_preserve_dated_status_and_history():
    archive = list(ARCHIVE.rglob("*.md"))
    assert len(archive) >= 35
    for name in (
        "v5-ratings-successor-roadmap-and-contracts.md",
        "02-v5-possession-measurement-certification.md",
        "11-v5-forecast-verification-closure.md",
        "12-v5-historical-results-and-readiness-review.md",
        "03-v5-live-research-tooling-completion.md",
    ):
        matches = list(ARCHIVE.rglob(name))
        assert len(matches) == 1
        assert re.search(r"^- \*\*Status:\*\*", matches[0].read_text(), re.MULTILINE)
    assert (ARCHIVE / "index.md").exists()


def test_historical_audit_and_conditional_limits_survive_archival():
    for name, required in (
        ("10-v5-historical-foundation-audit.md", "audit the complete v5 foundation"),
        ("11-v5-forecast-verification-closure.md", "independently reconstruct"),
        (
            "12-v5-historical-results-and-readiness-review.md",
            "not prospective evidence",
        ),
    ):
        content = _plain(next(ARCHIVE.rglob(name)).read_text())
        assert "status: implemented" in content
        assert required in content
    conditional = _plain(
        next(ARCHIVE.rglob("11a-v5-conditional-forecast-verification.md")).read_text()
    )
    assert "conditional_historical_results_only" in conditional
    assert "never restores forecast eligibility" in conditional
    assert "no readiness recommendation" in _plain(
        next(ARCHIVE.rglob("12a-v5-conditional-historical-scorecard.md")).read_text()
    )


def test_archived_successor_contracts_keep_prohibited_parent_boundary():
    for name in (
        "phase4a-prior-and-dynamic-rating-selection-v2.md",
        "phase4b-pregame-context-selection-v2.md",
        "phase5-rating-based-forecast-selection-v2.md",
        "phase6-prospective-evidence-v2.md",
    ):
        text = _plain((ROOT / "docs/plans/2026-09-08" / name).read_text())
        assert "status: superseded" in text
        assert "does not authorize executing old runners" in text


def test_methodology_retains_frozen_mathematics():
    text = _plain(METHODOLOGY.read_text())
    for required in (
        "true points per possession (ppp)",
        "epa per possession",
        "60 structural candidates",
        "i = n / k",
        "p = 1 / (1/p0 + i)",
        "four-pass",
        "no 2015–2019 global constant-fitting step",
        "bridge-first",
        "do not add rating variance again",
    ):
        assert required in text


def test_active_policy_does_not_restore_old_six_slate_gate():
    for path in (CURRENT, INDEX, ROOT / "README.md", ROOT / "AGENTS.md"):
        text = _plain(path.read_text())
        assert (
            "six slates are not" in text
            or "six slates are a useful review window" in text
            or "without a six-slate prelaunch wait" in text
        )
    common = next(ARCHIVE.rglob("v5-ratings-successor-roadmap-and-contracts.md"))
    assert "six qualifying paired slates" in _plain(common.read_text())
    assert "superseded" in _plain(common.read_text()[:1200])
