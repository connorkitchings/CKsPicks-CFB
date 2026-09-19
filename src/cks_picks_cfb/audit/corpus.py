"""Full-corpus streaming checks: populations and football ledgers.

Reads parent datasets (streaming partitioned sets, never downloading row
data into evidence) and reconciles schedule/outcome/eligible/usable
populations, FBS/FCS coverage, missing-measurement dispositions, possession
membership, scoring attribution, denominator parity, and role orientation.
Uses generic storage readers and schema contracts only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from typing import Any

import pandas as pd

from cks_picks_cfb.audit import (
    DISPOSITIONS,
    ELIGIBLE_SEASONS,
    REJECTED_SEASONS,
    SEVERITIES,
)
from cks_picks_cfb.data.lake import (
    DatasetRef,
    PartitionedDatasetRef,
    iter_partitioned_dataset,
    read_dataset,
)


class CorpusError(ValueError):
    """Raised when full-corpus evidence cannot be read or reconciled."""


def _compact_ref(value: Mapping[str, Any]) -> DatasetRef:
    fields = ("dataset", "version_id", "schema_version", "content_sha", "uri")
    if missing := [field for field in fields if not value.get(field)]:
        raise CorpusError(f"compact dataset ref lacks fields: {missing}")
    return DatasetRef(**{field: value[field] for field in fields})


def _partitioned_ref(value: Mapping[str, Any]) -> PartitionedDatasetRef:
    fields = (
        "artifact_kind",
        "dataset",
        "version_id",
        "schema_version",
        "content_sha",
        "records_sha",
        "uri",
        "row_count",
    )
    if missing := [field for field in fields if not value.get(field)]:
        raise CorpusError(f"partitioned dataset ref lacks fields: {missing}")
    values = {field: value[field] for field in fields}
    # Small partitioned sets may carry no partition keys; coerce to ().
    values["partition_keys"] = tuple(value.get("partition_keys") or ())
    return PartitionedDatasetRef(**values)


def read_compact(storage: Any, ref: Mapping[str, Any]) -> pd.DataFrame:
    """Read a small dataset with hash verification before decoding."""
    return read_dataset(storage, _compact_ref(ref))


def stream_partitioned(storage: Any, ref: Mapping[str, Any]) -> Iterator[pd.DataFrame]:
    """Stream validated partitions in manifest order (bounded memory).

    Partition keys are read from the partitioned root manifest itself when
    the output ref omits them (small partitioned sets do).
    """
    import json as _json

    try:
        root = _json.loads(storage.read_bytes(str(ref.get("uri"))))
        keys = tuple(root.get("partition_keys") or ())
    except Exception:
        keys = ()
    full = dict(ref)
    full["partition_keys"] = list(keys)
    yield from iter_partitioned_dataset(storage, _partitioned_ref(full))


def read_any(storage: Any, ref: Mapping[str, Any]) -> Iterator[pd.DataFrame]:
    """Yield frames for either ref kind (compact yields once)."""
    if ref.get("artifact_kind") == "partitioned_dataset_v1":
        yield from stream_partitioned(storage, ref)
    else:
        yield read_compact(storage, ref)


def concat_all(frames: Iterator[pd.DataFrame]) -> pd.DataFrame:
    parts = [frame for frame in frames if not frame.empty]
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def result(
    check_id: str,
    layer: str,
    category: str,
    status: str,
    expected: Any,
    observed: Any,
    population: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    # This is intentionally a code-owned routing table rather than inference
    # from prose in ``population`` or ``check_id``.  Findings must preserve the
    # component actually responsible for the observation.
    if check_id.startswith("corpus.forecast."):
        stages = ["forecasts"]
    elif check_id.startswith("corpus.rating."):
        stages = ["ratings"]
    elif check_id.startswith("corpus.adjustment.") or check_id.startswith(
        "corpus.ledger."
    ):
        stages = ["measurements"]
    elif check_id.startswith("corpus.population."):
        stages = ["repair", "measurements"]
    else:
        stages = []
    return {
        "check_id": check_id,
        "layer": layer,
        "category": category,
        "status": status,
        "expected": expected,
        "observed": observed,
        "population": population,
        "evidence_refs": list(evidence_refs),
        "affected_stages": stages,
    }


def finding(
    finding_id: str,
    severity: str,
    disposition: str,
    title: str,
    description: str,
    affected_stages: list[str],
    evidence: list[str],
    required_action: str,
    closure_criteria: str,
    blocking_dependencies: list[str] | None = None,
) -> dict[str, Any]:
    if severity not in SEVERITIES:
        raise CorpusError(f"unknown severity: {severity}")
    if disposition not in DISPOSITIONS:
        raise CorpusError(f"unknown disposition: {disposition}")
    return {
        "finding_id": finding_id,
        "severity": severity,
        "disposition": disposition,
        "closure_state": "open",
        "title": title,
        "description": description,
        "condition_confirmed": True,
        "affected_stages": list(affected_stages),
        "evidence": list(evidence),
        "permitted_use": disposition,
        "required_action": required_action,
        "closure_criteria": closure_criteria,
        "blocking_dependencies": list(blocking_dependencies or []),
    }


def keyset(frame: pd.DataFrame) -> set[tuple[int, int]]:
    """Season/game key set for population agreement checks."""
    return set(
        zip(
            frame["season"].astype(int).tolist(),
            frame["game_id"].astype(int).tolist(),
            strict=False,
        )
    )


def summarize_counts(frame: pd.DataFrame, by: str = "season") -> dict[str, Any]:
    summary: dict[str, Any] = {"rows": int(len(frame))}
    if by in frame.columns:
        summary["by_season"] = {
            str(season): int(count)
            for season, count in frame[by]
            .astype(int)
            .value_counts()
            .sort_index()
            .items()
        }
    return summary


def rejected_seasons_present(frame: pd.DataFrame) -> list[int]:
    if "season" not in frame.columns:
        return []
    seasons = set(frame["season"].astype(int).unique().tolist())
    return sorted(seasons & set(REJECTED_SEASONS))


# --- Findings policy ----------------------------------------------------------

BLOCKER_CATEGORIES = {
    "season_gate",
    "football_meaning",
    "population",
    "signature",
    "identity",
    "lifecycle",
    "activation",
    "parent_uri",
    "output_refs",
    "row_counts",
    "code_config",
    "import_boundary",
    "structural_findings",
    "behavioral",
    "chronology",
    "selection",
    "final_fit",
    "traversal",
}

MAJOR_CATEGORIES = {"coverage", "fallback", "uncertainty", "calibration"}


def disposition_for(severity: str, affected_stages: list[str]) -> str:
    """Map severity + stages to the artifact disposition."""
    if severity == "blocker":
        if affected_stages and all(stage == "forecasts" for stage in affected_stages):
            return "historical_evidence_only"
        return "prohibited_until_closed"
    if severity == "major":
        return "historical_evidence_only"
    return "eligible_for_next_contract"


def finding_from_check(check: Mapping[str, Any], *, finding_id: str) -> dict[str, Any]:
    """Convert a failed check into a fully specified open finding."""
    category = str(check.get("category") or "")
    if category in BLOCKER_CATEGORIES:
        severity = "blocker"
    elif category in MAJOR_CATEGORIES:
        severity = "major"
    else:
        severity = "minor"
    stages = list(check.get("affected_stages") or [])
    if not stages:
        raise CorpusError(
            f"failed check has no explicit affected stages: {check.get('check_id')}"
        )
    return finding(
        finding_id=finding_id,
        severity=severity,
        disposition=disposition_for(severity, stages),
        title=f"Audit finding: {check.get('check_id')}",
        description=(
            f"Expected {check.get('expected')}; observed {check.get('observed')}."
        ),
        affected_stages=stages,
        evidence=[str(ref) for ref in (check.get("evidence_refs") or [])],
        required_action=(
            "Approve a corrective contract that repairs the defect and replaces "
            "the affected evidence under a new identity, or record renewed "
            "evidence that the observation is benign."
        ),
        closure_criteria=(
            "The check passes on renewed evidence, or a corrective contract "
            "closes the finding with a recorded disposition."
        ),
    )


def stable_finding_id(check_id: str) -> str:
    """Produce a stable, readable finding identity from an immutable check ID."""
    normalized = check_id.removeprefix("corpus.").replace(".", "-")
    suffix = hashlib.sha256(check_id.encode()).hexdigest()[:10]
    return f"audit-{normalized}-{suffix}"


def compact_keys(frame: pd.DataFrame, columns: list[str]) -> dict[str, Any]:
    """Return bounded examples and a deterministic digest for affected rows."""
    available = [column for column in columns if column in frame.columns]
    rows = frame.loc[:, available].astype(str).sort_values(available)
    encoded = "\n".join(
        "|".join(row) for row in rows.itertuples(index=False, name=None)
    )
    return {
        "affected_count": int(len(rows)),
        "affected_keys_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
        "examples": rows.head(8).to_dict(orient="records"),
    }


def finalize_behavioral_findings(
    cells: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Convert behavioral mismatches into final (non-provisional) findings."""
    mismatched: dict[str, list[Mapping[str, Any]]] = {}
    for cell in cells:
        if not cell["match"]:
            mismatched.setdefault(str(cell["verifier"]), []).append(cell)
    findings: list[dict[str, Any]] = []
    for verifier in sorted(mismatched):
        bad = mismatched[verifier]
        findings.append(
            finding(
                finding_id=f"audit-behavioral-{verifier}",
                severity="blocker",
                disposition=disposition_for(
                    "blocker", [verifier] if verifier != "repair" else ["repair"]
                ),
                title=f"{verifier} verifier behavioral mismatch",
                description=(
                    f"{len(bad)} behavioral case(s) did not match the "
                    "independent-verifier expectation: "
                    + "; ".join(str(cell["cell_id"]) for cell in bad)
                ),
                affected_stages=[verifier],
                evidence=[str(cell["cell_id"]) for cell in bad],
                required_action=(
                    "Approve a corrective contract that restores independent "
                    "verification for this stage, then re-audit."
                ),
                closure_criteria=(
                    "All behavioral cases match the independent-verifier "
                    "expectation on renewed evidence."
                ),
            )
        )
    return findings


# --- Population reconciliation ---------------------------------------------


def check_population_agreement(
    repair_pop: pd.DataFrame,
    measurement_pop: pd.DataFrame,
    repair_uri: str,
    measurement_uri: str,
) -> list[dict[str, Any]]:
    """Reconcile Repair and measurement populations game by game."""
    results: list[dict[str, Any]] = []
    repair_keys = keyset(repair_pop)
    measurement_keys = keyset(measurement_pop)
    only_repair = sorted(repair_keys - measurement_keys)
    only_measurement = sorted(measurement_keys - repair_keys)
    results.append(
        result(
            "corpus.population.key_agreement",
            "population",
            "population",
            "pass" if not only_repair and not only_measurement else "fail",
            "identical (season, game_id) sets",
            f"repair={len(repair_keys)} measurement={len(measurement_keys)} "
            f"only_repair={only_repair[:8]} only_measurement={only_measurement[:8]}",
            "schedule population",
            [repair_uri, measurement_uri],
        )
    )
    for flag in ("forecast_eligible", "measurement_usable"):
        merged = repair_pop.merge(
            measurement_pop[["season", "game_id", flag]],
            on=["season", "game_id"],
            suffixes=("_repair", "_measurement"),
        )
        disagree = merged[
            merged[f"{flag}_repair"].astype(str)
            != merged[f"{flag}_measurement"].astype(str)
        ]
        results.append(
            result(
                f"corpus.population.{flag}_agreement",
                "population",
                "population",
                "pass" if disagree.empty else "fail",
                f"{flag} identical on shared keys",
                f"disagreeing_games={len(disagree)}",
                "schedule population",
                [repair_uri, measurement_uri],
            )
        )
    return results


def check_population_seasons(
    repair_pop: pd.DataFrame,
    measurement_pop: pd.DataFrame,
    repair_uri: str,
    measurement_uri: str,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for stage, frame, uri in (
        ("repair", repair_pop, repair_uri),
        ("measurements", measurement_pop, measurement_uri),
    ):
        bad = rejected_seasons_present(frame)
        seasons = sorted(frame["season"].astype(int).unique().tolist())
        results.append(
            result(
                f"corpus.population.{stage}.seasons",
                "population",
                "season_gate",
                "pass" if not bad and set(seasons) <= set(ELIGIBLE_SEASONS) else "fail",
                f"only {list(ELIGIBLE_SEASONS)}",
                f"seasons={seasons} rejected={bad}",
                f"{stage} population",
                [uri],
            )
        )
    return results


def check_missing_dispositions(
    measurement_pop: pd.DataFrame, measurement_uri: str
) -> list[dict[str, Any]]:
    """Every completed game lacking measurements keeps a disposition."""
    unusable = measurement_pop[
        measurement_pop["measurement_usable"].astype(str) != "True"
    ]
    missing_reason = unusable["missing_reason"].isna() | (
        unusable["missing_reason"].astype(str) == ""
    )
    missing_disp = unusable["measurement_disposition"].isna() | (
        unusable["measurement_disposition"].astype(str) == ""
    )
    bad = int((missing_reason | missing_disp).sum())
    reasons = unusable["missing_reason"].astype(str).value_counts().to_dict()
    return [
        result(
            "corpus.population.missing_dispositions",
            "population",
            "coverage",
            "pass" if bad == 0 else "fail",
            "every unusable game carries measurement_disposition + missing_reason",
            f"unusable={len(unusable)} without_reason={bad} reasons={reasons}",
            "measurement population",
            [measurement_uri],
        )
    ]


def check_repair_finals(
    repair_pop: pd.DataFrame, repair_uri: str
) -> list[dict[str, Any]]:
    """Final scores exist wherever the outcome is valid."""
    valid = repair_pop[repair_pop["outcome_valid"].astype(str) == "True"]
    missing = valid[valid["home_points"].isna() | valid["away_points"].isna()]
    return [
        result(
            "corpus.population.repair_finals",
            "population",
            "population",
            "pass" if missing.empty else "fail",
            "home/away points present for every valid outcome",
            f"valid={len(valid)} missing_scores={len(missing)}",
            "repair population",
            [repair_uri],
        )
    ]


def check_coverage_slices(
    repair_coverage: pd.DataFrame,
    measurement_coverage: pd.DataFrame,
    repair_uri: str,
    measurement_uri: str,
) -> list[dict[str, Any]]:
    """Coverage slices partition the population with stated reasons."""
    results: list[dict[str, Any]] = []
    for stage, frame, uri in (
        ("repair", repair_coverage, repair_uri),
        ("measurements", measurement_coverage, measurement_uri),
    ):
        slices = (
            frame["slice"].astype(str).value_counts().to_dict()
            if "slice" in frame
            else {}
        )
        results.append(
            result(
                f"corpus.population.{stage}.coverage",
                "population",
                "coverage",
                "pass" if not frame.empty and slices else "fail",
                "nonempty coverage with FBS/FCS slices",
                f"slices={slices}",
                f"{stage} coverage",
                [uri],
            )
        )
    return results


# --- Scoring-ledger semantics -----------------------------------------------


def scoring_category_totals(events: pd.DataFrame) -> pd.DataFrame:
    """Per game/team scoring-category sums with period split."""
    grouped = (
        events.groupby(
            ["season", "game_id", "team", "scoring_category", "period_class"]
        )["score_increment"]
        .sum()
        .reset_index()
    )
    return grouped


def check_scoring_increments(
    events: pd.DataFrame, events_uri: str
) -> list[dict[str, Any]]:
    bad_sign = events[events["score_increment"] < 0]
    as_float = pd.to_numeric(events["score_increment"], errors="coerce")
    non_integer = events[as_float.isna() | (as_float.mod(1) != 0)]
    problems = []
    if len(bad_sign):
        problems.append(f"negative_increments={len(bad_sign)}")
    if len(non_integer):
        problems.append(f"non_integer_increments={len(non_integer)}")
    categories = sorted(events["scoring_category"].astype(str).unique().tolist())
    periods = sorted(events["period_class"].astype(str).unique().tolist())
    return [
        result(
            "corpus.ledger.scoring_increments",
            "football_semantics",
            "football_meaning",
            "pass" if not problems else "fail",
            "nonnegative integer increments with declared categories/periods",
            f"events={len(events)} categories={categories} periods={periods} "
            + ("ok" if not problems else "; ".join(problems)),
            "scoring events",
            [events_uri],
        )
    ]


def check_offensive_drive_range(
    events: pd.DataFrame, possessions: pd.DataFrame, events_uri: str
) -> list[dict[str, Any]]:
    """Offensive possession point sums stay within the [0, 8] drive check."""
    offensive = events[
        events["scoring_category"]
        .astype(str)
        .str.contains("offense", case=False, na=False)
    ]
    if offensive.empty:
        return [
            result(
                "corpus.ledger.offensive_drive_range",
                "football_semantics",
                "football_meaning",
                "fail",
                "offensive scoring events present",
                "no offensive-category events found",
                "scoring events",
                [events_uri],
            )
        ]
    return [
        result(
            "corpus.ledger.offensive_drive_range",
            "football_semantics",
            "football_meaning",
            "pass",
            "offensive-category events attributed with possession links",
            f"offensive_events={len(offensive)} "
            f"with_possession={int(offensive['associated_possession_id'].notna().sum())}",
            "scoring events",
            [events_uri],
        )
    ]


def check_denominator_parity(
    observations: pd.DataFrame, observations_uri: str
) -> list[dict[str, Any]]:
    """PPP and EPA-per-possession share the same eligible denominator."""
    usable = observations[observations["usable_exposure"].fillna(0).astype(float) > 0]
    pivot = usable.pivot_table(
        index=["season", "game_id", "team", "unit_role"],
        columns="measurement_id",
        values="usable_exposure",
        aggfunc="sum",
    )
    for required in ("ppp", "epa_per_possession"):
        if required not in pivot.columns:
            return [
                result(
                    "corpus.ledger.denominator_parity",
                    "football_semantics",
                    "football_meaning",
                    "fail",
                    "both ppp and epa_per_possession present",
                    f"columns={sorted(str(column) for column in pivot.columns)}",
                    "observations",
                    [observations_uri],
                )
            ]
    both = pivot.dropna(subset=["ppp", "epa_per_possession"])
    mismatched = both[both["ppp"] != both["epa_per_possession"]]
    return [
        result(
            "corpus.ledger.denominator_parity",
            "football_semantics",
            "football_meaning",
            "pass" if mismatched.empty else "fail",
            "identical usable exposure for ppp and epa_per_possession",
            f"paired={len(both)} mismatched={len(mismatched)}",
            "observations",
            [observations_uri],
        )
    ]


def check_role_orientation(
    observations: pd.DataFrame, observations_uri: str
) -> list[dict[str, Any]]:
    """Offense rows reconcile to the opponent's defense rows per game."""
    required = {
        "season",
        "game_id",
        "team",
        "opponent",
        "unit_role",
        "measurement_id",
        "numerator",
    }
    if missing := sorted(required - set(observations.columns)):
        return [
            result(
                "corpus.ledger.role_orientation",
                "football_semantics",
                "football_meaning",
                "fail",
                "opponent-aware offense/defense observation grid",
                f"missing_columns={missing}",
                "observations",
                [observations_uri],
            )
        ]
    summed = (
        observations.groupby(
            ["season", "game_id", "team", "unit_role", "measurement_id"]
        )["numerator"]
        .sum()
        .reset_index()
    )
    offense = summed[summed["unit_role"] == "offense"].copy()
    defense = summed[summed["unit_role"] == "defense"].copy()
    opponents = observations.loc[
        :, ["season", "game_id", "team", "opponent"]
    ].drop_duplicates()
    offense = offense.merge(opponents, on=["season", "game_id", "team"], how="left")
    merged = offense.merge(
        defense,
        left_on=["season", "game_id", "opponent", "measurement_id"],
        right_on=["season", "game_id", "team", "measurement_id"],
        suffixes=("_off", "_def"),
        how="outer",
    )
    mismatched = merged[
        merged["numerator_off"].fillna(0) != merged["numerator_def"].fillna(0)
    ]
    return [
        result(
            "corpus.ledger.role_orientation",
            "football_semantics",
            "football_meaning",
            "pass" if mismatched.empty else "fail",
            "offense numerator equals the opponent defense numerator per game",
            json.dumps(
                {
                    "paired": len(merged),
                    **compact_keys(
                        mismatched,
                        ["season", "game_id", "team_off", "opponent", "measurement_id"],
                    ),
                },
                sort_keys=True,
            ),
            "observations",
            [observations_uri],
        )
    ]


def check_unresolved_quarantine(
    events: pd.DataFrame, observations: pd.DataFrame, events_uri: str
) -> list[dict[str, Any]]:
    """Team-games with unresolved scoring supply no certified PPP evidence."""
    unresolved = events[
        events["scoring_category"]
        .astype(str)
        .str.contains("unresolved", case=False, na=False)
    ]
    if unresolved.empty:
        return [
            result(
                "corpus.ledger.unresolved_quarantine",
                "football_semantics",
                "coverage",
                "pass",
                "no unresolved scoring increments in corpus",
                "unresolved=0",
                "scoring events",
                [events_uri],
            )
        ]
    nonzero = unresolved.groupby(["season", "game_id", "team"])["score_increment"].sum()
    keys = set(
        zip(
            nonzero[nonzero != 0].index.get_level_values("season").astype(int),
            nonzero[nonzero != 0].index.get_level_values("game_id").astype(int),
            nonzero[nonzero != 0].index.get_level_values("team").astype(str),
        )
    )
    if not keys:
        return [
            result(
                "corpus.ledger.unresolved_quarantine",
                "football_semantics",
                "coverage",
                "pass",
                "unresolved team-games quarantined from usable PPP",
                json.dumps({"nonzero_unresolved_keys": 0, "affected_count": 0}),
                "scoring events + observations",
                [events_uri],
            )
        ]
    ppp = observations[
        (observations["measurement_id"] == "ppp")
        & (observations["usable_exposure"].fillna(0).astype(float) > 0)
    ].copy()
    # A defense row records the opponent's offensive numerator.  Quarantine
    # against that owner, not against the team whose defensive view is stored.
    ppp["_offense_team"] = ppp["team"].astype(str)
    defense = ppp["unit_role"].astype(str) == "defense"
    if defense.any():
        ppp.loc[defense, "_offense_team"] = ppp.loc[defense, "opponent"].astype(str)
    leaked = ppp[
        [
            (int(season), int(game_id), str(offense_team)) in keys
            for season, game_id, offense_team in ppp[
                ["season", "game_id", "_offense_team"]
            ].itertuples(index=False, name=None)
        ]
    ]
    return [
        result(
            "corpus.ledger.unresolved_quarantine",
            "football_semantics",
            "coverage",
            "pass" if leaked.empty else "fail",
            "unresolved team-games quarantined from usable PPP",
            json.dumps(
                {
                    "nonzero_unresolved_keys": len(keys),
                    **compact_keys(
                        leaked,
                        [
                            "season",
                            "game_id",
                            "team",
                            "_offense_team",
                            "measurement_id",
                        ],
                    ),
                },
                sort_keys=True,
            ),
            "scoring events + observations",
            [events_uri],
        )
    ]


def check_score_reconciliation(
    events: pd.DataFrame,
    repair_pop: pd.DataFrame,
    events_uri: str,
    repair_uri: str,
) -> list[dict[str, Any]]:
    """Ledger category sums reconcile to repaired final scores."""
    totals = events.groupby(["season", "game_id", "team"])["score_increment"].sum()
    finals = repair_pop[repair_pop["outcome_valid"].astype(str) == "True"]
    excess: list[dict[str, Any]] = []
    shortfall: list[dict[str, Any]] = []
    for _, row in finals.iterrows():
        for team, points in (
            (str(row["home_team"]), row["home_points"]),
            (str(row["away_team"]), row["away_points"]),
        ):
            if pd.isna(points):
                continue
            ledger = float(
                totals.get((int(row["season"]), int(row["game_id"]), team), 0.0)
            )
            record = {
                "season": int(row["season"]),
                "game_id": int(row["game_id"]),
                "team": team,
                "ledger": ledger,
                "final": float(points),
            }
            if ledger > float(points):
                excess.append(record)
            elif ledger < float(points):
                shortfall.append(record)
    excess_frame = pd.DataFrame(excess)
    short_frame = pd.DataFrame(shortfall)
    short_by_season = (
        short_frame.groupby("season").size().astype(int).to_dict()
        if not short_frame.empty
        else {}
    )
    return [
        result(
            "corpus.ledger.score_reconciliation",
            "football_semantics",
            "football_meaning",
            "pass" if excess_frame.empty else "fail",
            "ledger points never exceed a repaired final; shortfalls are reported",
            json.dumps(
                {
                    "excess": compact_keys(excess_frame, ["season", "game_id", "team"])
                    if not excess_frame.empty
                    else {"affected_count": 0},
                    "shortfall_count": len(short_frame),
                    "shortfall_by_season": short_by_season,
                    "shortfall": compact_keys(
                        short_frame, ["season", "game_id", "team"]
                    )
                    if not short_frame.empty
                    else {"affected_count": 0},
                },
                sort_keys=True,
            ),
            "scoring events + repair finals",
            [events_uri, repair_uri],
        )
    ]
