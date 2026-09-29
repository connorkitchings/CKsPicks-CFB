import pytest

from cks_picks_cfb.db.migrations import MigrationError, discover_migrations
from scripts.pipeline import migrate_db


def test_migrations_are_ordered_and_checksummed(tmp_path):
    (tmp_path / "0002_second.sql").write_text("SELECT 2;")
    (tmp_path / "0001_first.sql").write_text("SELECT 1;")
    migrations = discover_migrations(tmp_path)
    assert [migration.version for migration in migrations] == ["0001", "0002"]
    assert all(len(migration.checksum) == 64 for migration in migrations)


def test_invalid_migration_name_is_rejected(tmp_path):
    (tmp_path / "latest.sql").write_text("SELECT 1;")
    with pytest.raises(MigrationError, match="Invalid migration filename"):
        discover_migrations(tmp_path)


def test_migration_cli_requires_an_explicit_target(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://production.example/db")
    monkeypatch.setattr("sys.argv", ["migrate_db.py"])
    with pytest.raises(SystemExit, match="2"):
        migrate_db.main()


def test_migration_cli_uses_only_the_selected_environment(monkeypatch):
    calls = []
    monkeypatch.setenv("DATABASE_URL", "postgresql://production.example/db")
    monkeypatch.setenv("PREVIEW_DATABASE_URL", "postgresql://preview.example/db")
    monkeypatch.setattr(
        "sys.argv", ["migrate_db.py", "--database-env", "PREVIEW_DATABASE_URL"]
    )
    monkeypatch.setattr(
        migrate_db,
        "apply_migrations",
        lambda url, path: calls.append((url, path)) or [],
    )
    migrate_db.main()
    assert calls[0][0] == "postgresql://preview.example/db"
