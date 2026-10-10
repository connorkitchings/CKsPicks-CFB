"""Exact, evidence-gated CFBD post-kickoff quote declarations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload

REASON = "cfbd_pregame_consensus_fetched_post_kickoff"
GAMES = frozenset({401871051, 401871066, 401871090})


def accepted_late_quote(
    quote: Mapping[str, Any],
    *,
    game_id: Any,
    target: str,
    declarations: Sequence[Mapping[str, Any]],
) -> bool:
    """No game-wide bypass: require exact quote, target and source provenance."""
    provider = quote.get("__capture_provider", quote.get("capture_provider"))
    entity = quote.get("entity", quote.get("source_entity"))
    if provider != "cfbd" or entity != "betting_lines" or int(game_id) not in GAMES:
        return False
    return any(
        str(item.get("game_id")) == str(game_id)
        and item.get("target") == target
        and str(item.get("quote_id")) == str(quote.get("quote_id"))
        and item.get("reason") == REASON
        and item.get("provider") == "cfbd"
        and item.get("entity") == "betting_lines"
        for item in declarations
    )


def validate_late_evidence(declarations, receipt):
    """Declarations can enter a market lock only with a passing empirical receipt."""
    if not declarations:
        return
    if receipt is None:
        raise ValueError("accepted late quotes require CFBD comparison evidence")
    verify_signed_payload(receipt, label="CFBD closing-line comparison")
    rows = receipt.get("comparisons", [])
    if (
        receipt.get("schema_version") != "cfbd_closing_line_comparison_v1"
        or receipt.get("state") != "passed"
        or receipt.get("season") != 2026
        or not rows
        or not all(row.get("matches") is True for row in rows)
        or {int(row["game_id"]) for row in rows}
        != {int(item["game_id"]) for item in receipt.get("requests", [])}
    ):
        raise ValueError("CFBD comparison does not support accepted late quotes")
    for item in declarations:
        if (
            int(item["game_id"]) not in GAMES
            or item.get("target") not in {"spread", "total"}
            or not item.get("quote_id")
            or item.get("reason") != REASON
            or item.get("provider") != "cfbd"
            or item.get("entity") != "betting_lines"
        ):
            raise ValueError("invalid accepted late quote declaration")
