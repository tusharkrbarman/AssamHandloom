PRAGMA foreign_keys = ON;

CREATE TABLE orders (
  id TEXT PRIMARY KEY,
  token TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'paid', 'fulfilled', 'cancelled', 'expired')),
  currency TEXT NOT NULL CHECK (
    length(currency) = 3 AND currency = upper(currency)
  ),
  subtotal_minor INTEGER NOT NULL CHECK (subtotal_minor >= 0),
  shipping_minor INTEGER NOT NULL DEFAULT 0 CHECK (shipping_minor >= 0),
  total_minor INTEGER NOT NULL CHECK (total_minor >= 0),
  ship_name TEXT NOT NULL,
  ship_phone TEXT NOT NULL,
  ship_address1 TEXT NOT NULL,
  ship_address2 TEXT,
  ship_city TEXT NOT NULL,
  ship_state TEXT NOT NULL,
  ship_postal_code TEXT NOT NULL,
  ship_country TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE order_items (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  variant_id TEXT NOT NULL REFERENCES variants(id),
  product_title TEXT NOT NULL,
  variant_title TEXT NOT NULL,
  sku TEXT NOT NULL,
  unit_price_minor INTEGER NOT NULL CHECK (unit_price_minor >= 0),
  currency TEXT NOT NULL CHECK (
    length(currency) = 3 AND currency = upper(currency)
  ),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  line_total_minor INTEGER NOT NULL CHECK (line_total_minor >= 0),
  created_at TEXT NOT NULL
);

CREATE TABLE inventory_reservations (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  variant_id TEXT NOT NULL REFERENCES variants(id),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  state TEXT NOT NULL DEFAULT 'active'
    CHECK (state IN ('active', 'consumed', 'released')),
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX one_active_reservation_per_order_variant
  ON inventory_reservations(order_id, variant_id) WHERE state = 'active';
CREATE INDEX reservations_availability_idx
  ON inventory_reservations(variant_id, state, expires_at);
CREATE INDEX order_items_order_idx ON order_items(order_id);
CREATE INDEX orders_status_created_idx ON orders(status, created_at);

CREATE TRIGGER inventory_reservations_within_stock
BEFORE INSERT ON inventory_reservations
WHEN NEW.quantity > (
  SELECT COALESCE(stock.quantity, 0)
  FROM inventory_items stock
  WHERE stock.variant_id = NEW.variant_id
) - COALESCE((
  SELECT SUM(other.quantity)
  FROM inventory_reservations other
  WHERE other.variant_id = NEW.variant_id
    AND other.state = 'active'
    AND other.expires_at > NEW.created_at
    AND NOT (other.order_id = NEW.order_id)
), 0)
BEGIN
  SELECT RAISE(ABORT, 'reservation_exceeds_available');
END;

CREATE TRIGGER inventory_reservations_identity_immutable
BEFORE UPDATE ON inventory_reservations
WHEN NEW.order_id <> OLD.order_id
  OR NEW.variant_id <> OLD.variant_id
  OR NEW.quantity <> OLD.quantity
BEGIN
  SELECT RAISE(ABORT, 'inventory_reservations_identity_immutable');
END;

CREATE TRIGGER inventory_reservations_protected_delete
BEFORE DELETE ON inventory_reservations
WHEN OLD.state = 'active'
BEGIN
  SELECT RAISE(ABORT, 'inventory_reservations_active_delete');
END;
