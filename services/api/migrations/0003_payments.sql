CREATE TABLE IF NOT EXISTS order_payments (
  id text PRIMARY KEY,
  order_id text NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  provider text NOT NULL DEFAULT 'razorpay' CHECK (provider = 'razorpay'),
  provider_order_id text NOT NULL UNIQUE,
  provider_payment_id text,
  amount_minor integer NOT NULL CHECK (amount_minor >= 0),
  currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  status text NOT NULL DEFAULT 'created'
    CHECK (status IN ('created', 'captured', 'failed')),
  failure_reason text,
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS order_payments_order_idx ON order_payments (order_id);
CREATE UNIQUE INDEX IF NOT EXISTS order_payments_payment_unique
  ON order_payments (provider_payment_id) WHERE provider_payment_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS inventory_adjustments (
  id text PRIMARY KEY,
  variant_id text NOT NULL REFERENCES variants(id),
  delta integer NOT NULL CHECK (delta <> 0),
  reason text NOT NULL,
  idempotency_key text NOT NULL UNIQUE,
  actor text NOT NULL,
  created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS inventory_adjustments_variant_idx
  ON inventory_adjustments (variant_id, created_at);
