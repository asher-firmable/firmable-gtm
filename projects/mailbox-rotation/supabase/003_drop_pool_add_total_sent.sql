-- Simplification: pool/pool_since/rotation_due/days_in_pool are no longer tracked.
-- is_active already captures "currently in a campaign right now" on its own, and
-- total_sent replaces them with a plain all-time send count per mailbox.
ALTER TABLE mailbox_rotation
    DROP COLUMN IF EXISTS pool,
    DROP COLUMN IF EXISTS pool_since,
    DROP COLUMN IF EXISTS rotation_due,
    DROP COLUMN IF EXISTS days_in_pool,
    ADD COLUMN IF NOT EXISTS total_sent integer;
