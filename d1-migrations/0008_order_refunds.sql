PRAGMA foreign_keys = ON;

CREATE TABLE order_refunds (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  payment_id TEXT NOT NULL REFERENCES order_payments(id),
  provider_refund_id TEXT NOT NULL UNIQUE,
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  currency TEXT NOT NULL CHECK (
    length(currency) = 3 AND currency = upper(currency)
  ),
  status TEXT NOT NULL DEFAULT 'processed'
    CHECK (status IN ('processed', 'pending', 'failed')),
  created_at TEXT NOT NULL
);

CREATE INDEX order_refunds_order_idx ON order_refunds(order_id);
