-- Migration 006: guest_review table (one review per booking)
-- Created here, not by create_all, because SQL migrations run BEFORE create_all
-- on first deploy. Idempotent: safe to re-run on every startup.
CREATE TABLE IF NOT EXISTS guest_review (
    id SERIAL PRIMARY KEY,
    booking_id INTEGER NOT NULL REFERENCES booking(id),
    rating_expectations SMALLINT NOT NULL,
    rating_comfort SMALLINT NOT NULL,
    rating_cleanliness SMALLINT NOT NULL,
    rating_communication SMALLINT NOT NULL,
    rating_location SMALLINT NOT NULL,
    rating_recommendation SMALLINT NOT NULL,
    liked_most TEXT NOT NULL,
    improvement TEXT NOT NULL,
    public_review TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_guest_review_booking_id
    ON guest_review(booking_id);
