-- Revocation records are append-only and written only by the separate release
-- authorization identity. Pipeline and web roles receive read-only/no access.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cks_release_authorizer') THEN
        CREATE ROLE cks_release_authorizer NOLOGIN;
    ELSIF (SELECT rolcanlogin FROM pg_roles WHERE rolname = 'cks_release_authorizer') THEN
        RAISE EXCEPTION 'cks_release_authorizer must remain a NOLOGIN group role';
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS ops.v5_release_revocations (
    record_type TEXT NOT NULL
        CHECK (record_type IN ('bundle_approval', 'intended_update_authorization')),
    record_id TEXT NOT NULL CHECK (length(trim(record_id)) > 0),
    decision_ref TEXT NOT NULL CHECK (length(trim(decision_ref)) > 0),
    revoked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (record_type, record_id)
);

CREATE OR REPLACE FUNCTION ops.reject_v5_release_revocation_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'V5 release revocations are append-only';
END;
$$;

CREATE OR REPLACE FUNCTION ops.validate_v5_release_revocation()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, ops AS $$
DECLARE
    exists_record BOOLEAN;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        RAISE EXCEPTION 'V5 release revocations are append-only';
    END IF;

    IF NEW.record_type = 'bundle_approval' THEN
        SELECT EXISTS (SELECT 1 FROM public.v5_model_bundle_approvals
                        WHERE approval_id = NEW.record_id) INTO exists_record;
    ELSIF NEW.record_type = 'intended_update_authorization' THEN
        SELECT EXISTS (SELECT 1 FROM public.v5_intended_update_release_authorizations
                        WHERE authorization_id = NEW.record_id) INTO exists_record;
    ELSE
        exists_record := FALSE;
    END IF;
    IF NOT exists_record THEN
        RAISE EXCEPTION 'revocation references no matching V5 authorization record';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS v5_release_revocations_validate ON ops.v5_release_revocations;
CREATE TRIGGER v5_release_revocations_validate
    BEFORE INSERT ON ops.v5_release_revocations
    FOR EACH ROW EXECUTE FUNCTION ops.validate_v5_release_revocation();
DROP TRIGGER IF EXISTS v5_release_revocations_no_mutation ON ops.v5_release_revocations;
CREATE TRIGGER v5_release_revocations_no_mutation
    BEFORE UPDATE OR DELETE ON ops.v5_release_revocations
    FOR EACH ROW EXECUTE FUNCTION ops.reject_v5_release_revocation_mutation();

REVOKE ALL ON ops.v5_release_revocations FROM PUBLIC;
REVOKE ALL ON ops.v5_release_revocations FROM cks_pipeline;
REVOKE ALL ON ops.v5_release_revocations FROM cks_web;
REVOKE ALL ON ops.v5_release_revocations FROM cks_release_authorizer;
GRANT USAGE ON SCHEMA ops TO cks_pipeline, cks_release_authorizer;
GRANT SELECT ON ops.v5_release_revocations TO cks_pipeline, cks_release_authorizer;
GRANT INSERT ON ops.v5_release_revocations TO cks_release_authorizer;
REVOKE UPDATE, DELETE, TRUNCATE ON ops.v5_release_revocations
    FROM cks_release_authorizer, cks_pipeline, cks_web, PUBLIC;
