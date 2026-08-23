"""Smoke and integration tests for scripts/pipeline/generate_weekly_bets.py CLI."""

import argparse
import sys
from unittest.mock import MagicMock, patch

import pytest

from scripts.pipeline.generate_weekly_bets import main


def test_cli_help_flag(capsys):
    """Verify that --help exits cleanly with status 0."""
    with patch.object(sys, "argv", ["generate_weekly_bets.py", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Generate Weekly Bets" in captured.out


def test_cli_invalid_config():
    """Verify that a missing config file raises an appropriate exception."""
    with patch.object(
        sys,
        "argv",
        [
            "generate_weekly_bets.py",
            "--config",
            "nonexistent_config_file_12345.yaml",
            "--year",
            "2026",
            "--week",
            "1",
        ],
    ):
        with pytest.raises(Exception):
            main()
