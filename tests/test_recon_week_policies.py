from types import SimpleNamespace

import pytest

from cks_picks_cfb.rebuild import (
    recon_comparison,
    recon_grades,
    recon_markets,
    recon_receipt,
)
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.recon_common import (
    EXPECTED_COUNTS,
    WEEKS,
    plan_counts,
    plan_total,
    plan_weeks,
    require_served_population,
    served_weeks,
    unserved_as_of,
)

WEEK6 = {
    "weeks": list(range(7)),
    "expected_counts": {**{str(w): n for w, n in EXPECTED_COUNTS.items()}, "6": 58},
    "served_weeks": list(WEEKS),
    "unserved_week_as_of": {"6": "2026-10-09T22:00:00Z"},
}


def ctx(**policies):
    return SimpleNamespace(plan=SimpleNamespace(policies=policies))


def test_default_policies_reproduce_the_published_population():
    c = ctx()
    assert plan_weeks(c) == WEEKS
    assert plan_counts(c) == EXPECTED_COUNTS
    assert plan_total(c) == 271
    assert served_weeks(c) == WEEKS
    assert unserved_as_of(c) == {}
    require_served_population(c, "markets")


def test_week6_policies_extend_population_and_declare_the_unserved_cutoff():
    c = ctx(**WEEK6)
    assert plan_weeks(c) == tuple(range(7))
    assert plan_total(c) == 271 + 58
    assert served_weeks(c) == WEEKS
    assert unserved_as_of(c) == {6: "2026-10-09T22:00:00Z"}


@pytest.mark.parametrize(
    "policies, message",
    [
        ({"weeks": [0, 1, 3]}, "contiguous"),
        ({"weeks": [1, 2]}, "contiguous"),
        ({"weeks": [0, 1, 2, 3, 4, 5, 6]}, "expected_counts is required"),
        ({**WEEK6, "expected_counts": {"0": 8}}, "exactly the planned weeks"),
        (
            {**WEEK6, "expected_counts": {**WEEK6["expected_counts"], "6": 0}},
            "exactly the planned weeks",
        ),
    ],
)
def test_malformed_week_or_count_policies_are_refused(policies, message):
    with pytest.raises(GateError, match=message):
        plan_counts(ctx(**policies))


def test_unserved_cutoff_must_be_declared_and_timezone_aware():
    with pytest.raises(GateError, match="exactly the weeks"):
        unserved_as_of(ctx(**{**WEEK6, "unserved_week_as_of": {}}))
    with pytest.raises(GateError, match="timezone"):
        unserved_as_of(
            ctx(**{**WEEK6, "unserved_week_as_of": {"6": "2026-10-09T22:00:00"}})
        )
    with pytest.raises(GateError, match="ISO"):
        unserved_as_of(ctx(**{**WEEK6, "unserved_week_as_of": {"6": "soon"}}))
    with pytest.raises(GateError, match="served_weeks"):
        served_weeks(ctx(**{**WEEK6, "served_weeks": [3, 2]}))


@pytest.mark.parametrize(
    "build",
    [
        recon_markets.build_markets,
        recon_markets.build_finals,
        recon_grades.build_old_grade_reproduction,
        recon_grades.build_retrospective_grades,
        recon_comparison.build_comparison,
        recon_receipt.build_receipt,
    ],
)
def test_reconciliation_stages_refuse_a_week6_population(build):
    with pytest.raises(GateError, match="served Weeks 0-5 runs only"):
        build(ctx(**WEEK6))
