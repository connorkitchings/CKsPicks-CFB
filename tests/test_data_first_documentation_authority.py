"""Regression checks for the active data-first research authority."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROADMAP = ROOT / "docs/planning/data-first-football-forecasting-roadmap.md"
CONTRACT_INDEX = ROOT / "docs/plans/index.md"
PHASE2_PLAN = ROOT / "docs/plans/2026-09-05/02-data-repair-and-recertification.md"
PHASE3_PLAN = ROOT / "docs/plans/2026-09-10/phase3-v2-compact-tournament-state.md"
PHASE4_TO_6 = tuple(
    ROOT / "docs/plans/2026-09-08" / name
    for name in (
        "phase4a-prior-and-dynamic-rating-selection-v2.md",
        "phase4b-pregame-context-selection-v2.md",
        "phase5-rating-based-forecast-selection-v2.md",
        "phase6-prospective-evidence-v2.md",
    )
)


def test_roadmap_records_the_certified_phase_three_and_specified_methodology():
    content = ROADMAP.read_text()

    assert "2026-09-10/phase3-v2-compact-tournament-state.md" in content
    assert "phase3-v2-compact-state-20260910-r2" in content
    assert "2026-09-11/possession-rating-methodology-specification.md" in content
    assert "possession-based rating methodology is specified (2026-09-11)" in content
    assert "remain on execution hold pending replacement contracts" in content
    assert "Repair v2 is implemented and independently verified in Preview." in content


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


def test_phase_three_is_implemented_and_later_contracts_are_approved_but_held():
    phase3 = PHASE3_PLAN.read_text()

    assert "**Status:** Implemented" in phase3
    assert "phase3-v2-compact-state-20260910-r2" in phase3
    assert "verified" in phase3
    assert "idempotent rerun" in phase3
    for contract in PHASE4_TO_6:
        content = contract.read_text()
        assert "**Status:** Approved" in content
        assert "**Execution hold (2026-09-10):**" in content


def test_possession_based_rating_direction_is_specified_not_certified():
    requirements = (ROOT / "docs/modeling/rating_system_requirements.md").read_text()
    catalog = (ROOT / "docs/modeling/measurement_catalog.md").read_text()
    methodology = (ROOT / "docs/modeling/possession_rating_methodology.md").read_text()

    assert "expected **scoring efficiency per possession**" in requirements
    assert "possession_rating_methodology.md" in requirements
    assert "Specified is not certified" in requirements
    assert "not points per possession" in catalog
    assert "Specified, uncertified" in catalog
    assert "true points per possession (PPP)" in methodology
    assert "EPA per possession" in methodology
    assert "excluded from rating evidence" in methodology
    assert "explicitly not a third rating" in methodology
