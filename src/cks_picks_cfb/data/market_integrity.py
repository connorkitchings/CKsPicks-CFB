"""Immutable canonical snapshot identities for corrected market decisions."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SNAPSHOT_POLICY = "canonical_snapshot_v2"
SNAPSHOT_FIELDS = (
    "game_id",
    "captured_at",
    "spread",
    "total",
    "spread_rule",
    "total_rule",
    "spread_provider_count",
    "total_provider_count",
    "source_quote_ids",
    "policy_version",
)


def snapshot_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Keep consensus values separate from selected prediction/quote points."""
    quotes = record["source_quote_ids"]
    if isinstance(quotes, str):
        quotes = json.loads(quotes)
    return {
        "game_id": record["game_id"],
        "captured_at": record["market_captured_at"],
        "spread": record.get("canonical_spread_line", record["home_team_spread_line"]),
        "total": record.get("canonical_total_line", record["total_line"]),
        "spread_rule": record["spread_selection_rule"],
        "total_rule": record["total_selection_rule"],
        "spread_provider_count": record["spread_provider_count"],
        "total_provider_count": record["total_provider_count"],
        "source_quote_ids": sorted(quotes),
        "policy_version": record["market_policy_version"],
    }


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
    ).encode()


def snapshot_identity(record: dict[str, Any]) -> str:
    """Content-bound identity; a different run alone never changes the snapshot."""
    payload = snapshot_payload(record)
    payload["policy_version"] = SNAPSHOT_POLICY
    return hashlib.sha256(_canonical(payload)).hexdigest()[:32]


def verify_snapshot(cur: Any, record: dict[str, Any]) -> None:
    """Compare after INSERT/ON CONFLICT; never silently accept different content."""
    cur.execute(
        "SELECT "
        + ", ".join(SNAPSHOT_FIELDS)
        + " FROM market_snapshots WHERE snapshot_id = %s",
        (record["market_snapshot_id"],),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError("market snapshot insert has no readback")
    actual = dict(zip(SNAPSHOT_FIELDS, row, strict=True))
    actual["source_quote_ids"] = sorted(actual["source_quote_ids"])
    for key in ("spread", "total"):
        if actual[key] is not None:
            actual[key] = float(actual[key])
    if _canonical(actual) != _canonical(snapshot_payload(record)):
        raise ValueError(
            f"conflicting immutable market snapshot {record['market_snapshot_id']}"
        )
