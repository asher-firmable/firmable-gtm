ALTER TABLE mailbox_rotation ADD COLUMN IF NOT EXISTS rotation_due boolean NOT NULL DEFAULT false;
ALTER TABLE mailbox_rotation ADD COLUMN IF NOT EXISTS days_in_pool integer;

CREATE INDEX IF NOT EXISTS mailbox_rotation_rotation_due_idx ON mailbox_rotation (rotation_due);
