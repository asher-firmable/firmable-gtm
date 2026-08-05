CREATE TABLE IF NOT EXISTS mailbox_rotation (
    email                   text primary key,
    region                  text,                                    -- US | SEA | ANZ | NULL
    vendor                  text,                                    -- InboxKit | ScaledMail | empty

    is_active               boolean not null default false,          -- currently assigned to at least one campaign
    pool                    text not null default 'not_sending',     -- sending | not_sending
    pool_since              timestamptz not null default now(),      -- when they entered the current pool

    warmup_rep              numeric,          -- SmartLead warmup reputation (0-100)
    at_reply_rate           numeric,          -- all-time reply rate (%)
    reply_14d_rate          numeric,          -- 14-day reply rate (%)
    bounce_rate             numeric,          -- all-time bounce rate (%)
    signals_passing         integer,          -- count of core signals passing (0-3)

    recommendation          text,             -- no_action | monitor | move_to_warmup | retire
    recommendation_reason   text,

    last_checked_at         timestamptz not null default now(),
    created_at              timestamptz not null default now(),

    CONSTRAINT mailbox_rotation_pool_check CHECK (pool IN ('sending', 'not_sending')),
    CONSTRAINT mailbox_rotation_rec_check CHECK (
        recommendation IS NULL OR
        recommendation IN ('no_action', 'monitor', 'move_to_warmup', 'retire')
    )
);

CREATE INDEX IF NOT EXISTS mailbox_rotation_recommendation_idx ON mailbox_rotation (recommendation);
CREATE INDEX IF NOT EXISTS mailbox_rotation_region_idx ON mailbox_rotation (region);
CREATE INDEX IF NOT EXISTS mailbox_rotation_pool_idx ON mailbox_rotation (pool, pool_since);

GRANT SELECT, INSERT, UPDATE ON public.mailbox_rotation TO service_role;
