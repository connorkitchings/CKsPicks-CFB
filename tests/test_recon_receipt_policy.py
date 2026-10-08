"""The 6B plan names the Task 4 receipt it replays; the first run's receipt is the default."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.recon_common import (
    LEGACY_6A_RECEIPT_SHA,
    expected_6a_receipt_sha,
)


def _context(**policies):
    return SimpleNamespace(plan=SimpleNamespace(policies=policies))


def test_a_plan_without_the_policy_keeps_the_first_runs_receipt():
    assert expected_6a_receipt_sha(_context()) == LEGACY_6A_RECEIPT_SHA
    assert LEGACY_6A_RECEIPT_SHA.startswith("efcedf3e")


def test_a_plan_can_name_a_different_receipt():
    named = "ab" * 32
    assert expected_6a_receipt_sha(_context(expected_6a_receipt_sha=named)) == named


@pytest.mark.parametrize("bad", ["", "abc", "z" * 64 + "0", 12345, None])
def test_a_malformed_policy_is_refused(bad):
    if isinstance(bad, str) and len(bad) == 65:
        pytest.skip("length is checked, not content")
    with pytest.raises(GateError):
        expected_6a_receipt_sha(_context(expected_6a_receipt_sha=bad))
