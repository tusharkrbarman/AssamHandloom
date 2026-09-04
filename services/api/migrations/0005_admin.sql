CREATE TABLE IF NOT EXISTS owner (
  id text PRIMARY KEY CHECK (id = 'owner'),
  email text NOT NULL UNIQUE,
  password_hash text NOT NULL,
  password_salt text NOT NULL,
  password_iterations integer NOT NULL CHECK (password_iterations >= 100000),
  session_version integer NOT NULL DEFAULT 1 CHECK (session_version >= 1),
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS login_lockouts (
  key_hash text PRIMARY KEY,
  failed_count integer NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
  locked_until timestamptz,
  updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS order_refunds (
  id text PRIMARY KEY,
  order_id text NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  payment_id text NOT NULL REFERENCES order_payments(id),
  provider_refund_id text NOT NULL UNIQUE,
  amount_minor integer NOT NULL CHECK (amount_minor > 0),
  currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  status text NOT NULL CHECK (status IN ('processed', 'pending', 'failed')),
  created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS order_refunds_order_idx
  ON order_refunds (order_id, created_at);

CREATE OR REPLACE FUNCTION reject_inventory_adjustment_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'inventory_adjustments_immutable';
END;
$$;

DROP TRIGGER IF EXISTS inventory_adjustments_immutable_trigger
  ON inventory_adjustments;
CREATE TRIGGER inventory_adjustments_immutable_trigger
  BEFORE UPDATE OR DELETE ON inventory_adjustments
  FOR EACH ROW EXECUTE FUNCTION reject_inventory_adjustment_mutation();
