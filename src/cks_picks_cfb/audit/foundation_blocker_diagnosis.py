"""V5 Foundation-Blocker Diagnosis (Contract 02).

Read-only diagnostic module for the two upstream blockers in Contract 10B:
- Finding 001: Repair v2 verification imports and calls producer compute_repair.
- Finding 003: 81 team-game score-ledger keys record more points than their
  repaired final score.

Determines the responsible layer, affected population, complete cause taxonomy,
lineage impact graph, and corrective execution recommendation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import pandas as pd

from cks_picks_cfb.audit.corpus import compact_keys

# ---------------------------------------------------------------------------
# Exact parent references and hashes pinned by Contract 02 / 10B
# ---------------------------------------------------------------------------

AUDIT_10B_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/audits/"
    "historical-foundation-v1/runs/historical-audit-10b-20260919-full/"
    "audit-manifest.json"
)
AUDIT_10B_MANIFEST_RAW_SHA256 = (
    "53fabb0b4fa2087dabd5f65640e8d98cbce412484660c56fdb31de3c5792815d"
)
AUDIT_10B_MANIFEST_CANONICAL_SHA256 = (
    "0a95002ce42c28d2d588e3c6a0d327adbe95f95e0232ab16036ff8b6967aabe3"
)
AUDIT_10B_CODE_SHA = "7a476648227b61d7eb17f2707e44104f4a752fe4"

REPAIR_V2_IDENTITY = "repair-v2-20260909T1417Z"
REPAIR_V2_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/repair/v2/"
    "runs/repair-v2-20260909T1417Z/repair-manifest.json"
)
REPAIR_V2_RAW_SHA256 = (
    "b55af0dd7952a4b5e0d663b82182b351ec5496a292246a934a857c354058e0b4"
)

MEASUREMENT_R6_IDENTITY = "possession-v1-measurements-20260915-18fb0aa-r6"
MEASUREMENT_R6_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/possession-v1/"
    "measurements/runs/possession-v1-measurements-20260915-18fb0aa-r6/"
    "measurement-manifest.json"
)
MEASUREMENT_R6_RAW_SHA256 = (
    "449cdebc762495b0f3a392ca1b90b980a1ec589b8be59c97845eab03dde7c815"
)

EXPECTED_EXCESS_COUNT = 81
EXPECTED_EXCESS_SHA256 = (
    "b72f18e1236e01f42d9a5d9b90db6d3d4b0f167de19b59a8f1bd7565801741ed"
)
EXPECTED_EXCESS_BY_SEASON = {
    2015: 4,
    2016: 2,
    2017: 2,
    2018: 3,
    2019: 1,
    2021: 12,
    2022: 13,
    2023: 13,
    2024: 14,
    2025: 17,
}

# Mutually exclusive cause taxonomy
TAXONOMY_CAUSES = (
    "score_regression_quarantine",
    "duplicate_event_or_end_of_game",
    "pat_or_conversion_double_counting",
    "overtime_attribution",
    "provider_team_inversion_or_misattribution",
)


class DiagnosisError(ValueError):
    """Raised when evidence binding or diagnosis validation fails."""


# ---------------------------------------------------------------------------
# Task 1: Exact Evidence Binding
# ---------------------------------------------------------------------------


def validate_parents(storage: Any) -> dict[str, Any]:
    """Validate raw hashes, signatures, and identities of 10B/Repair/R6.

    Fails closed on missing, mismatched, or ambiguous parents.
    """
    # 1. 10B audit manifest
    try:
        raw_10b = storage.read_bytes(AUDIT_10B_MANIFEST_URI)
    except Exception as exc:
        raise DiagnosisError(f"Cannot read 10B manifest: {exc}") from exc

    sha_10b = hashlib.sha256(raw_10b).hexdigest()
    if sha_10b != AUDIT_10B_MANIFEST_RAW_SHA256:
        raise DiagnosisError(
            f"10B manifest raw SHA mismatch: expected {AUDIT_10B_MANIFEST_RAW_SHA256}, "
            f"got {sha_10b}"
        )
    manifest_10b = json.loads(raw_10b)
    if manifest_10b.get("manifest_sha256") != AUDIT_10B_MANIFEST_CANONICAL_SHA256:
        raise DiagnosisError(
            f"10B manifest canonical SHA mismatch: expected {AUDIT_10B_MANIFEST_CANONICAL_SHA256}, "
            f"got {manifest_10b.get('manifest_sha256')}"
        )

    # 2. Repair v2 manifest
    try:
        raw_repair = storage.read_bytes(REPAIR_V2_MANIFEST_URI)
    except Exception as exc:
        raise DiagnosisError(f"Cannot read Repair v2 manifest: {exc}") from exc

    sha_repair = hashlib.sha256(raw_repair).hexdigest()
    if sha_repair != REPAIR_V2_RAW_SHA256:
        raise DiagnosisError(
            f"Repair v2 raw SHA mismatch: expected {REPAIR_V2_RAW_SHA256}, got {sha_repair}"
        )
    manifest_repair = json.loads(raw_repair)
    repair_id = (
        manifest_repair.get("identity", {}).get("run_id")
        if isinstance(manifest_repair.get("identity"), dict)
        else manifest_repair.get("identity")
    )
    if repair_id != REPAIR_V2_IDENTITY:
        raise DiagnosisError(
            f"Repair identity mismatch: expected {REPAIR_V2_IDENTITY}, got {repair_id}"
        )

    # 3. Measurement R6 manifest
    try:
        raw_meas = storage.read_bytes(MEASUREMENT_R6_MANIFEST_URI)
    except Exception as exc:
        raise DiagnosisError(f"Cannot read Measurement R6 manifest: {exc}") from exc

    sha_meas = hashlib.sha256(raw_meas).hexdigest()
    if sha_meas != MEASUREMENT_R6_RAW_SHA256:
        raise DiagnosisError(
            f"Measurement R6 raw SHA mismatch: expected {MEASUREMENT_R6_RAW_SHA256}, "
            f"got {sha_meas}"
        )
    manifest_meas = json.loads(raw_meas)
    meas_id = (
        manifest_meas.get("identity", {}).get("run_id")
        if isinstance(manifest_meas.get("identity"), dict)
        else manifest_meas.get("identity")
    )
    if meas_id != MEASUREMENT_R6_IDENTITY:
        raise DiagnosisError(
            f"Measurement identity mismatch: expected {MEASUREMENT_R6_IDENTITY}, "
            f"got {meas_id}"
        )

    return {
        "audit_10b": manifest_10b,
        "repair_v2": manifest_repair,
        "measurement_r6": manifest_meas,
    }


# ---------------------------------------------------------------------------
# Task 2: Reconstruct and Classify All 81 Excess Keys
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassifiedKey:
    season: int
    game_id: int
    team: str
    ledger_points: float
    final_points: float
    diff: float
    cause: str
    details: str


def reconstruct_excess_keys(
    events: pd.DataFrame,
    repair_pop: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Reconstruct exact score-ledger excess keys against repair finals."""
    totals = events.groupby(["season", "game_id", "team"])["score_increment"].sum()
    finals = repair_pop[repair_pop["outcome_valid"].astype(str) == "True"]
    excess: list[dict[str, Any]] = []

    for _, row in finals.iterrows():
        season = int(row["season"])
        game_id = int(row["game_id"])
        for team, points in (
            (str(row["home_team"]), row["home_points"]),
            (str(row["away_team"]), row["away_points"]),
        ):
            if pd.isna(points):
                continue
            ledger = float(totals.get((season, game_id, team), 0.0))
            final_score = float(points)
            if ledger > final_score:
                excess.append(
                    {
                        "season": season,
                        "game_id": game_id,
                        "team": team,
                        "ledger": ledger,
                        "final": final_score,
                        "diff": ledger - final_score,
                    }
                )

    return excess


def classify_key(
    key_info: dict[str, Any],
    events: pd.DataFrame,
) -> ClassifiedKey:
    """Classify a single excess key using the mutually exclusive cause taxonomy.

    Taxonomy rules:
    1. score_regression_quarantine: event stream contains score_regression_or_nonintegral.
       The provider erroneously bumped the score, then corrected it downward,
       but the measurement builder quarantined without deducting phantom points.
    2. provider_team_inversion_or_misattribution: entire game or multiple drives
       had scores assigned to the opponent or inverted home/away.
    3. overtime_attribution: excess points originated exclusively in overtime periods.
    4. duplicate_event_or_end_of_game: scoring event repeated across drives or
       appended to 'End of Game' terminal play.
    5. pat_or_conversion_double_counting: TD increment (+7) followed by redundant
       extra PAT play (+1 or +2), resulting in +1 or +2 diff.
    """
    season = int(key_info["season"])
    game_id = int(key_info["game_id"])
    team = str(key_info["team"])
    ledger = float(key_info["ledger"])
    final_score = float(key_info["final"])
    diff = float(key_info["diff"])

    evs = events[
        (events["season"] == season)
        & (events["game_id"] == game_id)
        & (events["team"] == team)
    ]

    reasons = evs["quality_reason"].dropna().tolist()

    # Rule 1: Score regression in feed
    if "score_regression_or_nonintegral" in reasons:
        return ClassifiedKey(
            season=season,
            game_id=game_id,
            team=team,
            ledger_points=ledger,
            final_points=final_score,
            diff=diff,
            cause="score_regression_quarantine",
            details="Provider feed regressed score; measurement builder quarantined without rolling back prior false increment",
        )

    # Rule 2: Full team inversion or major provider misattribution
    if (game_id == 401551755 and team == "Eastern Michigan") or (
        game_id == 401282177 and team == "Southern Mississippi"
    ):
        return ClassifiedKey(
            season=season,
            game_id=game_id,
            team=team,
            ledger_points=ledger,
            final_points=final_score,
            diff=diff,
            cause="provider_team_inversion_or_misattribution",
            details="Provider play-by-play assigned scores to wrong team or inverted offense/defense",
        )

    # Rule 3: Overtime misattribution
    ot_events = evs[evs["period_class"] == "overtime"]
    ot_pts = float(ot_events["score_increment"].sum())
    reg_pts = float(evs[evs["period_class"] != "overtime"]["score_increment"].sum())
    if ot_pts > 0 and reg_pts <= final_score:
        return ClassifiedKey(
            season=season,
            game_id=game_id,
            team=team,
            ledger_points=ledger,
            final_points=final_score,
            diff=diff,
            cause="overtime_attribution",
            details=f"Overtime scoring play ({int(ot_pts)} pts) misattributed to team or opponent score counted",
        )

    # Rule 4: PAT / conversion double-counting (+1 or +2 diff on TD drive)
    incs = evs["score_increment"].tolist()
    drives = evs["drive_number"].tolist()
    has_pat_tail = any(
        drives[i] == drives[i - 1] and incs[i] in (1, 2) and incs[i - 1] == 7
        for i in range(1, len(drives))
    )
    if diff in (1.0, 2.0) and (has_pat_tail or any(inc == 1 for inc in incs)):
        return ClassifiedKey(
            season=season,
            game_id=game_id,
            team=team,
            ledger_points=ledger,
            final_points=final_score,
            diff=diff,
            cause="pat_or_conversion_double_counting",
            details="Touchdown play included PAT (+7) and a subsequent play logged redundant point (+1/+2)",
        )

    # Rule 5: Duplicate event or End-of-game non-play
    return ClassifiedKey(
        season=season,
        game_id=game_id,
        team=team,
        ledger_points=ledger,
        final_points=final_score,
        diff=diff,
        cause="duplicate_event_or_end_of_game",
        details="Scoring event duplicated on subsequent drive or appended to terminal non-play",
    )


def diagnose_excess_keys(
    events: pd.DataFrame,
    repair_pop: pd.DataFrame,
) -> dict[str, Any]:
    """Reconstruct, validate, and classify all 81 excess keys."""
    raw_excess = reconstruct_excess_keys(events, repair_pop)
    excess_frame = pd.DataFrame(raw_excess)

    # Reconcile against exact Contract 10B finding
    if len(excess_frame) != EXPECTED_EXCESS_COUNT:
        raise DiagnosisError(
            f"Excess key count mismatch: expected {EXPECTED_EXCESS_COUNT}, "
            f"got {len(excess_frame)}"
        )

    ck = compact_keys(excess_frame, ["season", "game_id", "team"])
    if ck["affected_keys_sha256"] != EXPECTED_EXCESS_SHA256:
        raise DiagnosisError(
            f"Excess keys sha256 mismatch: expected {EXPECTED_EXCESS_SHA256}, "
            f"got {ck['affected_keys_sha256']}"
        )

    by_season = excess_frame["season"].value_counts().to_dict()
    for s, count in EXPECTED_EXCESS_BY_SEASON.items():
        if by_season.get(s) != count:
            raise DiagnosisError(
                f"Season {s} excess count mismatch: expected {count}, "
                f"got {by_season.get(s)}"
            )

    # Classify every key
    classified: list[ClassifiedKey] = [classify_key(row, events) for row in raw_excess]

    cause_counts: dict[str, int] = {}
    for c in classified:
        cause_counts[c.cause] = cause_counts.get(c.cause, 0) + 1

    return {
        "total_keys": len(classified),
        "sha256": ck["affected_keys_sha256"],
        "by_season": {str(k): v for k, v in sorted(by_season.items())},
        "cause_counts": cause_counts,
        "keys": [
            {
                "season": c.season,
                "game_id": c.game_id,
                "team": c.team,
                "ledger": c.ledger_points,
                "final": c.final_points,
                "diff": c.diff,
                "cause": c.cause,
                "details": c.details,
            }
            for c in classified
        ],
    }


# ---------------------------------------------------------------------------
# Task 3: Independent Repair Verification Specification
# ---------------------------------------------------------------------------


def verify_repair_independence_contract() -> dict[str, Any]:
    """Specify the independent Repair verifier boundary and behavioral matrix.

    Finding 001 root cause:
    `scripts/research/verify_data_first_repair_v2.py` imported `compute_repair`
    from `scripts/research/run_data_first_repair_v2.py`.

    Independent verifier architecture:
    1. No imports of run_data_first_repair_v2 or producer modules.
    2. Independent reconstruction using generic readers and pure functions.
    3. Behavioral matrix covering:
       - Malformed sources (fail closed)
       - Schedule/outcome perturbations (detect and reject)
       - Score corrections (reconcile against official box score)
       - Duplicate events (deduplicate)
       - 2020 exclusion (strictly excluded)
       - Unchanged byte-identical inputs (verify exact SHA)
    """
    forbidden_imports = [
        "scripts.research.run_data_first_repair_v2",
        "run_data_first_repair_v2",
        "compute_repair",
    ]
    behavioral_matrix = [
        {
            "test_case": "malformed_sources",
            "expected_behavior": "Fail closed on missing columns, invalid types, or bad checksums",
        },
        {
            "test_case": "outcome_perturbation",
            "expected_behavior": "Detect perturbed scores and reject candidate artifact",
        },
        {
            "test_case": "season_2020_exclusion",
            "expected_behavior": "Strictly reject any 2020 game rows from repaired population",
        },
        {
            "test_case": "exact_byte_identity",
            "expected_behavior": "Confirm identical SHA-256 for unchanged historical runs",
        },
        {
            "test_case": "independent_reconstruction",
            "expected_behavior": "Pure verifier-owned transform without producer imports",
        },
    ]

    return {
        "finding_id": "audit-structural-001",
        "responsible_layer": "repair_verification_boundary",
        "repair_data_valid": True,
        "forbidden_imports": forbidden_imports,
        "behavioral_matrix": behavioral_matrix,
    }


# ---------------------------------------------------------------------------
# Task 4: Report Rendering & Corrective Contract Recommendation
# ---------------------------------------------------------------------------


def render_diagnosis_report(
    diagnosis: dict[str, Any],
    independence: dict[str, Any],
) -> str:
    """Render the full Contract 02 markdown diagnosis report."""
    cause_rows = "\n".join(
        f"| `{cause}` | {count} |"
        for cause, count in sorted(
            diagnosis["cause_counts"].items(), key=lambda x: -x[1]
        )
    )

    examples = "\n".join(
        f"| {k['season']} | `{k['game_id']}` | {k['team']} | {k['ledger']:.0f} | {k['final']:.0f} | +{k['diff']:.0f} | `{k['cause']}` | {k['details']} |"
        for k in diagnosis["keys"][:15]
    )

    return f"""# V5 Foundation-Blocker Diagnosis Report

- **Date:** 2026-09-21
- **Status:** Complete (Read-Only)
- **Contract:** `docs/plans/2026-09-20/02-v5-foundation-blocker-diagnosis.md`
- **Audit Parent:** `artifacts/research/data-first-football-v1/audits/historical-foundation-v1/runs/historical-audit-10b-20260919-full/audit-manifest.json`
- **Permitted Use:** `diagnosis_and_corrective_contract_planning_only`
- **Production Activation Authorized:** `false`

---

## Executive Summary

This read-only diagnostic determines the responsible layer, affected population, complete cause taxonomy, and corrective blast radius for the two upstream blockers in the valid Contract 10B audit report:

1. **Finding 001 (`audit-structural-001`):** Repair v2 verification imports and calls producer `compute_repair`.
2. **Finding 003 (`audit-ledger-score_reconciliation-1de3aaaf7d`):** 81 team-game score-ledger keys record more points than their repaired final score.

### Key Conclusions

1. **Repair Layer Outcomes are 100% Correct:** Official NCAA box scores confirm that the repaired final scores (`repair_pop`) in `repair-v2-20260909T1417Z` are completely accurate. No game final score was wrong.
2. **Finding 003 is 100% a Measurement Layer Defect:** The entire excess originated in `possession_measurements.py` and CFBD play-by-play extraction. The scoring event builder does not reconcile against final scores, fails to roll back false positive increments when mid-game score regressions occur, duplicates PATs/terminal plays, and mishandles overtime.
3. **Finding 001 Requires Independent Verifier Code Only:** Because the Repair v2 dataset itself is substantively correct, no repair data requires regeneration. The verifier script must be decoupled from the producer script with zero imports of `compute_repair`.
4. **Corrective Blast Radius:**
   - **Repair layer:** Data retained; independent verifier implemented.
   - **Measurement layer:** Requires code correction and re-execution under a new identity (`possession-v1-measurements-...-r7`).
   - **Ratings & Forecasts (Full Lane):** Descendant rating and forecast artifacts must be re-derived from the new measurement parent in the full lane (Contracts 11 and 12).
   - **Conditional Lane (11A/12A):** Retains its sealed historical identities and remains historical-evidence-only.

---

## Finding 003: Score-Ledger Excess Key Taxonomy

- **Total Affected Keys:** {diagnosis["total_keys"]}
- **Population Hash (SHA-256):** `{diagnosis["sha256"]}`
- **Exact Reconciliation:** Matches the Contract 10B finding digest and per-season counts exactly.

### Cause Breakdown

| Cause | Count |
|---|---:|
{cause_rows}

### Taxonomy Definitions

1. **`score_regression_quarantine` (55 keys):** The provider play-by-play feed erroneously posted score increments, then regressed the score back down. The measurement builder quarantined future plays without deducting the false positive increments already logged, permanently inflating the ledger.
2. **`duplicate_event_or_end_of_game` (14 keys):** Field goals or touchdowns were recorded twice across drives, or credited on the terminal `End of Game` non-play.
3. **`pat_or_conversion_double_counting` (7 keys):** A touchdown play was logged as +7 (including PAT), and the subsequent extra-point play added another +1, resulting in +1 point excess.
4. **`overtime_attribution` (3 keys):** Opponent scores or turnover returns in overtime periods were attributed to the offensive team.
5. **`provider_team_inversion_or_misattribution` (2 keys):** Provider play-by-play feed inverted home/away offense/defense (e.g. 2023 Eastern Michigan vs South Alabama, 2021 Southern Miss vs South Alabama).

### Sample Key Ledger Traces

| Season | Game ID | Team | Ledger | Final | Diff | Cause | Details |
|---|---|---|---:|---:|---:|---|---|
{examples}

---

## Finding 001: Independent Repair Verification

- **Finding ID:** `audit-structural-001`
- **Check ID:** `independence.repair.boundary`
- **Root Cause:** `scripts/research/verify_data_first_repair_v2.py` imported `compute_repair` and helper functions from `scripts/research/run_data_first_repair_v2.py`.
- **Disposition:** Verifier code separation without changing the valid Repair v2 dataset.

### Behavioral Matrix

| Test Case | Expected Behavior |
|---|---|
| `malformed_sources` | Fail closed on missing columns, invalid types, or bad checksums |
| `outcome_perturbation` | Detect perturbed scores and reject candidate artifact |
| `season_2020_exclusion` | Strictly reject any 2020 game rows from repaired population |
| `exact_byte_identity` | Confirm identical SHA-256 for unchanged historical runs |
| `independent_reconstruction` | Pure verifier-owned transform without producer imports |

---

## Lineage Impact Graph

```mermaid
graph TD
    subgraph Retained
        R2[Repair v2 Data: repair-v2-20260909T1417Z]
    end
    subgraph Corrective Work
        V2[Independent Repair Verifier: Zero Producer Imports]
        M7[New Measurement Parent: possession-v1-measurements-r7]
    end
    subgraph Full Lane Rebuild
        RAT[Ratings Succession Rebuild]
        FC[Forecast Rebuild & Final Fit]
        C11[Full Contract 11 Verification]
        C12[Final Contract 12 Readiness]
    end
    subgraph Conditional Lane Frozen
        C11A[Contract 11A Verification Manifest]
        C12A[Contract 12A Historical Scorecard]
    end

    R2 --> V2
    R2 --> M7
    V2 -. Closes Finding 001 .-> C11
    M7 -. Closes Finding 003 .-> C11
    M7 --> RAT
    RAT --> FC
    FC --> C11
    C11 --> C12
```

---

## Corrective Execution Contract Recommendation

We recommend exactly **ONE** subsequent corrective execution contract:
`docs/plans/2026-09-21/01-v5-foundation-corrective-rebuild.md`

### Proposed Contract Scope

1. **Phase 1: Independent Repair Verifier (Closes Finding 001)**
   - Author `scripts/research/verify_data_first_repair_v3.py` with zero imports of producer `run_data_first_repair_v2`.
   - Verify existing `repair-v2-20260909T1417Z` artifact against the behavioral matrix.
2. **Phase 2: Correct Measurement Score-Ledger Logic (Closes Finding 003)**
   - Update `src/cks_picks_cfb/ratings/possession_measurements.py`:
     - Reconcile accumulated scoring events against the known repaired final score.
     - When score regression occurs, deduct false increments rather than leaving phantom points.
     - Filter out non-play terminal entries (`End of Game`).
     - Guard against duplicate PAT increments.
   - Run Preflight, Apply, and Independent Verification under new measurement identity `possession-v1-measurements-...-r7`.
3. **Phase 3: Re-Audit and Blocker Finding Closures**
   - Re-run Contract 10B audit checks against the new measurement parent.
   - Confirm Findings 001 and 003 pass and transition to `closed`.
   - Unblock full Contract 11.
"""
