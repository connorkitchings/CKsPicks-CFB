"""Regression checks for active V5 authority and preserved historical evidence."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ROADMAP = ROOT / "docs/planning/data-first-football-forecasting-roadmap.md"
CONTRACT_INDEX = ROOT / "docs/plans/index.md"
PHASE2_PLAN = ROOT / "docs/plans/2026-09-05/02-data-repair-and-recertification.md"
PHASE3_PLAN = ROOT / "docs/plans/2026-09-10/phase3-v2-compact-tournament-state.md"
V5_DIR = ROOT / "docs/plans/2026-09-13"
COMMON = V5_DIR / "v5-ratings-successor-roadmap-and-contracts.md"
HISTORICAL_REVIEW_DIR = ROOT / "docs/plans/2026-09-18"
CONDITIONAL_RESULTS_DIR = ROOT / "docs/plans/2026-09-19"
BLOCKER_DIAGNOSIS = ROOT / "docs/plans/2026-09-20/02-v5-foundation-blocker-diagnosis.md"
V5_NAMES = (
    "00-v5-documentation-and-methodology-alignment.md",
    "01-v4-feature-v5-diagnostic-closure.md",
    "02-v5-possession-measurement-certification.md",
    "03-v5-possession-rating-estimation.md",
    "04-v5-forecast-bridge-and-fitting-window.md",
    "05-v5-prospective-readiness-and-shadow-tooling.md",
    "06-v5-prospective-evidence-and-recommendation.md",
)
REPLACEMENTS = {
    "phase4a-prior-and-dynamic-rating-selection-v2.md": (V5_NAMES[3],),
    "phase4b-pregame-context-selection-v2.md": (V5_NAMES[4],),
    "phase5-rating-based-forecast-selection-v2.md": (V5_NAMES[4],),
    "phase6-prospective-evidence-v2.md": (V5_NAMES[5], V5_NAMES[6]),
}
# Bound assertions to current authority, not intentionally preserved historical text.
ENTRY_POINTS = {
    "README.md": None,
    "AGENTS.md": "**Roadmap (2026 transition):**",
    ".agent/CONTEXT.md": "### Feature Engineering",
    ".codex/QUICKSTART.md": "### Install Dependencies",
    "docs/index.md": "## Documentation policy",
    "docs/planning/data-first-football-forecasting-roadmap.md": "## Historical predecessor identities",
    "docs/planning/roadmap.md": "## Historical successor rules",
    "docs/plans/index.md": "### Certified foundations",
    "docs/modeling/rating_system_requirements.md": "### Historical Phase 1",
    "docs/modeling/measurement_catalog.md": "## Responsibility boundary",
    "docs/modeling/evaluation.md": "## Ordered evaluation layers",
    "docs/modeling/possession_rating_methodology.md": "## Rating definitions",
    "docs/architecture/repository_boundaries.md": "## Dependency direction",
}


def _plain(text: str) -> str:
    text = re.sub(r"^> ", "", text, flags=re.MULTILINE)
    return " ".join(text.replace("**", "").split()).lower()


def _assert_current_checkpoint(text: str) -> None:
    content = _plain(text)
    for required in (
        "v5 ratings successor",
        "feature schema v5",
        "phase 3 v2",
        "r6",
        "possession",
        "historical",
        "2025",
        "forecast",
        "original phase 4b retained manifest remains prohibited as a forecasting parent",
    ):
        assert required in content
    for stale in (
        r"(?:still needs|needs|remains pending) preview certification",
        r"next design task will define",
        r"before a dedicated possession-based methodology plan",
        r"remain on execution hold pending replacement contracts",
        r"possession measurements remain uncertified",
        r"next ratings task is 03",
        r"next ratings task is 03: possession rating estimation",
        r"sole eligible forecast parent for contract 05",
        r"original phase 4b retained manifest (?:is eligible|may be used|is permitted)",
    ):
        assert not re.search(stale, content), stale


@pytest.mark.parametrize("relative_path", ENTRY_POINTS)
def test_active_entry_points_share_one_checkpoint(relative_path: str):
    content = (ROOT / relative_path).read_text()
    end = ENTRY_POINTS[relative_path]
    if end:
        assert end in content
        content = content.split(end, 1)[0]
    _assert_current_checkpoint(content)
    if ROOT / relative_path != ROADMAP:
        assert "data-first-football-forecasting-roadmap.md" in content


@pytest.mark.parametrize(
    "contradiction",
    (
        "Phase 3 v2 still needs Preview certification.",
        "Possession measurements remain uncertified.",
        "The next ratings task is 03: possession rating estimation.",
        "The 04B artifact is the sole eligible forecast parent for Contract 05.",
        "The original Phase 4B retained manifest is eligible for forecasting.",
    ),
)
def test_checkpoint_check_rejects_conflicting_claims(contradiction: str):
    # A correct summary must not hide an additional, contradictory authority claim.
    content = (ROOT / "README.md").read_text()
    with pytest.raises(AssertionError):
        _assert_current_checkpoint(content + "\n" + contradiction)


def test_roadmap_preserves_certified_evidence_and_original_audit_dispositions():
    content = _plain(ROADMAP.read_text())
    for required in (
        "2026-09-10/phase3-v2-compact-tournament-state.md",
        "phase3-v2-compact-state-20260910-r2",
        "2026-09-11/possession-rating-methodology-specification.md",
        "repair v2",
        "1,300 returning-production bronze captures",
        "26,844 betting-line bronze captures",
        "obsolete 2016–2018 play-gap claim is not current authority",
        "11.36%",
    ):
        assert required in content
    for checksum in (
        "0fd8a32a13ce64a261fa8a0179cdaa1de1cb93e428e362d50ad0aa9970c7761f",
        "7a46adfaff0bcb89b86f244c586d93085557ba3119699da81824ffa4e83f5518",
        "cdeeea01035c9108491a42b2e29a9e6033cdd7781d1ab837df8e411b29afe760",
        "c2ff56b084e58b5cd159f884171df05187746c0dc40b42817912866a540de650",
        "d06ed3968a7bb6ec7ba97212aa2063068c253f26202e810c921b044006ab13ad",
    ):
        assert checksum in content
    assert "**Implemented after repair.**" in CONTRACT_INDEX.read_text()
    assert "**Status:** Implemented" in PHASE2_PLAN.read_text()
    phase3 = PHASE3_PLAN.read_text()
    for evidence in ("**Status:** Implemented", "verified", "idempotent rerun"):
        assert evidence in phase3


@pytest.mark.parametrize("name", V5_NAMES)
def test_all_v5_contracts_are_linked_with_accurate_lifecycle(name: str):
    contract = (V5_DIR / name).read_text()
    status = re.search(r"^- \*\*Status:\*\* (.+)$", contract, re.MULTILINE)
    assert status is not None
    if name.startswith(("00-", "02-", "03-", "04-")):
        assert status[1] in {"In Progress", "Implemented"}
    else:
        assert status[1] in {"Approved", "In Progress", "Implemented"}
    for metadata in ("Approval source", "Implementation log", "Commit policy"):
        assert f"**{metadata}:**" in contract
    for document in (COMMON, ROADMAP, CONTRACT_INDEX):
        assert (
            f"/{name})" in document.read_text() or f"]({name})" in document.read_text()
        )
    index_row = next(
        line for line in CONTRACT_INDEX.read_text().splitlines() if f"/{name})" in line
    )
    assert f"**{status[1]}.**" in index_row


def test_historical_first_contracts_preserve_lifecycle_and_gate_2026_application():
    required = {
        "10-v5-historical-foundation-audit.md": (
            "status: implemented",
            "audit the complete v5 foundation",
        ),
        "11-v5-forecast-verification-closure.md": (
            "status: approved",
            "independently reconstruct",
        ),
        "12-v5-historical-results-and-readiness-review.md": (
            "status: draft",
            "not prospective evidence",
        ),
    }
    for name, (status, phrase) in required.items():
        content = _plain((HISTORICAL_REVIEW_DIR / name).read_text())
        assert status in content
        assert phrase in content
        assert f"2026-09-18/{name}" in CONTRACT_INDEX.read_text()

    for name in (
        "07-v5-2026-repair-and-measurement-extension.md",
        "08-v5-2026-rating-state-replay.md",
        "09-v5-2026-forecast-and-readiness.md",
    ):
        content = _plain((HISTORICAL_REVIEW_DIR / name).read_text())
        for required_gate in (
            "contracts 10-12",
            "explicitly accepts",
            "re-reviewed",
        ):
            assert required_gate in content


def test_conditional_results_lane_cannot_bypass_eligibility_or_readiness():
    verification = (
        CONDITIONAL_RESULTS_DIR / "11a-v5-conditional-forecast-verification.md"
    ).read_text()
    scorecard = (
        CONDITIONAL_RESULTS_DIR / "12a-v5-conditional-historical-scorecard.md"
    ).read_text()
    assert "status: implemented" in _plain(verification)
    assert any(
        status in _plain(scorecard)
        for status in ("status: approved", "status: in progress", "status: implemented")
    ), "12A should be Approved, In Progress, or Implemented"
    for content in (verification, scorecard):
        plain = _plain(content)
        assert "conditional_historical_results_only" in content
        assert "never restores forecast eligibility" in plain
        assert "prospective evidence" in plain
        assert "2026" in plain

    assert "if any reconstruction comparison fails" in _plain(verification)
    assert "do not calculate or publish any scorecard values" in _plain(verification)
    assert "no v4 comparison" in _plain(scorecard)
    assert "no readiness recommendation" in _plain(scorecard)

    final_review = _plain(
        (
            HISTORICAL_REVIEW_DIR / "12-v5-historical-results-and-readiness-review.md"
        ).read_text()
    )
    for required in (
        "10b is complete",
        "implemented 11a and approved 12a have successfully completed",
        "every foundation blocker",
    ):
        assert required in final_review

    for document in (ROADMAP, CONTRACT_INDEX, COMMON, ROOT / "docs/index.md"):
        plain = _plain(document.read_text())
        assert "conditional_historical_results_only" in plain
        assert "10b" in plain
        assert "2026" in plain

    for name in (
        "06-v5-prospective-evidence-and-recommendation.md",
        "07-v5-2026-repair-and-measurement-extension.md",
        "08-v5-2026-rating-state-replay.md",
        "09-v5-2026-forecast-and-readiness.md",
    ):
        directory = V5_DIR if name.startswith("06-") else HISTORICAL_REVIEW_DIR
        plain = _plain((directory / name).read_text())
        assert "conditional-results clarification (2026-09-20)" in plain
        assert "conditional_historical_results_only" in plain
        assert "contracts 10-12" in plain
        assert "re-reviewed-application gate" in plain


def test_forecast_lifecycle_keeps_historical_artifact_but_reopens_eligibility():
    umbrella = (V5_DIR / "04-v5-forecast-bridge-and-fitting-window.md").read_text()
    certification = (
        ROOT / "docs/plans/2026-09-17/02-v5-forecast-calibration-and-certification.md"
    ).read_text()
    assert "**Status:** In Progress" in umbrella
    assert "**Status:** In Progress" in certification
    for content in (umbrella, certification, ROADMAP.read_text()):
        plain = _plain(content)
        assert "historical evidence" in plain
        assert "independently reconstruct" in plain
        assert "not an eligible forecast parent" in plain


@pytest.mark.parametrize("old_name, successors", REPLACEMENTS.items())
def test_superseded_contracts_preserve_history_and_name_successors(
    old_name, successors
):
    content = (ROOT / "docs/plans/2026-09-08" / old_name).read_text()
    assert "**Status:** Superseded" in content
    assert "**Approval source:** User approved" in content
    assert "**Execution hold (2026-09-10):**" in content
    assert "**Superseded (2026-09-13):**" in content
    assert "does not authorize executing old runners" in _plain(content)
    for name in successors:
        assert f"../2026-09-13/{name}" in content


def test_original_methodology_is_an_implemented_amended_documentation_milestone():
    original = (
        ROOT / "docs/plans/2026-09-11/possession-rating-methodology-specification.md"
    ).read_text()
    assert "**Status:** Implemented" in original
    assert "**Approval source:** User selected" in original
    assert "**Methodology amended (2026-09-13):**" in original
    assert COMMON.name in original
    assert "original text below records the September 11 design" in original


def test_amended_methodology_locks_scoring_chronology_and_uncertainty():
    methodology = _plain(
        (ROOT / "docs/modeling/possession_rating_methodology.md").read_text()
    )
    for required in (
        "true points per possession (ppp)",
        "epa per possession",
        "eligible regulation offensive possession points",
        "excluded regulation offensive possession points",
        "regulation non-offense points",
        "overtime points",
        "unresolved scoring increments",
        "explicitly not a third rating",
        "fixed first-generation settings",
        "no 2015–2019 global constant-fitting step",
        "i = n / k",
        "p = 1 / (1/p0 + i)",
        "evidence_weight = i / (1/p0 + i)",
        "valid only when p0 equals one",
        "60 structural candidates",
        "four-pass",
        "bridge-first",
        "latest five eligible completed seasons",
        "identical 2022–2025 games",
        "preserve continuous state",
        "mean squared earlier rolling-origin prediction error",
        "do not add rating variance again",
    ):
        assert required in methodology
    for row in (
        "| scale floor | 0.30 | 0.50 |",
        "| fallback scale | 1.00 | 1.50 |",
        "| equivalent prior exposure k | 8 possessions | 20 possessions |",
    ):
        assert row in methodology
    catalog = _plain((ROOT / "docs/modeling/measurement_catalog.md").read_text())
    assert "not points per possession" in catalog
    assert "specified, uncertified" in catalog
    assert "no catalog registration is authorized" in catalog


def test_prospective_gates_and_deferred_families_remain_explicit():
    evaluation = _plain((ROOT / "docs/modeling/evaluation.md").read_text())
    for required in (
        "six qualifying normal-coverage paired slates",
        ">=40 games",
        "t−2h target/t−1h hard measured freeze",
        ">=24h",
        "week 0 and historical replays do not count",
        "promotion requires a separate contract",
        "markets are comparison-only after football evaluation",
        "nb2/arithmetic are later challengers",
    ):
        assert required in evaluation
    boundaries = _plain(
        (ROOT / "docs/architecture/repository_boundaries.md").read_text()
    )
    assert (
        "research commands may freeze and score isolated shadow artifacts" in boundaries
    )
    assert (
        "no catalog registration or production schema changes are authorized"
        in boundaries
    )


def test_quickstart_examples_are_not_live_execution_authority():
    content = _plain((ROOT / ".codex/QUICKSTART.md").read_text())
    assert "illustrative examples" in content
    assert (
        "not instructions to execute a research phase or the current live configuration"
        in content
    )


def test_current_authority_records_the_approved_scorecard_and_blocker_diagnosis():
    assert any(
        status in _plain(BLOCKER_DIAGNOSIS.read_text())
        for status in ("status: approved", "status: in progress", "status: implemented")
    ), "Contract 02 should be Approved, In Progress, or Implemented"
    diagnosis = _plain(BLOCKER_DIAGNOSIS.read_text())
    for required in (
        "finding 001",
        "finding 003",
        "read-only",
        "must not repair data",
        "one subsequent corrective execution contract",
    ):
        assert required in diagnosis

    for document in (ROADMAP, CONTRACT_INDEX, COMMON, ROOT / "docs/index.md"):
        content = _plain(document.read_text())
        assert "approved" in content
        assert "12a" in content
        assert "conditional_historical_results_only" in content
        assert "contract11_permitted: false" in content or "full contract 11" in content

    for document in (ROADMAP, CONTRACT_INDEX, COMMON):
        content = _plain(document.read_text())
        assert "12a | draft" not in content
        assert "10b remains in progress" not in content
        assert "draft 11a" not in content
