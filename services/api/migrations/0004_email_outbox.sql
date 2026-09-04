CREATE TABLE IF NOT EXISTS email_outbox (
  id text PRIMARY KEY,
  kind text NOT NULL CHECK (kind IN (
    'order_confirmation', 'order_paid', 'payment_failed',
    'order_shipped', 'order_cancelled', 'order_refunded'
  )),
  order_id text NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  to_email text NOT NULL,
  status text NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'sent', 'failed')),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  next_attempt_at timestamptz NOT NULL,
  sent_at timestamptz,
  last_error text,
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  UNIQUE (order_id, kind)
);

CREATE INDEX IF NOT EXISTS email_outbox_due_idx
  ON email_outbox (status, next_attempt_at);
