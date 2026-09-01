CREATE TABLE IF NOT EXISTS products (
  id text PRIMARY KEY,
  slug text NOT NULL,
  title text NOT NULL,
  description text NOT NULL DEFAULT '',
  silk_type text NOT NULL,
  colour text,
  occasion text,
  publication_state text NOT NULL DEFAULT 'draft'
    CHECK (publication_state IN ('draft', 'published')),
  featured_rank integer NOT NULL DEFAULT 0,
  archived_at timestamptz,
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS products_slug_lower_idx ON products (lower(slug));
CREATE INDEX IF NOT EXISTS products_public_idx
  ON products (publication_state, archived_at, featured_rank);

CREATE TABLE IF NOT EXISTS variants (
  id text PRIMARY KEY,
  product_id text NOT NULL REFERENCES products(id),
  sku text NOT NULL,
  title text NOT NULL,
  price_minor integer NOT NULL CHECK (price_minor >= 0),
  currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  weight_grams integer CHECK (weight_grams IS NULL OR weight_grams > 0),
  publication_state text NOT NULL DEFAULT 'draft'
    CHECK (publication_state IN ('draft', 'published')),
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS variants_sku_lower_idx ON variants (lower(sku));
CREATE INDEX IF NOT EXISTS variants_product_public_idx
  ON variants (product_id, publication_state);

CREATE TABLE IF NOT EXISTS inventory_items (
  variant_id text PRIMARY KEY REFERENCES variants(id) ON DELETE CASCADE,
  quantity integer NOT NULL DEFAULT 0 CHECK (quantity >= 0),
  version integer NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS collections (
  id text PRIMARY KEY,
  slug text NOT NULL,
  title text NOT NULL,
  description text NOT NULL DEFAULT '',
  publication_state text NOT NULL DEFAULT 'draft'
    CHECK (publication_state IN ('draft', 'published')),
  display_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS collections_slug_lower_idx ON collections (lower(slug));
CREATE INDEX IF NOT EXISTS collections_public_idx
  ON collections (publication_state, display_order);

CREATE TABLE IF NOT EXISTS collection_products (
  collection_id text NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
  product_id text NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  display_order integer NOT NULL DEFAULT 0,
  PRIMARY KEY (collection_id, product_id)
);

CREATE TABLE IF NOT EXISTS product_media (
  id text PRIMARY KEY,
  product_id text NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  object_key text NOT NULL UNIQUE,
  alt_text text NOT NULL,
  content_type text NOT NULL CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp')),
  byte_size integer NOT NULL CHECK (byte_size BETWEEN 1 AND 8388608),
  display_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS product_media_product_idx
  ON product_media (product_id, display_order);
