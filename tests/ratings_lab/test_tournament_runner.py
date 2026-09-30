"""Tests for standalone V6 tournament runner script."""

from __future__ import annotations

import pytest

from scripts.research.run_v6_tournament import main


def test_tournament_runner_help():
    """Verify tournament runner CLI accepts --help."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
