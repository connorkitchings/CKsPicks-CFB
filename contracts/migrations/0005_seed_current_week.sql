-- A schema-only Neon branch copies table definitions but not the singleton
-- control row created by contracts/schema.sql.  Seed its neutral state so a
-- freshly bootstrapped serving branch passes the operating-path checks.
INSERT INTO current_week (id, season, week)
VALUES (1, 0, 0)
ON CONFLICT (id) DO NOTHING;
