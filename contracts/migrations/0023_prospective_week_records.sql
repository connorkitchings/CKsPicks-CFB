-- Designate the authentic pre-kickoff V5 freeze retained as prospective evidence.
CREATE TABLE IF NOT EXISTS public.prospective_week_records (
    season INTEGER NOT NULL CHECK (season = 2026),
    week INTEGER NOT NULL CHECK (week >= 5),
    run_id TEXT NOT NULL UNIQUE
        REFERENCES public.prediction_runs(run_id) ON DELETE RESTRICT,
    freeze_receipt_uri TEXT NOT NULL CHECK (length(trim(freeze_receipt_uri)) > 0),
    freeze_receipt_sha256 TEXT NOT NULL
        CHECK (freeze_receipt_sha256 ~ '^[0-9a-f]{64}$'),
    frozen_at TIMESTAMPTZ NOT NULL,
    first_kickoff_utc TIMESTAMPTZ NOT NULL,
    decision_ref TEXT NOT NULL CHECK (length(trim(decision_ref)) > 0),
    PRIMARY KEY (season, week),
    CHECK (frozen_at < first_kickoff_utc)
);

CREATE OR REPLACE FUNCTION public.validate_prospective_week_record()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    run_row public.prediction_runs%ROWTYPE;
    schedule_kickoff TIMESTAMPTZ;
    freeze_recorded BOOLEAN;
BEGIN
    SELECT * INTO run_row
      FROM public.prediction_runs
     WHERE run_id = NEW.run_id;
    IF NOT FOUND
       OR run_row.season <> NEW.season
       OR run_row.week <> NEW.week
       OR run_row.model_id NOT LIKE 'v5-%'
       OR run_row.state NOT IN ('frozen', 'scored')
       OR run_row.evidence_class <> 'live'
       OR run_row.frozen_at IS DISTINCT FROM NEW.frozen_at THEN
        RAISE EXCEPTION 'prospective record must reference an authentic same-slate frozen V5 run';
    END IF;

    SELECT MIN(g.start_date) INTO schedule_kickoff
      FROM public.predictions p
      JOIN public.games g ON g.game_id = p.game_id
     WHERE p.run_id = NEW.run_id;
    IF schedule_kickoff IS NULL
       OR NEW.first_kickoff_utc IS DISTINCT FROM schedule_kickoff
       OR NEW.frozen_at >= schedule_kickoff THEN
        RAISE EXCEPTION 'prospective record cutoff does not match the current earliest slate kickoff';
    END IF;

    SELECT EXISTS (
        SELECT 1 FROM ops.activation_history ah
         WHERE ah.run_id = NEW.run_id AND ah.action = 'freeze'
           AND ah.season = NEW.season AND ah.week = NEW.week
    ) INTO freeze_recorded;
    IF NOT freeze_recorded THEN
        RAISE EXCEPTION 'prospective record lacks retained freeze activation evidence';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'prospective records are append-only';
    ELSIF TG_OP = 'UPDATE' THEN
        IF NEW.season <> OLD.season OR NEW.week <> OLD.week
           OR NEW.first_kickoff_utc <> OLD.first_kickoff_utc
           OR clock_timestamp() >= LEAST(OLD.first_kickoff_utc, schedule_kickoff)
           OR NEW.run_id = OLD.run_id THEN
            RAISE EXCEPTION 'prospective replacement is only allowed for the same slate before its earliest kickoff';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS prospective_week_records_validate ON public.prospective_week_records;
CREATE TRIGGER prospective_week_records_validate
    BEFORE INSERT OR UPDATE ON public.prospective_week_records
    FOR EACH ROW EXECUTE FUNCTION public.validate_prospective_week_record();

CREATE OR REPLACE FUNCTION public.reject_prospective_week_record_delete()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'prospective records are append-only';
END;
$$;

DROP TRIGGER IF EXISTS prospective_week_records_no_delete ON public.prospective_week_records;
CREATE TRIGGER prospective_week_records_no_delete
    BEFORE DELETE ON public.prospective_week_records
    FOR EACH ROW EXECUTE FUNCTION public.reject_prospective_week_record_delete();

REVOKE ALL ON public.prospective_week_records FROM PUBLIC;
REVOKE ALL ON public.prospective_week_records FROM cks_pipeline;
REVOKE ALL ON public.prospective_week_records FROM cks_web;
GRANT SELECT, INSERT, UPDATE ON public.prospective_week_records TO cks_pipeline;
GRANT SELECT ON public.prospective_week_records TO cks_web;
