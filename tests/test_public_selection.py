"""Focused tests for explicit public week selection, including V4 fallback."""

import pytest

from cks_picks_cfb.ops import public_selection
from cks_picks_cfb.ops.public_selection import PublicSelectionError, select_week_run

V4_MODEL = "week0-2026-v4-strict-20260818-r2"
V5_MODEL = "v5-possession-ppp-rho060-exposure"
V5_BUNDLE = "b" * 64
SUCCESSOR_MODEL = "v5-intended-update-2026-v1"


def test_batch_failure_never_recomputes_stats(monkeypatch):
    calls = []

    def select(_cur, *, week, **_kwargs):
        calls.append(week)
        if week == 2:
            raise PublicSelectionError("injected second-run failure")
        return f"old-{week}"

    monkeypatch.setattr(public_selection, "select_week_run", select)
    cur = FakeCursor([])
    with pytest.raises(PublicSelectionError, match="injected"):
        public_selection.select_week_runs_batch(
            cur,
            season=2026,
            runs_by_week={2: "new-2", 1: "new-1"},
            reason="batch rehearsal",
            environment="preview",
        )
    assert calls == [1, 2]
    assert not any("system_stats" in sql for sql in cur.executed)


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
        if self.executed and "ops.v5_release_revocations" in self.executed[-1]:
            return None
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
            ("approval-1", V5_MODEL, V5_BUNDLE, 2026, 5),
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
    assert any("v5_model_bundle_approvals" in sql for sql in cur.executed)
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


def test_v5_selection_rejects_ambiguous_bundle_approval():
    cur = FakeCursor(
        [
            _candidate(
                model_id=V5_MODEL,
                evidence_class="replay",
                bundle_sha256=V5_BUNDLE,
                state="scored",
            ),
            (None, V5_MODEL, V5_BUNDLE, 2026, 5),
        ]
    )
    with pytest.raises(PublicSelectionError, match="approved model bundle"):
        select_week_run(
            cur,
            season=2026,
            week=0,
            run_id="ambiguous-v5",
            reason="rehearsal",
            environment="preview",
        )
    assert not any("INSERT INTO site_week_selections" in sql for sql in cur.executed)


def test_preview_successor_selection_requires_exact_preview_authorization(monkeypatch):
    import cks_picks_cfb.artifacts as artifacts_module
    import cks_picks_cfb.data.storage as storage_module
    from cks_picks_cfb.ops.v5_intended_update_release import IntendedUpdateReleaseError

    monkeypatch.setattr(storage_module, "get_storage", lambda **_: object())
    monkeypatch.setattr(
        artifacts_module,
        "read_json_artifact",
        lambda *_: {"artifact_sha256": "a" * 64, "run_id": "successor-w0"},
    )
    cur = FakeCursor(
        [
            _candidate(
                model_id=SUCCESSOR_MODEL,
                evidence_class="replay",
                bundle_sha256=V5_BUNDLE,
                state="scored",
            ),
            ("approval-1", SUCCESSOR_MODEL, V5_BUNDLE, 2026, 5),
            None,
        ]
    )
    with pytest.raises(IntendedUpdateReleaseError, match="authorization is absent"):
        select_week_run(
            cur,
            season=2026,
            week=0,
            run_id="successor-w0",
            reason="preview rehearsal",
            environment="preview",
        )
    assert not any("INSERT" in sql for sql in cur.executed)


def test_successor_authorization_is_scoped_to_the_requested_environment():
    from cks_picks_cfb.ops.v5_intended_update_release import (
        IntendedUpdateReleaseError,
        require_intended_update_release_record,
        validate_intended_update_release_record,
    )

    class AuthCursor:
        def __init__(self):
            self.params = None

        def execute(self, _sql, params):
            self.params = params

        def fetchone(self):
            return None

    cur = AuthCursor()
    with pytest.raises(IntendedUpdateReleaseError, match="authorization is absent"):
        require_intended_update_release_record(
            cur,
            manifest={"run_id": "successor-w0"},
            storage=object(),
            season=2026,
            week=0,
            environment="preview",
        )
    assert cur.params == ("preview", 2026, 0, "successor-w0")

    with pytest.raises(
        IntendedUpdateReleaseError, match="release does not match environment"
    ):
        validate_intended_update_release_record(
            {
                "authorization_id": "wrong-environment",
                "decision_ref": "test",
                "environment": "production",
            },
            manifest={"run_id": "successor-w0"},
            storage=object(),
            season=2026,
            week=0,
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


def test_production_replay_selection_requires_exact_authorization(monkeypatch):
    import cks_picks_cfb.artifacts as artifacts_module
    import cks_picks_cfb.data.storage as storage_module
    from cks_picks_cfb.ops.v5_release import V5ReleaseError

    artifact_sha = "a" * 64
    monkeypatch.setattr(storage_module, "get_storage", lambda **_: object())
    monkeypatch.setattr(
        artifacts_module,
        "read_json_artifact",
        lambda *_: {"artifact_sha256": artifact_sha},
    )
    cur = FakeCursor(
        [
            _candidate(
                model_id=V5_MODEL,
                evidence_class="replay",
                bundle_sha256=V5_BUNDLE,
                artifact_sha256=artifact_sha,
                state="published",
            ),
            ("approval-1", V5_MODEL, V5_BUNDLE, 2026, 5),
        ],
        identities=("cks_prod_pipeline", "cks_prod_pipeline"),
    )
    with pytest.raises(V5ReleaseError, match="replay release authorization is absent"):
        select_week_run(
            cur,
            season=2026,
            week=0,
            run_id="2026w0-v5",
            reason="replay rehearsal",
            environment="production",
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
