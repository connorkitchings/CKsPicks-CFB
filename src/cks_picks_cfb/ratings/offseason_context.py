"""Provenance and admission checks for football-only offseason context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from cks_picks_cfb.preseason_features import canonical_team

FAMILY_FEATURES: Mapping[str, tuple[str, ...]] = {
    "returning_production": (
        "return_total_ppa",
        "return_passing_ppa",
        "return_rushing_ppa",
        "return_receiving_ppa",
        "return_percent_ppa",
        "return_passing_usage",
        "return_rushing_usage",
    ),
    "transfer_portal": (
        "transfer_in_count",
        "transfer_out_count",
        "transfer_net_rating",
        "transfer_in_qb",
        "transfer_out_qb",
    ),
    "recruiting": ("recruiting_4yr", "recruiting_current", "recruiting_trend"),
    "coaching": ("coach_tenure", "coach_new"),
    "talent": ("talent",),
}
FORBIDDEN_TOKENS = ("spread", "line", "odds", "market", "bookmaker", "over_under")
REPORT_VERSION = "offseason_context_admission_v1"


class ContextAdmissionError(ValueError):
    """Raised when a source cannot be admitted."""


@dataclass(frozen=True)
class ContextAdmission:
    context: pd.DataFrame
    report: dict[str, object]


def _timestamps(values: pd.Series, label: str) -> pd.Series:
    result = pd.to_datetime(values, utc=True, errors="coerce")
    if result.isna().any():
        raise ContextAdmissionError(f"{label} contains invalid timestamps")
    return result


def _source(family: str, frame: pd.DataFrame, seasons: set[int]) -> pd.DataFrame:
    if family not in FAMILY_FEATURES:
        raise ContextAdmissionError(f"Unknown context family: {family}")
    required = {
        "season",
        "team",
        "effective_at",
        "retrieved_at",
        *FAMILY_FEATURES[family],
    }
    if missing := sorted(required - set(frame)):
        raise ContextAdmissionError(f"{family} is missing columns: {missing}")
    if forbidden := [
        c for c in frame if any(t in c.casefold() for t in FORBIDDEN_TOKENS)
    ]:
        raise ContextAdmissionError(
            f"{family} contains market-derived columns: {forbidden}"
        )
    result = frame.loc[
        :, ["season", "team", "effective_at", "retrieved_at", *FAMILY_FEATURES[family]]
    ].copy()
    result["season"] = pd.to_numeric(result["season"], errors="coerce")
    if (
        result["season"].isna().any()
        or not set(result["season"].astype(int)) <= seasons
    ):
        raise ContextAdmissionError(f"{family} contains forbidden seasons")
    result["season"] = result["season"].astype(int)
    result["team"] = result["team"].map(canonical_team)
    if result["team"].isna().any() or result.duplicated(["season", "team"]).any():
        raise ContextAdmissionError(
            f"{family} has invalid or duplicate team-season keys"
        )
    result["effective_at"] = _timestamps(
        result["effective_at"], f"{family}.effective_at"
    )
    result["retrieved_at"] = _timestamps(
        result["retrieved_at"], f"{family}.retrieved_at"
    )
    numeric = result.loc[:, list(FAMILY_FEATURES[family])].apply(
        pd.to_numeric, errors="coerce"
    )
    finite_rows = np.isfinite(numeric.to_numpy(dtype=float)).all(axis=1)
    # Source feeds may include teams outside the target FBS universe or partial
    # rows.  They are not imputed; coverage admission decides whether the
    # remaining complete team-season evidence meets the family threshold.
    result = result.loc[finite_rows].copy()
    result.loc[:, list(FAMILY_FEATURES[family])] = numeric.loc[finite_rows]
    return result


def admit_offseason_context(
    sources: Mapping[str, pd.DataFrame],
    team_universe: pd.DataFrame,
    *,
    permitted_seasons: Sequence[int],
    authentic_season: int = 2026,
    minimum_coverage: float = 0.90,
    source_refs: Mapping[str, Mapping[str, object]] | None = None,
    unavailable_reasons: Mapping[str, str] | None = None,
) -> ContextAdmission:
    """Classify each complete family as strict, reconstructed, or rejected."""
    permitted = {int(year) for year in permitted_seasons}
    if (
        2020 in permitted
        or authentic_season in permitted
        or not 0 < minimum_coverage <= 1
    ):
        raise ContextAdmissionError("Invalid season policy or coverage threshold")
    required = {"season", "team", "first_kickoff_utc"}
    if missing := sorted(required - set(team_universe)):
        raise ContextAdmissionError(f"Team universe is missing columns: {missing}")
    universe = team_universe.loc[:, ["season", "team", "first_kickoff_utc"]].copy()
    universe["season"] = pd.to_numeric(universe["season"], errors="coerce")
    universe["team"] = universe["team"].map(canonical_team)
    if (
        universe["season"].isna().any()
        or universe["team"].isna().any()
        or universe.duplicated(["season", "team"]).any()
    ):
        raise ContextAdmissionError("Team universe has invalid or duplicate keys")
    universe["season"] = universe["season"].astype(int)
    universe["first_kickoff_utc"] = _timestamps(
        universe["first_kickoff_utc"], "first_kickoff_utc"
    )
    universe = universe[universe["season"].isin([*permitted, authentic_season])]
    if universe.empty:
        raise ContextAdmissionError("Team universe has no permitted rows")

    unavailable = {
        str(name): str(reason) for name, reason in (unavailable_reasons or {}).items()
    }
    unknown = sorted(set(unavailable) - set(FAMILY_FEATURES))
    if unknown:
        raise ContextAdmissionError(f"Unknown unavailable context families: {unknown}")
    duplicates = sorted(set(unavailable) & set(sources))
    if duplicates:
        raise ContextAdmissionError(
            f"Context families cannot be both supplied and unavailable: {duplicates}"
        )
    if any(not reason.strip() for reason in unavailable.values()):
        raise ContextAdmissionError("Unavailable context families require a reason")

    admitted: list[pd.DataFrame] = []
    reports: dict[str, dict[str, object]] = {}
    for family in FAMILY_FEATURES:
        if family not in sources:
            reports[family] = {
                "status": "rejected",
                "reason": unavailable.get(family, "source not supplied"),
            }
            continue
        try:
            source = _source(family, sources[family], {*permitted, authentic_season})
        except ContextAdmissionError as exc:
            reports[family] = {"status": "rejected", "reason": str(exc)}
            continue
        joined = universe.merge(
            source, on=["season", "team"], how="left", validate="one_to_one"
        )
        features = list(FAMILY_FEATURES[family])
        season_report, complete, strict = {}, True, True
        for season, values in joined.groupby("season", observed=True):
            covered = values[features].notna().all(axis=1)
            evidence = covered & (values["effective_at"] < values["first_kickoff_utc"])
            if int(season) == authentic_season:
                evidence &= values["retrieved_at"] < values["first_kickoff_utc"]
            coverage = float(covered.mean())
            season_report[str(int(season))] = {
                "required_rows": len(values),
                "covered_rows": int(covered.sum()),
                "coverage_fraction": coverage,
                "pre_kickoff_evidence_rows": int(evidence.sum()),
            }
            complete &= coverage >= minimum_coverage
            strict &= bool(evidence.all())
        if not complete:
            reports[family] = {
                "status": "rejected",
                "reason": f"coverage below {minimum_coverage:.0%}",
                "seasons": season_report,
            }
            continue
        status = "strict" if strict else "reconstructed"
        reports[family] = {
            "status": status,
            "reason": None if strict else "pre-kickoff source evidence incomplete",
            "required_features": features,
            "seasons": season_report,
            "source_ref": dict((source_refs or {}).get(family, {})),
        }
        admitted.append(joined[["season", "team", *features]])
    if not admitted:
        raise ContextAdmissionError("No context family passed admission")
    context = admitted[0]
    for frame in admitted[1:]:
        context = context.merge(
            frame, on=["season", "team"], how="outer", validate="one_to_one"
        )
    families = [
        name for name, detail in reports.items() if detail["status"] != "rejected"
    ]
    track = (
        "strict"
        if all(reports[name]["status"] == "strict" for name in families)
        else "reconstructed"
    )
    context = context.copy()
    context["feature_track"] = track
    return ContextAdmission(
        context=context.sort_values(["season", "team"]).reset_index(drop=True),
        report={
            "schema_version": REPORT_VERSION,
            "state": "admitted",
            "feature_track": track,
            "activation_eligible": track == "strict",
            "minimum_coverage": minimum_coverage,
            "permitted_seasons": sorted(permitted),
            "authentic_season": authentic_season,
            "admitted_families": families,
            "families": reports,
        },
    )


def require_admitted_context(
    report: Mapping[str, object], *, allow_reconstructed: bool
) -> tuple[str, ...]:
    """Reject unadmitted or reconstructed context outside explicit research mode."""
    if (
        report.get("schema_version") != REPORT_VERSION
        or report.get("state") != "admitted"
    ):
        raise ContextAdmissionError("Context report is not an admitted v1 report")
    track = str(report.get("feature_track") or "")
    if track not in {"strict", "reconstructed"}:
        raise ContextAdmissionError("Context report has an invalid feature track")
    if track == "reconstructed" and not allow_reconstructed:
        raise ContextAdmissionError(
            "Reconstructed context requires explicit research-only opt-in"
        )
    families = tuple(str(value) for value in report.get("admitted_families") or ())
    if not families:
        raise ContextAdmissionError("Context report has no admitted families")
    return families
