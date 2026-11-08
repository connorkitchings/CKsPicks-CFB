"""Independent, read-only arithmetic for auditing V5 rating generations."""

from __future__ import annotations

import json
import math
from collections import defaultdict

import numpy as np
import pandas as pd

ROLES = ("offense", "defense")
TOLERANCE = 1e-10


def _require(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = columns - set(frame.columns)
    if missing:
        raise ValueError(f"{label} lacks columns: {sorted(missing)}")


def _finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _compare(
    actual: list[dict],
    stored: pd.DataFrame | None,
    *,
    keys: list[str],
    fields: dict[str, str],
) -> dict:
    if stored is None:
        return {"status": "unavailable", "reason": "original artifact not supplied"}
    _require(stored, set(keys) | set(fields.values()), "stored artifact")
    expected = pd.DataFrame(actual)
    if expected.empty:
        expected = pd.DataFrame(columns=keys + list(fields))
    if stored.duplicated(keys).any() or expected.duplicated(keys).any():
        return {"status": "discrepancy", "reason": "duplicate keys"}
    merged = expected.merge(
        stored, on=keys, how="outer", indicator=True, suffixes=("_audit", "_stored")
    )
    differences = []
    for row in merged.to_dict("records"):
        key = {name: row[name] for name in keys}
        if row["_merge"] != "both":
            differences.append({**key, "reason": row["_merge"]})
            continue
        for field, stored_field in fields.items():
            a = row.get(field + "_audit", row.get(field))
            b = row.get(stored_field + "_stored", row.get(stored_field))
            if not _finite(a) or not _finite(b) or abs(float(a) - float(b)) > TOLERANCE:
                differences.append({**key, "field": field, "audit": a, "stored": b})
    checked_optional = []
    if "contributions" in expected and "evidence" in stored:
        checked_optional.append("evidence")
        for row in merged[merged._merge.eq("both")].to_dict("records"):
            key = {name: row[name] for name in keys}
            evidence = row["evidence"]
            if isinstance(evidence, str):
                try:
                    evidence = json.loads(evidence)
                except (TypeError, ValueError):
                    evidence = None
            if not isinstance(evidence, list):
                differences.append(
                    {**key, "field": "evidence", "reason": "invalid evidence"}
                )
                continue
            audit_items = row["contributions"]
            stored_ids = [x.get("game_id") for x in evidence if isinstance(x, dict)]
            expected_ids = [x["game_id"] for x in audit_items]
            if (
                len(stored_ids) != len(evidence)
                or len(set(stored_ids)) != len(stored_ids)
                or set(stored_ids) != set(expected_ids)
            ):
                differences.append(
                    {
                        **key,
                        "field": "evidence",
                        "reason": "duplicate or mismatched source games",
                    }
                )
                continue
            lookup = {x["game_id"]: x for x in evidence}
            for item in audit_items:
                original = lookup[item["game_id"]]
                for name in (
                    "exposure",
                    "raw_ppp",
                    "adjusted_ppp",
                    "adjusted_z",
                    "contribution",
                ):
                    a, b = item[name], original.get(name)
                    if not _finite(b) or abs(float(a) - float(b)) > TOLERANCE:
                        differences.append(
                            {
                                **key,
                                "game_id": item["game_id"],
                                "field": "evidence." + name,
                                "audit": a,
                                "stored": b,
                            }
                        )
                if original.get("source_week") != item["week"]:
                    differences.append(
                        {
                            **key,
                            "game_id": item["game_id"],
                            "field": "evidence.source_week",
                            "audit": item["week"],
                            "stored": original.get("source_week"),
                        }
                    )
                try:
                    available_matches = pd.Timestamp(
                        original.get("available_utc")
                    ) == pd.Timestamp(item["available_utc"])
                except (ValueError, TypeError):
                    available_matches = False
                if not available_matches:
                    differences.append(
                        {
                            **key,
                            "game_id": item["game_id"],
                            "field": "evidence.available_utc",
                        }
                    )
                expected_reason = (
                    None
                    if item["context_status"] == "complete"
                    else item["context_status"]
                )
                if original.get("missing_context_reason") != expected_reason:
                    differences.append(
                        {
                            **key,
                            "game_id": item["game_id"],
                            "field": "evidence.missing_context_reason",
                        }
                    )
    for column in ("k", "evidence_weight", "completed_games"):
        if column not in stored or "contributions" not in expected:
            continue
        checked_optional.append(column)
        for row in merged[merged._merge.eq("both")].to_dict("records"):
            expected_value = {
                "k": None if row.get("snapshot_class") == "preseason" else 8.0,
                "evidence_weight": 1 - row["prior_weight_audit"],
                "completed_games": len(row["contributions"]),
            }[column]
            found = row[column]
            mismatch = (
                not pd.isna(found)
                if expected_value is None
                else not _finite(found)
                or abs(float(found) - expected_value) > TOLERANCE
            )
            if mismatch:
                differences.append(
                    {
                        **{name: row[name] for name in keys},
                        "field": column,
                        "audit": expected_value,
                        "stored": found,
                    }
                )
    return {
        "status": "agreement" if not differences else "discrepancy",
        "differences": differences,
        "checked_optional": checked_optional,
        "evidence_status": (
            "checked" if "evidence" in checked_optional else "unavailable"
        )
        if "contributions" in expected
        else "not_applicable",
    }


def _artifact_metadata(
    check: dict,
    frame: pd.DataFrame | None,
    *,
    week: int,
    cutoff: pd.Timestamp,
    cutoff_column: str,
    expected_sources: dict[str, str | None],
) -> dict:
    if frame is None:
        return check
    checks = {}
    for column, expected in {
        "as_of_week": week,
        cutoff_column: cutoff,
        **expected_sources,
    }.items():
        if expected is None or column not in frame:
            checks[column] = "unavailable"
            continue
        differences = []
        for index, value in frame[column].items():
            if column == cutoff_column:
                try:
                    actual = pd.Timestamp(value)
                    valid = actual.tzinfo is not None and actual == cutoff
                except (TypeError, ValueError):
                    valid = False
            else:
                valid = pd.notna(value) and value == expected
            if not valid:
                differences.append(
                    {
                        "field": column,
                        "row": str(index),
                        "audit": str(expected),
                        "stored": str(value),
                    }
                )
        checks[column] = "discrepancy" if differences else "agreement"
        if differences:
            check.setdefault("differences", []).extend(differences)
            check["status"] = "discrepancy"
    check["metadata"] = checks
    return check


def _cohort_summary(rows: pd.DataFrame) -> dict:
    result = {
        "count": len(rows),
        "team_mean": float(rows.value.mean()) if len(rows) else None,
        "exposure_sum": None,
        "exposure_weighted_mean": None,
        "exposure_min": None,
        "exposure_median": None,
        "exposure_max": None,
        "valid_exposure_count": 0,
    }
    if "primary_exposure" not in rows:
        return result
    exposure = pd.to_numeric(rows.primary_exposure, errors="coerce")
    valid = exposure.gt(0) & np.isfinite(exposure)
    values = exposure[valid]
    result["valid_exposure_count"] = int(valid.sum())
    if len(values):
        result.update(
            exposure_sum=float(values.sum()),
            exposure_weighted_mean=float(
                (rows.loc[valid, "value"] * values).sum() / values.sum()
            ),
            exposure_min=float(values.min()),
            exposure_median=float(values.median()),
            exposure_max=float(values.max()),
        )
    return result


def audit_generation(
    observations: pd.DataFrame,
    priors: pd.DataFrame,
    terminal: pd.DataFrame,
    *,
    week: int,
    cutoff: object,
    components: pd.DataFrame | None = None,
    adjusted: pd.DataFrame | None = None,
    fbs_teams: set[str] | None = None,
    expected_rating_source: str | None = None,
    expected_measurement_source: str | None = None,
) -> dict:
    """Recompute a cutoff's graph and Bayesian ratings from original inputs.

    ``week`` is exclusive, and evidence is available six hours after kickoff.
    Comparisons expect generation-filtered original artifact frames.
    """
    _require(
        observations,
        {
            "season",
            "week",
            "game_id",
            "kickoff_utc",
            "team",
            "opponent",
            "measurement_id",
            "unit_role",
            "raw_value",
            "numerator",
            "denominator",
            "coverage_status",
        },
        "observations",
    )
    _require(
        priors,
        {"season", "team", "unit_role", "prior_mean", "prior_variance"},
        "priors",
    )
    _require(
        terminal,
        {"season", "measurement_id", "unit_role", "adjusted_value"},
        "terminal",
    )
    timestamp = pd.Timestamp(cutoff)
    if timestamp.tzinfo is None:
        raise ValueError("cutoff must be timezone-aware")
    timestamp = timestamp.tz_convert("UTC")
    source = observations[observations.measurement_id.eq("ppp")].copy()
    if source.duplicated(["season", "game_id", "team", "unit_role"]).any():
        raise ValueError("duplicate team-game-role observation")
    if not source.unit_role.isin(ROLES).all() or not priors.unit_role.isin(ROLES).all():
        raise ValueError("unknown role")
    if (
        source[
            [
                "season",
                "week",
                "game_id",
                "kickoff_utc",
                "team",
                "opponent",
                "unit_role",
            ]
        ]
        .isna()
        .any()
        .any()
    ):
        raise ValueError("missing observation key")
    if source.team.eq(source.opponent).any():
        raise ValueError("team equals opponent")
    source["available_utc"] = pd.to_datetime(
        source.kickoff_utc, utc=True, errors="raise"
    ) + pd.Timedelta(hours=6)
    source = source[source.week.lt(week) & source.available_utc.le(timestamp)].copy()
    for col in ("raw_value", "numerator", "denominator"):
        source[col] = pd.to_numeric(source[col], errors="coerce")
    usable = (
        source.coverage_status.eq("observed")
        & source.denominator.gt(0)
        & np.isfinite(source.denominator)
        & np.isfinite(source.raw_value)
        & np.isfinite(source.numerator)
    )
    exclusions = []
    for row in source[~usable].to_dict("records"):
        reasons = []
        if row["coverage_status"] != "observed":
            reasons.append("coverage_not_observed")
        if not _finite(row["denominator"]) or row["denominator"] <= 0:
            reasons.append("nonpositive_or_missing_denominator")
        if not _finite(row["raw_value"]):
            reasons.append("nonfinite_raw_value")
        if not _finite(row["numerator"]):
            reasons.append("nonfinite_numerator")
        exclusions.append(
            {
                k: row[k]
                for k in ("season", "week", "game_id", "team", "opponent", "unit_role")
            }
            | {"reasons": reasons, "coverage_status": row["coverage_status"]}
        )
    rows = source[usable].to_dict("records")
    sums, weights = defaultdict(float), defaultdict(float)
    for row in rows:
        key = (str(row["team"]), row["unit_role"])
        sums[key] += row["numerator"]
        weights[key] += row["denominator"]
    raw = {key: sums[key] / weights[key] for key in sums}
    estimates = raw.copy()
    passes = [
        {"pass": 0, "team": k[0], "role": k[1], "value": v, "exposure": weights[k]}
        for k, v in sorted(raw.items())
    ]
    edges = []
    for iteration in range(1, 5):
        centers = {
            role: sum(estimates[k] * weights[k] for k in estimates if k[1] == role)
            / sum(weights[k] for k in estimates if k[1] == role)
            for role in ROLES
            if any(k[1] == role for k in estimates)
        }
        delta, matched = defaultdict(float), defaultdict(float)
        for row in rows:
            key = (str(row["team"]), row["unit_role"])
            opposite = "defense" if key[1] == "offense" else "offense"
            estimate = estimates.get((str(row["opponent"]), opposite))
            center = centers.get(opposite)
            available = estimate is not None and center is not None
            if available:
                delta[key] += (estimate - center) * row["denominator"]
                matched[key] += row["denominator"]
            edges.append(
                {
                    "pass": iteration,
                    "game_id": int(row["game_id"]),
                    "week": int(row["week"]),
                    "team": key[0],
                    "role": key[1],
                    "opponent": str(row["opponent"]),
                    "raw_ppp": float(row["raw_value"]),
                    "available_utc": row["available_utc"].isoformat(),
                    "exposure": float(row["denominator"]),
                    "opposite_center": center,
                    "opponent_estimate": estimate,
                    "adjusted_ppp": float(row["raw_value"] - (estimate - center))
                    if available
                    else float(row["raw_value"]),
                    "context_status": "complete"
                    if available
                    else "missing_opponent_context_raw_ppp",
                }
            )
        estimates = {
            key: value - delta[key] / matched[key] if matched[key] else value
            for key, value in raw.items()
        }
        passes.extend(
            {
                "pass": iteration,
                "team": k[0],
                "role": k[1],
                "value": v,
                "exposure": weights[k],
                "matched_exposure": matched[k],
            }
            for k, v in sorted(estimates.items())
        )
    scales = {}
    for role in ROLES:
        subset = terminal[
            terminal.season.eq(2025)
            & terminal.measurement_id.eq("ppp")
            & terminal.unit_role.eq(role)
        ]
        vals = pd.to_numeric(subset.adjusted_value, errors="coerce").dropna()
        if not np.isfinite(vals).all():
            raise ValueError("nonfinite historical scale")
        scales[role] = {
            "center": float(vals.mean()) if len(vals) else 0.0,
            "spread": max(float(vals.std(ddof=0)), 0.3) if len(vals) else 1.0,
            "sign": -1 if role == "defense" else 1,
            "count": len(vals),
            "status": "available" if len(vals) else "fallback_missing_terminal",
        }
    scale_cohorts = {}
    role_values = {}
    for role in ROLES:
        subset = terminal[
            terminal.season.eq(2025)
            & terminal.measurement_id.eq("ppp")
            & terminal.unit_role.eq(role)
        ].copy()
        subset["value"] = pd.to_numeric(subset.adjusted_value, errors="coerce")
        subset = subset[subset.value.notna()]
        role_values[role] = subset
        entry = {
            "membership_basis": "passed_fbs_teams_2026_not_verified_2025"
            if fbs_teams is not None
            else "unavailable",
            "teams": sorted(subset.team.astype(str).tolist())
            if "team" in subset
            else None,
        }
        entry["full"] = _cohort_summary(subset)
        if "team" in subset and fbs_teams is not None:
            entry["membership_reference"] = (
                "2026 pinned team catalogue applied to 2025 terminal; 2025 membership unknown"
            )
            entry["fbs"] = _cohort_summary(subset[subset.team.isin(fbs_teams)])
            entry["non_fbs"] = _cohort_summary(subset[~subset.team.isin(fbs_teams)])
            entry["fbs_count"] = int(subset.team.isin(fbs_teams).sum())
            entry["non_fbs_count"] = int((~subset.team.isin(fbs_teams)).sum())
        if "primary_exposure" in subset:
            exposure = pd.to_numeric(subset.primary_exposure, errors="coerce")
            valid = exposure.gt(0) & np.isfinite(exposure)
            entry["exposure_weighted_center"] = (
                float(
                    (subset.loc[valid, "value"] * exposure[valid]).sum()
                    / exposure[valid].sum()
                )
                if valid.any()
                else None
            )
            entry["terminal_exposure"] = float(exposure[valid].sum())
        scale_cohorts[role] = entry
    if all("team" in role_values[r] for r in ROLES):
        common = set(role_values["offense"].team) & set(role_values["defense"].team)
        for role in ROLES:
            vals = role_values[role].loc[role_values[role].team.isin(common), "value"]
            scale_cohorts[role]["common_team_count"] = len(common)
            scale_cohorts[role]["common_team_center"] = (
                float(vals.mean()) if len(vals) else None
            )
    selected = priors[priors.season.eq(2026)]
    if selected.duplicated(["team", "unit_role"]).any():
        raise ValueError("duplicate prior")
    states = []
    last_edges = [edge for edge in edges if edge["pass"] == 4]
    for prior in selected.to_dict("records"):
        team, role = str(prior["team"]), prior["unit_role"]
        mean, variance = prior["prior_mean"], prior["prior_variance"]
        if not _finite(mean) or not _finite(variance) or variance <= 0:
            raise ValueError("invalid prior")
        items = [
            dict(edge)
            for edge in last_edges
            if edge["team"] == team and edge["role"] == role
        ]
        exposure = sum(item["exposure"] for item in items)
        posterior_variance = 1 / (1 / variance + exposure / 8)
        scale = scales[role]
        for item in items:
            item["adjusted_z"] = (
                scale["sign"]
                * (item["adjusted_ppp"] - scale["center"])
                / scale["spread"]
            )
            item["contribution"] = (
                posterior_variance * item["exposure"] * item["adjusted_z"] / 8
            )
        prior_contribution = posterior_variance * mean / variance
        predecessor = terminal[
            terminal.season.eq(2025)
            & terminal.measurement_id.eq("ppp")
            & terminal.unit_role.eq(role)
        ]
        prior_check = {
            "status": "unavailable",
            "reason": "terminal team or exposure unavailable",
            "terminal_exposure": None,
        }
        if "team" in predecessor and "primary_exposure" in predecessor:
            predecessor = predecessor[predecessor.team.astype(str).eq(team)]
            if len(predecessor) == 1:
                previous = predecessor.iloc[0]
                terminal_exposure = previous.primary_exposure
                value = previous.adjusted_value
                if (
                    _finite(value)
                    and _finite(terminal_exposure)
                    and terminal_exposure > 0
                ):
                    terminal_z = (
                        scale["sign"]
                        * (float(value) - scale["center"])
                        / scale["spread"]
                    )
                    expected_mean = 0.6 * terminal_z
                    expected_variance = 0.36 / (1 + float(terminal_exposure) / 8) + 0.64
                    prior_check = {
                        "status": "agreement"
                        if abs(mean - expected_mean) <= TOLERANCE
                        and abs(variance - expected_variance) <= TOLERANCE
                        else "discrepancy",
                        "source": "2025_terminal",
                        "terminal_value": float(value),
                        "terminal_exposure": float(terminal_exposure),
                        "terminal_z": terminal_z,
                        "expected_mean": expected_mean,
                        "expected_variance": expected_variance,
                        "mean_error": float(mean - expected_mean),
                        "variance_error": float(variance - expected_variance),
                    }
                else:
                    prior_check = {
                        "status": "agreement"
                        if abs(mean) <= TOLERANCE and abs(variance - 1) <= TOLERANCE
                        else "discrepancy",
                        "source": "neutral_invalid_predecessor",
                        "terminal_exposure": float(terminal_exposure)
                        if _finite(terminal_exposure)
                        else None,
                        "expected_mean": 0.0,
                        "expected_variance": 1.0,
                        "mean_error": float(mean),
                        "variance_error": float(variance - 1),
                    }
            elif len(predecessor) > 1:
                prior_check["reason"] = "duplicate terminal predecessor"
            else:
                prior_check["reason"] = (
                    "no unique terminal predecessor; neutral fallback unverified"
                )
        key = (team, role)
        weighted_adjusted = (
            sum(i["adjusted_ppp"] * i["exposure"] for i in items) / exposure
            if exposure
            else None
        )
        complete = all(i["context_status"] == "complete" for i in items)
        identity_status = (
            "no_evidence"
            if not items
            else "missing_context"
            if not complete
            else "agreement"
            if abs(weighted_adjusted - estimates[key]) <= TOLERANCE
            else "discrepancy"
        )
        states.append(
            {
                "team": team,
                "unit_role": role,
                "rating_mean": prior_contribution
                + sum(i["contribution"] for i in items),
                "rating_variance": posterior_variance,
                "prior_mean": mean,
                "prior_variance": variance,
                "prior_weight": posterior_variance / variance,
                "prior_contribution": prior_contribution,
                "prior_check": prior_check,
                "usable_exposure": exposure,
                "contributions": items,
                "adjusted_identity": {
                    "status": identity_status,
                    "game_weighted": weighted_adjusted,
                    "cumulative": estimates.get(key),
                },
            }
        )
    population = []
    for key in sorted(raw):
        games = [r for r in rows if r["team"] == key[0] and r["unit_role"] == key[1]]
        for cohort in ("full", "fbs_vs_fbs"):
            subset = (
                games
                if cohort == "full"
                else [
                    r
                    for r in games
                    if fbs_teams is not None
                    and r["team"] in fbs_teams
                    and r["opponent"] in fbs_teams
                ]
            )
            numerator = sum(r["numerator"] for r in subset)
            denominator = sum(r["denominator"] for r in subset)
            population.append(
                {
                    "team": key[0],
                    "role": key[1],
                    "cohort": cohort,
                    "status": "unavailable"
                    if cohort == "fbs_vs_fbs" and fbs_teams is None
                    else "available",
                    "games": len(subset),
                    "opponents": sorted(str(r["opponent"]) for r in subset),
                    "points": numerator,
                    "possessions": denominator,
                    "ppp": numerator / denominator if denominator else None,
                }
            )
    for item in population:
        peers = [
            p["ppp"]
            for p in population
            if p["role"] == item["role"]
            and p["cohort"] == item["cohort"]
            and p["ppp"] is not None
        ]
        item["cohort_size"] = len(peers)
        item["rank"] = (
            1
            + sum(
                v > item["ppp"] if item["role"] == "offense" else v < item["ppp"]
                for v in peers
            )
            if item["ppp"] is not None
            else None
        )
    adjusted_rows = [
        {
            "team": k[0],
            "role": k[1],
            "raw_value": raw[k],
            "adjusted_value": value,
            "opponent_adjustment": raw[k] - value,
            "primary_exposure": weights[k],
        }
        for k, value in estimates.items()
        if fbs_teams is None or k[0] in fbs_teams
    ]
    prior_counts = {
        status: sum(s["prior_check"]["status"] == status for s in states)
        for status in ("agreement", "discrepancy", "unavailable")
    }
    return {
        "scales": scales,
        "scale_cohorts": scale_cohorts,
        "prior_summary": prior_counts,
        "passes": passes,
        "edges": edges,
        "states": states,
        "exclusions": exclusions,
        "populations": population,
        "component_check": _artifact_metadata(
            _compare(
                states,
                components,
                keys=["team", "unit_role"],
                fields={
                    x: x
                    for x in (
                        "rating_mean",
                        "rating_variance",
                        "prior_mean",
                        "prior_variance",
                        "prior_weight",
                        "prior_contribution",
                        "usable_exposure",
                    )
                },
            ),
            components,
            week=week,
            cutoff=timestamp,
            cutoff_column="cutoff_utc",
            expected_sources={"source_manifest_sha256": expected_rating_source},
        ),
        "adjusted_check": _artifact_metadata(
            _compare(
                adjusted_rows,
                adjusted,
                keys=["team", "role"],
                fields={
                    x: x
                    for x in (
                        "raw_value",
                        "adjusted_value",
                        "opponent_adjustment",
                        "primary_exposure",
                    )
                },
            ),
            adjusted,
            week=week,
            cutoff=timestamp,
            cutoff_column="as_of_cutoff",
            expected_sources={
                "rating_manifest_sha256": expected_rating_source,
                "measurement_manifest_sha256": expected_measurement_source,
            },
        ),
    }


def audit_graph_sensitivity(
    observations: pd.DataFrame,
    priors: pd.DataFrame,
    terminal: pd.DataFrame,
    *,
    week: int,
    cutoff: object,
    sec_teams: set[str],
    focus_teams: tuple[str, ...] = ("Georgia", "Florida"),
) -> dict:
    """Remove remaining edges of partially quarantined SEC games diagnostically."""
    baseline = audit_generation(
        observations, priors, terminal, week=week, cutoff=cutoff
    )
    edges = [e for e in baseline["edges"] if e["pass"] == 4]
    excluded = baseline["exclusions"]
    partial = sorted(
        {
            int(e["game_id"])
            for e in excluded
            if e["team"] in sec_teams
            and e["opponent"] in sec_teams
            and any(x["game_id"] == e["game_id"] for x in edges)
        }
    )
    paths = []
    for game in partial:
        for edge in (e for e in edges if e["game_id"] == game):
            # Influence flows from an opponent role to the opposing team role.
            start = (edge["team"], edge["role"])
            for first in edges:
                opposite = "defense" if first["role"] == "offense" else "offense"
                if (first["opponent"], opposite) != start:
                    continue
                path = [edge, first]
                if first["team"] in focus_teams:
                    paths.append(
                        {"quarantined_game_id": game, "hops": 1, "edges": path}
                    )
                for second in edges:
                    opposite2 = "defense" if second["role"] == "offense" else "offense"
                    if (second["opponent"], opposite2) == (
                        first["team"],
                        first["role"],
                    ) and second["team"] in focus_teams:
                        paths.append(
                            {
                                "quarantined_game_id": game,
                                "hops": 2,
                                "edges": path + [second],
                            }
                        )

    def values(result: dict) -> dict:
        final = {
            (p["team"], p["role"]): p["value"]
            for p in result["passes"]
            if p["pass"] == 4
        }
        states = {
            (s["team"], s["unit_role"]): s["rating_mean"] for s in result["states"]
        }
        output = {}
        for role in ROLES:
            cohort = sorted(
                (v for (team, r), v in states.items() if r == role), reverse=True
            )
            for team in focus_teams:
                key = (team, role)
                rating = states.get(key)
                output[key] = {
                    "adjusted_ppp": final.get(key),
                    "rating": rating,
                    "rank": 1 + sum(v > rating for v in cohort)
                    if rating is not None
                    else None,
                }
        return output

    original = values(baseline)
    scenarios = []
    for games in [[game] for game in partial] + ([partial] if len(partial) > 1 else []):
        remaining = observations[~observations.game_id.isin(games)]
        altered = values(
            audit_generation(remaining, priors, terminal, week=week, cutoff=cutoff)
        )
        changes = []
        for key, before in original.items():
            after = altered[key]
            changes.append(
                {
                    "team": key[0],
                    "role": key[1],
                    "baseline": before,
                    "removed": after,
                    "delta": {
                        name: after[name] - before[name]
                        if after[name] is not None and before[name] is not None
                        else None
                        for name in before
                    },
                }
            )
        scenarios.append({"removed_game_ids": games, "changes": changes})
    return {"partial_game_ids": partial, "paths": paths, "scenarios": scenarios}


def audit_source_quarantine(
    observations: pd.DataFrame,
    events: pd.DataFrame,
    finals: pd.DataFrame,
    exceptions: dict[tuple[int, str], str],
    *,
    through_week: int = 8,
) -> dict:
    """Classify excluded scoring pairs and reconcile each affected game's scores.

    Finals are one row per game with ``game_id``, ``home_team``, ``away_team``,
    ``home_points`` and ``away_points``. Events use production scoring columns.
    """
    _require(
        observations,
        {
            "week",
            "game_id",
            "team",
            "opponent",
            "measurement_id",
            "unit_role",
            "coverage_status",
            "numerator",
            "denominator",
            "raw_value",
        },
        "observations",
    )
    _require(
        events,
        {"game_id", "team", "score_increment", "scoring_category", "unit_category"},
        "events",
    )
    _require(
        finals,
        {"game_id", "home_team", "away_team", "home_points", "away_points"},
        "finals",
    )
    source = observations[
        observations.measurement_id.eq("ppp") & observations.week.le(through_week)
    ].copy()
    if source.duplicated(["game_id", "team", "unit_role"]).any():
        raise ValueError("duplicate team-game-role observation")
    if finals.duplicated("game_id").any():
        raise ValueError("duplicate final game")
    if not source.unit_role.isin(ROLES).all():
        raise ValueError("unknown role")
    denominator = pd.to_numeric(source.denominator, errors="coerce")
    source["usable"] = (
        source.coverage_status.eq("observed")
        & denominator.gt(0)
        & np.isfinite(pd.to_numeric(source.raw_value, errors="coerce"))
        & np.isfinite(pd.to_numeric(source.numerator, errors="coerce"))
    )
    affected = sorted(int(x) for x in source.loc[~source.usable, "game_id"].unique())
    summaries = []
    for game_id in affected:
        rows = source[source.game_id.eq(game_id)]
        final = finals[finals.game_id.eq(game_id)]
        if final.empty:
            summaries.append(
                {"game_id": game_id, "status": "unavailable", "reason": "missing final"}
            )
            continue
        final = final.iloc[0]
        teams = [str(final.home_team), str(final.away_team)]
        statuses = []
        for team, opponent in (teams, teams[::-1]):
            for role in ROLES:
                item = rows[rows.team.eq(team) & rows.unit_role.eq(role)]
                if item.empty:
                    statuses.append(
                        {
                            "team": team,
                            "opponent": opponent,
                            "role": role,
                            "status": "missing_observation",
                        }
                    )
                else:
                    r = item.iloc[0]
                    statuses.append(
                        {
                            "team": team,
                            "opponent": str(r.opponent),
                            "role": role,
                            "status": "usable" if r.usable else "excluded",
                            "coverage_status": r.coverage_status,
                            "missing_reason": r.get("missing_reason"),
                            "quality_flags": r.get("quality_flags"),
                            "numerator": float(r.numerator)
                            if _finite(r.numerator)
                            else None,
                            "possessions": float(r.denominator)
                            if _finite(r.denominator)
                            else None,
                        }
                    )
        pairs = []
        for team, opponent in (teams, teams[::-1]):
            offense = next(
                x for x in statuses if x["team"] == team and x["role"] == "offense"
            )
            defense = next(
                x for x in statuses if x["team"] == opponent and x["role"] == "defense"
            )
            pair_status = (
                "unavailable"
                if "missing_observation" in (offense["status"], defense["status"])
                else "agreement"
                if offense["status"] == defense["status"]
                else "discrepancy"
            )
            pairs.append(
                {
                    "scoring_team": team,
                    "opponent": opponent,
                    "offense_status": offense["status"],
                    "opponent_defense_status": defense["status"],
                    "pair_integrity": pair_status,
                }
            )
        scores = []
        for team, score_column in (
            (teams[0], "home_points"),
            (teams[1], "away_points"),
        ):
            ledger = events[events.game_id.eq(game_id) & events.team.eq(team)].copy()
            ledger["score_increment"] = pd.to_numeric(
                ledger.score_increment, errors="coerce"
            )
            if ledger.score_increment.isna().any():
                total = None
            else:
                total = float(ledger.score_increment.sum())
            score = float(final[score_column]) if _finite(final[score_column]) else None
            mismatch = (
                total != score if total is not None and score is not None else None
            )
            reason = exceptions.get((game_id, team))
            category = [
                {
                    "scoring_category": str(k[0]),
                    "unit_category": str(k[1]),
                    "count": int(len(g)),
                    "points": float(g.score_increment.sum()),
                }
                for k, g in ledger.groupby(
                    ["scoring_category", "unit_category"], dropna=False
                )
            ]
            scores.append(
                {
                    "team": team,
                    "event_total": total,
                    "final_score": score,
                    "status": "unavailable"
                    if mismatch is None
                    else "declared_mismatch"
                    if mismatch and reason is not None
                    else "undeclared_mismatch"
                    if mismatch
                    else "unused_exception"
                    if reason is not None
                    else "agreement",
                    "exception_reason": reason,
                    "categories": category,
                }
            )
        usable_count = sum(x["status"] == "usable" for x in statuses)
        missing_count = sum(x["status"] == "missing_observation" for x in statuses)
        classification = (
            "incomplete"
            if missing_count
            else "whole_game_quarantine"
            if usable_count == 0
            else "partial_quarantine"
        )
        summaries.append(
            {
                "game_id": game_id,
                "classification": classification,
                "roles": statuses,
                "scoring_pairs": pairs,
                "scores": scores,
            }
        )
    return {"excluded_rows": int((~source.usable).sum()), "affected_games": summaries}
