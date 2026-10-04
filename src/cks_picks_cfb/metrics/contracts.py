"""Semantic validators for the Gold measurement datasets (Window 2 Step 5B).

``schema_for`` / ``validate_frame`` check column presence, keys, non-null identities,
integers, booleans, timestamps and allowed values. They cannot express nullable numbers or
cross-field rules, so these validators add them. Every validator returns a list of problem
strings (empty when valid); ``require_*`` raise :class:`GoldContractError` on any problem.

Null semantics (the contract):

- A missing source value is null, never zero. A verified zero-event population is zero.
- A ratio with a zero denominator is null (undefined), not zero.
- An incomplete numerator is null while a known denominator is preserved.
- Count and sum metrics carry denominator 1 and ``value == numerator``.
- ``coverage_status == "missing"`` requires a ``missing_reason`` and a null ``value``.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable

import pandas as pd

from cks_picks_cfb.metrics import registry as reg

MAX_RESOLVED_INCREMENT = 8
SHA256_HEX = 64


class GoldContractError(ValueError):
    """A Gold dataset frame breaks a semantic rule of its contract."""


def canonical_json_text(value: Any) -> str:
    """Canonical JSON text used for stored lists and maps."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def possession_id_for(
    season: int, game_id: int, drive_number: int, offense: str
) -> str:
    """Deterministic possession identity from the composite key."""
    raw = f"{int(season)}|{int(game_id)}|{int(drive_number)}|{offense}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def _null(value: Any) -> bool:
    return (
        value is None
        or (isinstance(value, float) and math.isnan(value))
        or value is pd.NA
    )


def _json(value: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _sorted_string_list(value: Any) -> bool:
    parsed = _json(value)
    return (
        isinstance(parsed, list)
        and all(isinstance(v, str) for v in parsed)
        and parsed == sorted(parsed)
    )


def _string_map(value: Any) -> bool:
    parsed = _json(value)
    return isinstance(parsed, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()
    )


def team_game_metrics_problems(frame: pd.DataFrame) -> list[str]:
    problems: list[str] = []
    if frame.duplicated(["season", "game_id", "team", "role", "metric"]).any():
        problems.append("duplicate metric identity")
    for row in frame.to_dict("records"):
        name = row["metric"]
        where = f"{row['game_id']}/{row['team']}/{row['role']}/{name}"
        definition = reg.BY_NAME.get(name)
        if definition is None:
            problems.append(f"{where}: metric not in the registry")
            continue
        if (row["definition_version"], row["population_id"], row["coverage_unit"]) != (
            definition.definition_version,
            definition.population_id,
            definition.coverage_unit,
        ):
            problems.append(
                f"{where}: definition, population or coverage unit differs from the registry"
            )
        num, den, value = row["numerator"], row["denominator"], row["value"]
        for label, number in (
            ("numerator", num),
            ("denominator", den),
            ("value", value),
        ):
            if not _null(number) and not math.isfinite(float(number)):
                problems.append(f"{where}: {label} is not finite")
        eligible, observed = row["eligible_count"], row["observed_count"]
        for label, count in (
            ("eligible_count", eligible),
            ("observed_count", observed),
        ):
            if not _null(count) and (float(count) < 0 or float(count) != int(count)):
                problems.append(f"{where}: {label} is not a nonnegative integer")
        if (
            not _null(eligible)
            and not _null(observed)
            and float(observed) > float(eligible)
        ):
            problems.append(f"{where}: observed_count exceeds eligible_count")
        if row["coverage_status"] == "missing":
            if _null(row["missing_reason"]) or not str(row["missing_reason"]).strip():
                problems.append(f"{where}: missing coverage needs a missing_reason")
            if not _null(value):
                problems.append(f"{where}: missing coverage must have a null value")
        else:
            if not _null(row["missing_reason"]):
                problems.append(
                    f"{where}: observed coverage must not carry a missing_reason"
                )
            if definition.kind in ("count", "sum"):
                if (
                    _null(num)
                    or _null(value)
                    or float(den) != 1.0
                    or abs(float(value) - float(num)) > 1e-9
                ):
                    problems.append(
                        f"{where}: a {definition.kind} metric needs denominator 1 and value == numerator"
                    )
            elif not _null(num) and not _null(den):
                if float(den) == 0:
                    if not _null(value):
                        problems.append(
                            f"{where}: a zero denominator must give a null value (undefined ratio)"
                        )
                elif _null(value) or abs(float(value) - float(num) / float(den)) > 1e-9:
                    problems.append(
                        f"{where}: value differs from numerator / denominator"
                    )
            elif not _null(value):
                problems.append(
                    f"{where}: value present without a numerator and denominator"
                )
        if not _sorted_string_list(row["quality_flags"]):
            problems.append(
                f"{where}: quality_flags must be a sorted JSON list of strings"
            )
        if not _string_map(row["source_versions"]):
            problems.append(f"{where}: source_versions must be a JSON map of strings")
    return problems


def defense_mirror_problems(frame: pd.DataFrame) -> list[str]:
    """Defense rows must mirror the opponent's offensive measurement and provenance."""
    keep = [
        "numerator",
        "denominator",
        "value",
        "eligible_count",
        "observed_count",
        "coverage_status",
        "missing_reason",
        "quality_flags",
        "timing_class",
        "source_versions",
    ]
    if frame.duplicated(["season", "game_id", "team", "role", "metric"]).any():
        return ["duplicate metric identity"]
    offense = frame[frame["role"] == "offense"].set_index(
        ["season", "game_id", "team", "metric"]
    )
    problems = []
    for row in frame[frame["role"] == "defense"].to_dict("records"):
        key = (row["season"], row["game_id"], row["opponent"], row["metric"])
        if key not in offense.index:
            problems.append(f"{key}: defense row has no opponent offense row")
            continue
        mirror = offense.loc[key]
        for column in keep:
            a, b = row[column], mirror[column]
            if not (
                (_null(a) and _null(b)) or (not _null(a) and not _null(b) and a == b)
            ):
                problems.append(
                    f"{key}: defense {column} differs from the opponent's offense"
                )
                break
    return problems


def possessions_problems(frame: pd.DataFrame) -> list[str]:
    problems = []
    if frame.duplicated(["season", "game_id", "drive_number", "offense"]).any():
        problems.append("duplicate possession identity")
    for row in frame.to_dict("records"):
        expected = possession_id_for(
            row["season"], row["game_id"], row["drive_number"], row["offense"]
        )
        if row["possession_id"] != expected:
            problems.append(
                f"{row['game_id']}/{row['drive_number']}/{row['offense']}: possession_id is not the deterministic id"
            )
        if row["possession_eligible"] and row["period_class"] != "regulation":
            problems.append(
                f"{row['possession_id']}: an eligible possession must be regulation"
            )
        if row["possession_eligible"] and not _null(row["quality_reason"]):
            problems.append(
                f"{row['possession_id']}: an eligible possession cannot carry a quality_reason"
            )
        if (
            not _null(row["start_yards_to_goal"])
            and not 0 <= float(row["start_yards_to_goal"]) <= 100
        ):
            problems.append(
                f"{row['possession_id']}: start_yards_to_goal outside 0-100"
            )
        if _json(row["source_play_ids"]) is None:
            problems.append(f"{row['possession_id']}: source_play_ids is not JSON")
        if not _string_map(row["source_versions"]):
            problems.append(
                f"{row['possession_id']}: source_versions must be a JSON map of strings"
            )
    return problems


def scoring_ledger_problems(
    frame: pd.DataFrame, possessions: pd.DataFrame | None = None
) -> list[str]:
    problems = []
    if frame.duplicated(["season", "game_id", "team", "source_event_id"]).any():
        problems.append("duplicate scoring event identity")
    if (
        not frame["admission"]
        .isin(
            (
                "baseline_unchanged",
                "corroborated",
                "reverted_unverified",
                "reverted_contradicted",
            )
        )
        .all()
    ):
        problems.append("unknown or candidate admission in final scoring ledger")
    event_keys = {
        (r["season"], r["game_id"], r["team"], r["source_event_id"])
        for r in frame.to_dict("records")
    }
    possession_ids = (
        set(possessions["possession_id"]) if possessions is not None else None
    )
    possession_rows = {}
    if possessions is not None:
        if possessions.possession_id.duplicated().any():
            problems.append("duplicate possession reference identity")
        possession_rows = {
            r.possession_id: r for r in possessions.itertuples(index=False)
        }
    for row in frame.to_dict("records"):
        where = f"{row['game_id']}/{row['team']}/{row['source_event_id']}"
        increment = row["score_increment"]
        if row["scoring_category"] == "unresolved":
            if not _null(increment):
                problems.append(
                    f"{where}: an unresolved marker must have a null score_increment, not a number"
                )
        else:
            if (
                _null(increment)
                or float(increment) < 0
                or float(increment) != int(increment)
            ):
                problems.append(
                    f"{where}: a resolved increment must be a nonnegative integer"
                )
            elif float(increment) > MAX_RESOLVED_INCREMENT:
                problems.append(
                    f"{where}: increment {increment} exceeds the eight-point limit"
                )
        ref = row["conversion_for_event_id"]
        if (
            not _null(ref)
            and (row["season"], row["game_id"], row["team"], ref) not in event_keys
        ):
            problems.append(
                f"{where}: conversion_for_event_id does not resolve within the same game and team"
            )
        possession = row["associated_possession_id"]
        if (
            possession_ids is not None
            and not _null(possession)
            and possession not in possession_ids
        ):
            problems.append(
                f"{where}: associated_possession_id does not resolve to a possession"
            )
        if (
            possessions is not None
            and not _null(possession)
            and possession in possession_ids
        ):
            linked = possession_rows[possession]
            if not (
                linked.season == row["season"]
                and linked.game_id == row["game_id"]
                and (
                    row["scoring_category"]
                    not in {
                        "eligible_regulation_offense",
                        "excluded_regulation_offense",
                    }
                    or linked.offense == row["team"]
                )
            ):
                problems.append(f"{where}: possession reference crosses game or team")
        if row["scoring_category"] == "eligible_regulation_offense" and _null(
            possession
        ):
            problems.append(
                f"{where}: an eligible offensive event needs an associated possession"
            )
        before, after, final = (
            row["envelope_before"],
            row["envelope_after"],
            row["certified_final"],
        )
        if not _null(before) and not _null(after) and float(before) > float(after):
            problems.append(f"{where}: envelope decreases")
        if not _null(after) and not _null(final) and float(after) > float(final):
            problems.append(f"{where}: envelope exceeds the certified final")
        evidence = _json(row["evidence_ids"])
        if not _sorted_string_list(row["evidence_ids"]):
            problems.append(
                f"{where}: evidence_ids must be a sorted JSON list of strings"
            )
        elif row["admission"] == "corroborated" and not evidence:
            problems.append(f"{where}: a corroborated event needs evidence_ids")
        if not _string_map(row["source_versions"]):
            problems.append(f"{where}: source_versions must be a JSON map of strings")
    return problems


def evidence_problems(frame: pd.DataFrame) -> list[str]:
    problems = []
    for row in frame.to_dict("records"):
        where = row["evidence_id"]
        digest = str(row["source_sha256"])
        if len(digest) != SHA256_HEX or any(
            c not in "0123456789abcdef" for c in digest
        ):
            problems.append(f"{where}: source_sha256 is not a lowercase SHA-256")
        if row["verdict"] == "supports" and not str(row["source_locator"]).strip():
            problems.append(f"{where}: a supporting citation needs a retained locator")
        if not str(row["rights_basis"]).strip() or not str(row["terms_uri"]).strip():
            problems.append(f"{where}: terms_uri and rights_basis are required")
    return problems


def require(problems: Iterable[str], label: str) -> None:
    items = list(problems)
    if items:
        raise GoldContractError(
            f"{label}: {len(items)} problem(s): " + "; ".join(items[:5])
        )
