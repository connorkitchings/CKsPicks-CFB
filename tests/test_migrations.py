import pytest

from cks_picks_cfb.db.migrations import MigrationError, discover_migrations


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
