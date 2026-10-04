-- Migration 0022: Grant SELECT on market_quotes to cks_web
--
-- Performance detail queries join market_quotes to display price provenance
-- on graded picks. Migration 0003 created market_quotes but did not grant
-- SELECT to cks_web.

GRANT SELECT ON market_quotes TO cks_web;
