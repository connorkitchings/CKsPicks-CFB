"""Restricted pipeline database identity guard."""

from __future__ import annotations

import pytest

from cks_picks_cfb.season.database_role import (
    V5ReleaseError,
    assert_v5_database_environment,
)


class RoleCursor:
    def __init__(self, session_user, current_user):
        self.session_user = session_user
        self.current_user = current_user
        self.queries = []

    def execute(self, sql, params=None):
        self.queries.append(sql)

    def fetchone(self):
        if "session_user" in self.queries[-1]:
            return (self.session_user, self.current_user)
        return None


@pytest.mark.parametrize(
    "environment,role",
    [
        ("production", "cks_prod_pipeline"),
        ("preview", "cks_preview_pipeline"),
    ],
)
def test_guard_accepts_the_exact_restricted_pipeline_roles(environment, role):
    assert_v5_database_environment(RoleCursor(role, role), environment) is None


@pytest.mark.parametrize(
    "session_user,current_user",
    [
        ("neondb_owner", "neondb_owner"),
        ("cks_prod_migrator", "cks_prod_migrator"),
        ("cks_prod_web", "cks_prod_web"),
        ("cks_preview_pipeline", "cks_preview_pipeline"),
        ("cks_prod_pipeline_admin", "cks_prod_pipeline_admin"),
        ("neondb_owner", "cks_prod_pipeline"),
        ("cks_prod_pipeline", "neondb_owner"),
    ],
)
def test_guard_rejects_non_pipeline_production_identities(session_user, current_user):
    with pytest.raises(V5ReleaseError, match="exact restricted pipeline role"):
        assert_v5_database_environment(
            RoleCursor(session_user, current_user), "production"
        )


@pytest.mark.parametrize(
    "session_user,current_user",
    [
        ("neondb_owner", "neondb_owner"),
        ("cks_preview_migrator", "cks_preview_migrator"),
        ("cks_prod_pipeline", "cks_prod_pipeline"),
        ("neondb_owner", "cks_preview_pipeline"),
    ],
)
def test_guard_rejects_non_pipeline_preview_identities(session_user, current_user):
    with pytest.raises(V5ReleaseError, match="exact restricted pipeline role"):
        assert_v5_database_environment(
            RoleCursor(session_user, current_user), "preview"
        )


def test_guard_rejects_an_unreadable_identity():
    class EmptyCursor(RoleCursor):
        def fetchone(self):
            return None

    with pytest.raises(V5ReleaseError, match="unreadable"):
        assert_v5_database_environment(
            EmptyCursor("cks_prod_pipeline", "cks_prod_pipeline"), "production"
        )


def test_guard_rejects_an_unknown_environment():
    with pytest.raises(V5ReleaseError, match="invalid V5 database environment"):
        assert_v5_database_environment(
            RoleCursor("cks_prod_pipeline", "cks_prod_pipeline"), "staging"
        )
