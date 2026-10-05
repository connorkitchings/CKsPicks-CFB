"""``scoring_attribution_evidence_v1``: CFBD drive evidence for admitted allocation groups.

One evidence row per admitted group. The id is deterministic and tied to the retained
bundle bytes (``cfbd_drives:<sha256 of group id and bundle hash>``, the full digest). The
locator names the retained bundle and every event the group allocates, so a reader can
resolve the citation without trusting the producer. Rights fields are the user-specified
terms recorded in contract Appendix A (Amendment 3); they are not an independent legal
finding.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from typing import Any

import pandas as pd

TERMS_URI = "https://collegefootballdata.com/key"
RIGHTS_BASIS = "cfbd_api_user_agreement"
SOURCE_KIND = "cfbd_drives"
VERIFIER_VERSION = "cfbd_drives_5a"
BUNDLE_PREFIX = "raw/cfbd/drives/"


class EvidenceError(ValueError):
    """Evidence inputs are ambiguous, missing or inconsistent."""


def evidence_id(group_id: str, bundle_sha256: str) -> str:
    digest = hashlib.sha256(f"{group_id}|{bundle_sha256}".encode()).hexdigest()
    return f"cfbd_drives:{digest}"


def bundle_index(
    records: Iterable[Mapping[str, Any]], read_bundle: Callable[[str], bytes]
) -> dict[int, Mapping[str, Any]]:
    """Map each CFBD game id to its single retained, hash-verified bundle record."""
    index: dict[int, Mapping[str, Any]] = {}
    for record in records:
        raw = read_bundle(record["file"])
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise EvidenceError(f"bundle hash mismatch: {record['file']}")
        for row in json.loads(raw):
            game_id = int(row["gameId"])
            existing = index.get(game_id)
            if existing is not None and existing["sha256"] != record["sha256"]:
                raise EvidenceError(f"game {game_id} appears in more than one bundle")
            index[game_id] = record
    return index


def build_evidence(
    decisions: pd.DataFrame,
    ledger: pd.DataFrame,
    index: Mapping[int, Mapping[str, Any]],
) -> pd.DataFrame:
    """Evidence rows for every ``admitted`` group, from decisions and the v1 ledger."""
    admitted = decisions[decisions["decision"] == "admitted"]
    by_event = ledger.set_index(["season", "game_id", "team", "source_event_id"])
    rows: list[dict[str, Any]] = []
    for group in admitted.itertuples(index=False):
        record = index.get(int(group.game_id))
        if record is None:
            raise EvidenceError(f"no retained bundle for game {group.game_id}")
        declared = sorted(json.loads(group.event_ids))
        present = [
            event
            for event in declared
            if (int(group.season), int(group.game_id), group.team, event)
            in by_event.index
        ]
        replaced = [event for event in declared if event not in set(present)]
        events = [
            by_event.loc[(int(group.season), int(group.game_id), group.team, event)]
            for event in present
        ]
        if not events:
            raise EvidenceError(f"group {group.group_id} has no ledger events")
        first = min(events, key=lambda e: (int(e["quarter"]), int(e["play_number"])))
        rows.append(
            {
                "evidence_id": evidence_id(group.group_id, record["sha256"]),
                "allocation_group_id": group.group_id,
                "season": int(group.season),
                "game_id": int(group.game_id),
                "team": group.team,
                "quarter": int(first["quarter"]),
                "points": int(round(float(group.net_points))),
                "source_event_id": first.name[3],
                "possession_id": first["associated_possession_id"],
                "conversion_for_event_id": first["conversion_for_event_id"],
                "unit_category": first["unit_category"],
                "source_kind": SOURCE_KIND,
                "source_uri": BUNDLE_PREFIX + record["file"],
                "source_sha256": record["sha256"],
                "source_locator": json.dumps(
                    {
                        "bundle_file": record["file"],
                        "game_id": int(group.game_id),
                        "event_ids": present,
                        "replaced_baseline_event_ids": replaced,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "terms_uri": TERMS_URI,
                "rights_basis": RIGHTS_BASIS,
                "verdict": "supports",
                "reason": str(group.primary_cause),
                "verifier_version": VERIFIER_VERSION,
                "captured_at": record["captured_at_utc"],
            }
        )
    return pd.DataFrame(rows).sort_values("evidence_id").reset_index(drop=True)


def evidence_reference_problems(
    evidence: pd.DataFrame,
    ledger: pd.DataFrame,
    index: Mapping[int, Mapping[str, Any]],
    read_bundle: Callable[[str], bytes],
) -> list[str]:
    """Independent checks: references resolve, locators match the ledger, bytes verify."""
    problems: list[str] = []
    if evidence["evidence_id"].duplicated().any():
        problems.append("duplicate evidence ids")
    known = set(evidence["evidence_id"])
    cited: set[str] = set()
    for row in ledger.itertuples(index=False):
        ids = json.loads(row.evidence_ids)
        if row.admission == "corroborated" and not ids:
            problems.append(f"{row.source_event_id}: corroborated without evidence")
        if row.admission != "corroborated" and ids:
            problems.append(
                f"{row.source_event_id}: evidence on a non-corroborated event"
            )
        for item in ids:
            cited.add(item)
            if item not in known:
                problems.append(f"{row.source_event_id}: unresolved evidence id")
    if known - cited:
        problems.append(f"{len(known - cited)} evidence rows are cited by no event")
    events = {
        (int(r.season), int(r.game_id), r.team, r.source_event_id): r
        for r in ledger.itertuples(index=False)
    }
    bundle_cache: dict[str, str] = {}
    for row in evidence.itertuples(index=False):
        locator = json.loads(row.source_locator)
        record = index.get(int(row.game_id))
        if record is None or record["sha256"] != row.source_sha256:
            problems.append(
                f"{row.evidence_id}: source hash differs from the pinned manifest"
            )
            continue
        if row.evidence_id != evidence_id(row.allocation_group_id, row.source_sha256):
            problems.append(
                f"{row.evidence_id}: id is not derived from group and bundle"
            )
        for event in locator.get("replaced_baseline_event_ids", []):
            if (int(row.season), int(row.game_id), row.team, event) in events:
                problems.append(
                    f"{row.evidence_id}: replaced baseline event {event} is still in the ledger"
                )
        for event in locator["event_ids"]:
            ledger_row = events.get(
                (int(row.season), int(row.game_id), row.team, event)
            )
            if ledger_row is None:
                problems.append(
                    f"{row.evidence_id}: locator event {event} not in ledger"
                )
            elif ledger_row.allocation_group_id != row.allocation_group_id:
                problems.append(f"{row.evidence_id}: event {event} is in another group")
        if row.source_uri not in bundle_cache:
            data = read_bundle(row.source_uri.removeprefix(BUNDLE_PREFIX))
            bundle_cache[row.source_uri] = hashlib.sha256(data).hexdigest()
        if bundle_cache[row.source_uri] != row.source_sha256:
            problems.append(
                f"{row.evidence_id}: retained bytes do not match source_sha256"
            )
    return problems
