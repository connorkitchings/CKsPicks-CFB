"""Regression checks for the active data-first research authority."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROADMAP = ROOT / "docs/planning/data-first-football-forecasting-roadmap.md"
CONTRACT_INDEX = ROOT / "docs/plans/index.md"
PHASE2_PLAN = ROOT / "docs/plans/2026-09-05/02-data-repair-and-recertification.md"


def test_roadmap_uses_resequenced_phase_three_to_six_contracts():
    content = ROADMAP.read_text()

    for path in (
        "2026-09-07/01-phase3-measurement-certification-and-core-selection.md",
        "2026-09-07/02-phase4a-context-free-rating-selection.md",
        "2026-09-07/03-phase4b-target-context-selection.md",
        "2026-09-07/04-phase5-final-spread-total-selection.md",
        "2026-09-07/05-phase6-prospective-evidence-and-market-diagnostics.md",
    ):
        assert path in content

    assert "Phase 3C" not in content
    assert "Phase 4B, not Phase 3" in " ".join(content.split())


def test_roadmap_records_only_the_certified_phase_two_handoffs():
    content = ROADMAP.read_text()

    for checksum in (
        "0fd8a32a13ce64a261fa8a0179cdaa1de1cb93e428e362d50ad0aa9970c7761f",
        "7a46adfaff0bcb89b86f244c586d93085557ba3119699da81824ffa4e83f5518",
        "cdeeea01035c9108491a42b2e29a9e6033cdd7781d1ab837df8e411b29afe760",
        "c2ff56b084e58b5cd159f884171df05187746c0dc40b42817912866a540de650",
        "d06ed3968a7bb6ec7ba97212aa2063068c253f26202e810c921b044006ab13ad",
    ):
        assert checksum in content

    assert "1,300\nreturning-production Bronze captures" in content
    assert "26,844 betting-line Bronze captures" in content
    assert "obsolete 2016–2018 play-gap claim is not current authority" in content


def test_contract_index_and_phase_two_plan_close_completed_predecessors():
    index = CONTRACT_INDEX.read_text()
    phase2 = PHASE2_PLAN.read_text()

    assert "**Implemented after repair.**" in index
    assert "**Status:** Implemented" in phase2
    assert "**Reopened 2026-09-06.**" not in index
