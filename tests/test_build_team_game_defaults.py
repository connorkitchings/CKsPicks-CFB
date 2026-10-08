"""The weekly team-game build keeps provider-missing PPA null unless told otherwise."""

from __future__ import annotations

from scripts.pipeline.build_team_game_dataset import build_parser

REQUIRED = [
    "--plays-ref-uri",
    "p",
    "--games-ref-uri",
    "g",
    "--corrections-ref-uri",
    "c",
    "--as-of",
    "2026-10-05T00:00:00Z",
    "--output-ref-uri",
    "o",
    "--environment",
    "preview",
]


def test_missing_ppa_stays_null_by_default():
    assert build_parser().parse_args(REQUIRED).nullable_ppa is True


def test_zero_filling_is_an_explicit_opt_out():
    assert (
        build_parser().parse_args([*REQUIRED, "--no-nullable-ppa"]).nullable_ppa
        is False
    )
    assert build_parser().parse_args([*REQUIRED, "--nullable-ppa"]).nullable_ppa is True
