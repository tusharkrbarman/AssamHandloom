PRAGMA foreign_keys = ON;

CREATE TABLE order_payments (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  provider TEXT NOT NULL DEFAULT 'razorpay' CHECK (provider = 'razorpay'),
  provider_order_id TEXT NOT NULL UNIQUE,
  provider_payment_id TEXT,
  amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
  currency TEXT NOT NULL CHECK (
    length(currency) = 3 AND currency = upper(currency)
  ),
  status TEXT NOT NULL DEFAULT 'created'
    CHECK (status IN ('created', 'captured', 'failed')),
  failure_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX order_payments_order_idx ON order_payments(order_id);
CREATE UNIQUE INDEX order_payments_payment_unique
  ON order_payments(provider_payment_id) WHERE provider_payment_id IS NOT NULL;
