-- Migration 009: add is_published / published_at to guest_review for moderation.
-- Nothing is public until an admin publishes the review.
-- Idempotent: safe to re-run on every startup. One DO block for asyncpg.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'guest_review' AND column_name = 'is_published'
    ) THEN
        ALTER TABLE guest_review ADD COLUMN is_published BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'guest_review' AND column_name = 'published_at'
    ) THEN
        ALTER TABLE guest_review ADD COLUMN published_at TIMESTAMPTZ NULL;
    END IF;
END
$$;
