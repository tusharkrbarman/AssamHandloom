CREATE TABLE IF NOT EXISTS orders (
  id text PRIMARY KEY,
  token text NOT NULL UNIQUE,
  email text NOT NULL,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'paid', 'fulfilled', 'cancelled', 'expired')),
  currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  subtotal_minor integer NOT NULL CHECK (subtotal_minor >= 0),
  shipping_minor integer NOT NULL DEFAULT 0 CHECK (shipping_minor >= 0),
  total_minor integer NOT NULL CHECK (total_minor >= 0),
  ship_name text NOT NULL,
  ship_phone text NOT NULL,
  ship_address1 text NOT NULL,
  ship_address2 text,
  ship_city text NOT NULL,
  ship_state text NOT NULL,
  ship_postal_code text NOT NULL,
  ship_country text NOT NULL CHECK (ship_country = 'IN'),
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
  id text PRIMARY KEY,
  order_id text NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  variant_id text NOT NULL REFERENCES variants(id),
  product_title text NOT NULL,
  variant_title text NOT NULL,
  sku text NOT NULL,
  unit_price_minor integer NOT NULL CHECK (unit_price_minor >= 0),
  currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  quantity integer NOT NULL CHECK (quantity > 0),
  line_total_minor integer NOT NULL CHECK (line_total_minor >= 0),
  created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_reservations (
  id text PRIMARY KEY,
  order_id text NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  variant_id text NOT NULL REFERENCES variants(id),
  quantity integer NOT NULL CHECK (quantity > 0),
  state text NOT NULL DEFAULT 'active'
    CHECK (state IN ('active', 'consumed', 'released')),
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_reservation_per_order_variant
  ON inventory_reservations (order_id, variant_id) WHERE state = 'active';
CREATE INDEX IF NOT EXISTS reservations_availability_idx
  ON inventory_reservations (variant_id, state, expires_at);
CREATE INDEX IF NOT EXISTS order_items_order_idx ON order_items (order_id);
CREATE INDEX IF NOT EXISTS orders_status_created_idx ON orders (status, created_at);
