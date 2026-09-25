"""Focused tests for explicit public week selection, including V4 fallback."""

import pytest

from cks_picks_cfb.ops.public_selection import PublicSelectionError, select_week_run

V4_MODEL = "week0-2026-v4-strict-20260818-r2"
V5_MODEL = "v5-possession-ppp-rho060-exposure"
V5_BUNDLE = "b" * 64


class FakeCursor:
    def __init__(self, results, identities=("cks_preview_pipeline",) * 2):
        self.results = list(results)
        self.identities = identities
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append(sql)

    def fetchone(self):
        if self.executed and "session_user" in self.executed[-1]:
            return self.identities
        return self.results.pop(0) if self.results else None


def _candidate(
    *,
    season=2026,
    week=0,
    state="frozen",
    expected=8,
    predicted=8,
    model_id=V4_MODEL,
    artifact_sha256="a" * 64,
    evidence_class="legacy",
    bundle_sha256=None,
):
    return (
        season,
        week,
        state,
        expected,
        predicted,
        model_id,
        artifact_sha256,
        evidence_class,
        bundle_sha256,
    )


def test_v4_fallback_selection_requires_the_explicit_flag():
    cur = FakeCursor([_candidate()])
    with pytest.raises(PublicSelectionError, match="requires V5"):
        select_week_run(
            cur, season=2026, week=0, run_id="2026w0-v4", reason="rollback rehearsal"
        )
    assert not any("INSERT" in sql for sql in cur.executed)


def test_v4_fallback_selection_writes_selection_history_and_pointer():
    cur = FakeCursor(
        [
            _candidate(),
            (8, 0),
            ("2026w0-v5",),
        ]
    )
    previous = select_week_run(
        cur,
        season=2026,
        week=0,
        run_id="2026w0-v4",
        reason="rollback rehearsal",
        allow_v4_fallback=True,
    )
    assert previous == "2026w0-v5"
    assert any("INSERT INTO site_week_selections" in sql for sql in cur.executed)
    assert any("site_week_selection_history" in sql for sql in cur.executed)
    assert any("UPDATE current_week" in sql for sql in cur.executed)


def test_v4_fallback_rejects_non_legacy_evidence_class():
    cur = FakeCursor([_candidate(evidence_class="pending")])
    with pytest.raises(PublicSelectionError, match="requires V5"):
        select_week_run(
            cur,
            season=2026,
            week=0,
            run_id="2026w0-v4",
            reason="rollback rehearsal",
            allow_v4_fallback=True,
        )


def test_incomplete_run_is_never_selectable():
    cur = FakeCursor([_candidate(predicted=7)])
    with pytest.raises(PublicSelectionError, match="incomplete or not published"):
        select_week_run(
            cur,
            season=2026,
            week=0,
            run_id="2026w0-v4",
            reason="rollback rehearsal",
            allow_v4_fallback=True,
        )


def test_run_from_another_week_is_rejected():
    cur = FakeCursor([_candidate(season=2025, week=0)])
    with pytest.raises(PublicSelectionError, match="another season or week"):
        select_week_run(
            cur, season=2026, week=0, run_id="2026w0-v4", reason="rollback rehearsal"
        )


def test_run_without_a_verified_artifact_is_rejected():
    cur = FakeCursor([_candidate(artifact_sha256=None)])
    with pytest.raises(PublicSelectionError, match="verified immutable artifact"):
        select_week_run(
            cur,
            season=2026,
            week=0,
            run_id="2026w0-v4",
            reason="rollback rehearsal",
            allow_v4_fallback=True,
        )


def test_empty_reason_is_rejected_before_any_query():
    cur = FakeCursor([])
    with pytest.raises(PublicSelectionError, match="reason is required"):
        select_week_run(cur, season=2026, week=0, run_id="2026w0-v4", reason="   ")
    assert cur.executed == []


def test_v5_selection_enforces_the_release_policy():
    cur = FakeCursor(
        [
            _candidate(
                model_id=V5_MODEL,
                evidence_class="replay",
                bundle_sha256=V5_BUNDLE,
                state="scored",
            ),
            (V5_MODEL, V5_BUNDLE, 2026, 5),
            (8, 0),
            None,
        ]
    )
    previous = select_week_run(
        cur,
        season=2026,
        week=0,
        run_id="2026w0-v5",
        reason="rehearsal",
        environment="preview",
    )
    assert previous is None
    assert any("v5_release_policy" in sql for sql in cur.executed)
    assert any("INSERT INTO site_week_selections" in sql for sql in cur.executed)


def test_v5_selection_rejects_an_unapproved_bundle():
    cur = FakeCursor(
        [
            _candidate(
                model_id=V5_MODEL, evidence_class="replay", bundle_sha256="c" * 64
            ),
            None,
        ]
    )
    with pytest.raises(PublicSelectionError, match="approved model bundle"):
        select_week_run(
            cur,
            season=2026,
            week=0,
            run_id="2026w0-v5",
            reason="rehearsal",
            environment="preview",
        )


@pytest.mark.parametrize(
    "identities",
    [
        ("neondb_owner", "neondb_owner"),
        ("cks_preview_migrator", "cks_preview_migrator"),
        ("cks_prod_web", "cks_prod_web"),
        ("cks_prod_pipeline", "cks_prod_pipeline"),
        ("cks_preview_pipeline_admin", "cks_preview_pipeline_admin"),
        ("neondb_owner", "cks_preview_pipeline"),
        ("cks_preview_pipeline", "neondb_owner"),
    ],
)
def test_v5_selection_rejects_non_pipeline_identities(identities):
    cur = FakeCursor(
        [
            _candidate(
                model_id=V5_MODEL, evidence_class="replay", bundle_sha256=V5_BUNDLE
            )
        ],
        identities=identities,
    )
    with pytest.raises(PublicSelectionError, match="exact restricted pipeline role"):
        select_week_run(
            cur,
            season=2026,
            week=0,
            run_id="2026w0-v5",
            reason="rehearsal",
            environment="preview",
        )
    assert not any("INSERT" in sql for sql in cur.executed)
    assert not any("UPDATE current_week" in sql for sql in cur.executed)


def test_reselecting_the_same_run_writes_nothing():
    cur = FakeCursor(
        [
            _candidate(),
            (8, 0),
            ("2026w0-v4",),
        ]
    )
    previous = select_week_run(
        cur,
        season=2026,
        week=0,
        run_id="2026w0-v4",
        reason="same selection again",
        allow_v4_fallback=True,
    )
    assert previous == "2026w0-v4"
    assert not any("INSERT" in sql for sql in cur.executed)
