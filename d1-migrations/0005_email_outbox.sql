PRAGMA foreign_keys = ON;

CREATE TABLE email_outbox (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('order_confirmation', 'order_paid')),
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  to_email TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'sent', 'failed')),
  attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  next_attempt_at TEXT NOT NULL,
  sent_at TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX email_outbox_order_kind_unique ON email_outbox(order_id, kind);
CREATE INDEX email_outbox_due_idx ON email_outbox(status, next_attempt_at);
