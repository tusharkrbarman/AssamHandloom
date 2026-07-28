# Cloudflare Commerce Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the demo's backend with a one-click-deployable Cloudflare Worker that preserves the Quiet Commerce storefront and provides secure single-owner catalogue, inventory, and product-media management.

**Architecture:** Add one TypeScript Worker at the repository root while retaining the current FastAPI/Render application as a temporary fallback. The Worker contains isolated storefront, catalogue, authentication/admin, inventory, and media modules backed by one D1 database and one private R2 bucket.

**Tech Stack:** TypeScript 6, Cloudflare Workers, D1, R2, Workers Static Assets, Web Crypto, Wrangler 4, Vitest 4 with Cloudflare's Workers integration.

## Global Constraints

- Preserve the current Quiet Commerce visual hierarchy, copy, CSS, accessibility landmarks, and responsive behavior.
- Phase 1 includes catalogue, collections, variants, inventory, product media, and one owner account only.
- Do not add cart, customer, order, passwordless order link, payment, email, Queue, Durable Object, container, or microservice code.
- Use integer minor units and an explicit three-letter currency code for every price.
- Products are archived rather than hard-deleted.
- Public queries return only published, non-archived products with at least one published variant.
- Inventory adjustments are immutable, idempotent, atomic, and cannot make quantity negative.
- Admin sessions last eight hours and use signed `HttpOnly`, `Secure`, `SameSite=Strict` cookies.
- Admin mutations require a valid session, same-origin verification, and a CSRF token.
- Product uploads accept JPEG, PNG, or WebP up to 8 MiB.
- Existing Python, Render, and PostgreSQL files remain unchanged until Cloudflare acceptance.
- No test-first workflow: implement each bounded slice, then add and run its focused verification.
- Add no runtime npm dependency; use Worker platform APIs and prepared D1 SQL.

---

## Planned File Structure

### Create

- `package.json` — Worker commands, pinned development tools, and deploy-button binding descriptions.
- `package-lock.json` — reproducible npm dependency graph.
- `tsconfig.json` — strict Worker TypeScript configuration.
- `wrangler.jsonc` — Worker, D1, R2, assets, required secrets, and log configuration.
- `.dev.vars.example` — secret names detected by Deploy to Cloudflare.
- `worker-configuration.d.ts` — generated binding and runtime types.
- `d1-migrations/0001_phase_one.sql` — complete Phase 1 schema and inventory invariants.
- `src/index.ts` — request ID, route dispatch, safe errors, logging, health, and asset fallback.
- `src/http.ts` — HTML/JSON responses, redirects, form parsing, origin checks, escaping, and `HttpError`.
- `src/catalogue.ts` — public catalogue reads and owner catalogue writes.
- `src/storefront.ts` — Quiet Commerce HTML and public route handling.
- `src/auth.ts` — owner setup, recovery, password hashing, sessions, lockout, and CSRF.
- `src/admin.ts` — protected server-rendered owner routes and audit coordination.
- `src/inventory.ts` — inventory reads and immutable adjustment insertion.
- `src/media.ts` — upload validation, R2 writes, authorized reads, and deletion.
- `vitest.config.ts` — Cloudflare test runtime and D1 migration injection.
- `test/env.d.ts` — test-only bindings.
- `test/apply-migrations.ts` — clean D1 schema before each test.
- `test/health.spec.ts` — Worker and D1 health behavior.
- `test/storefront.spec.ts` — publication boundaries and Quiet Commerce rendering.
- `test/auth.spec.ts` — setup, login, lockout, session, recovery, and CSRF.
- `test/admin.spec.ts` — catalogue and collection owner workflows.
- `test/inventory.spec.ts` — atomic non-negative idempotent adjustments.
- `test/media.spec.ts` — upload validation, R2 persistence, and public visibility.

### Modify

- `.gitignore` — ignore local Worker secrets and Wrangler state.
- `.github/workflows/quality.yml` — run Worker verification while retaining Python fallback checks.
- `README.md` — add Cloudflare deployment, setup, local development, recovery, and fallback notes.

### Reuse without modification

- `app/static/css/site.css`
- `app/static/js/site.js`
- `app/static/vendor/htmx-2.0.4.min.js`
- `app/templates/` as the markup source during the TypeScript port
- `app/data/river-reed-gold.json` as reference data only; Cloudflare production starts empty

---

### Task 1: Worker Foundation and D1 Schema

**Files:**
- Create: `package.json`
- Create: `package-lock.json`
- Create: `tsconfig.json`
- Create: `wrangler.jsonc`
- Create: `.dev.vars.example`
- Create: `worker-configuration.d.ts`
- Create: `d1-migrations/0001_phase_one.sql`
- Create: `src/http.ts`
- Create: `src/index.ts`
- Create: `vitest.config.ts`
- Create: `test/env.d.ts`
- Create: `test/apply-migrations.ts`
- Create: `test/health.spec.ts`
- Modify: `.gitignore`

**Interfaces:**
- Produces: global `Env` bindings `DB`, `MEDIA`, `ASSETS`, `ADMIN_SETUP_TOKEN`, `ADMIN_RECOVERY_TOKEN`, and `COOKIE_SIGNING_KEY`.
- Produces: `HttpError`, `html()`, `json()`, `redirect()`, `escapeHtml()`, `readForm()`, and `requireSameOrigin()` from `src/http.ts`.
- Produces: the default Worker handler consumed by every integration test.

- [ ] **Step 1: Add the Worker toolchain and commands**

Create `package.json` with no runtime dependencies:

```json
{
  "name": "luit-and-loom-worker",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "wrangler dev --local-protocol=https",
    "types": "wrangler types",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "db:migrate:local": "wrangler d1 migrations apply DB --local",
    "db:migrate:remote": "wrangler d1 migrations apply DB --remote",
    "build": "npm run typecheck && npm test && wrangler deploy --dry-run",
    "deploy": "npm run db:migrate:remote && wrangler deploy",
    "verify": "npm run build"
  },
  "devDependencies": {
    "@cloudflare/vitest-pool-workers": "^0.18.7",
    "typescript": "^6.0.0",
    "vitest": "^4.1.0",
    "wrangler": "^4.114.0"
  },
  "cloudflare": {
    "bindings": {
      "ADMIN_SETUP_TOKEN": {
        "description": "One-time secret used only to create the first owner."
      },
      "ADMIN_RECOVERY_TOKEN": {
        "description": "Separate break-glass secret used to reset owner access."
      },
      "COOKIE_SIGNING_KEY": {
        "description": "Random secret of at least 32 bytes used to sign admin sessions."
      }
    }
  }
}
```

Run `npm install`, then commit the generated `package-lock.json`.

- [ ] **Step 2: Configure the Worker resources and strict types**

Create `wrangler.jsonc` with compatibility date `2026-07-28`, entry point
`src/index.ts`, the existing `app/static` directory as the `ASSETS` binding,
the `DB` D1 binding using `d1-migrations`, the private `MEDIA` R2 binding, all
three required secret names, and Workers Logs enabled at a sampling rate of
`1`.

Use these stable resource defaults so Deploy to Cloudflare can replace their
identifiers:

```jsonc
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "luit-and-loom",
  "main": "src/index.ts",
  "compatibility_date": "2026-07-28",
  "assets": {
    "directory": "./app/static",
    "binding": "ASSETS"
  },
  "d1_databases": [
    {
      "binding": "DB",
      "database_name": "luit-and-loom",
      "database_id": "00000000-0000-0000-0000-000000000000",
      "migrations_dir": "d1-migrations"
    }
  ],
  "r2_buckets": [
    {
      "binding": "MEDIA",
      "bucket_name": "luit-and-loom-media"
    }
  ],
  "secrets": {
    "required": [
      "ADMIN_SETUP_TOKEN",
      "ADMIN_RECOVERY_TOKEN",
      "COOKIE_SIGNING_KEY"
    ]
  },
  "observability": {
    "enabled": true,
    "head_sampling_rate": 1
  }
}
```

Create `.dev.vars.example` with the three secret names and clearly non-secret
example values. Add `.dev.vars`, `.wrangler/`, and `dist/` to `.gitignore`.
Run `npm run types` to generate `worker-configuration.d.ts`.

- [ ] **Step 3: Create the complete Phase 1 schema**

Create `d1-migrations/0001_phase_one.sql` with foreign keys enabled and these
tables:

```sql
CREATE TABLE products (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL COLLATE NOCASE UNIQUE,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  silk_type TEXT NOT NULL,
  colour TEXT,
  occasion TEXT,
  publication_state TEXT NOT NULL DEFAULT 'draft'
    CHECK (publication_state IN ('draft', 'published')),
  featured_rank INTEGER NOT NULL DEFAULT 0,
  archived_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE variants (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id),
  sku TEXT NOT NULL COLLATE NOCASE UNIQUE,
  title TEXT NOT NULL,
  price_minor INTEGER NOT NULL CHECK (price_minor >= 0),
  currency TEXT NOT NULL CHECK (
    length(currency) = 3 AND currency = upper(currency)
  ),
  weight_grams INTEGER CHECK (weight_grams IS NULL OR weight_grams > 0),
  publication_state TEXT NOT NULL DEFAULT 'draft'
    CHECK (publication_state IN ('draft', 'published')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE collections (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL COLLATE NOCASE UNIQUE,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  publication_state TEXT NOT NULL DEFAULT 'draft'
    CHECK (publication_state IN ('draft', 'published')),
  display_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE collection_products (
  collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  display_order INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (collection_id, product_id)
);

CREATE TABLE product_media (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  object_key TEXT NOT NULL UNIQUE,
  alt_text TEXT NOT NULL,
  content_type TEXT NOT NULL CHECK (
    content_type IN ('image/jpeg', 'image/png', 'image/webp')
  ),
  byte_size INTEGER NOT NULL CHECK (byte_size BETWEEN 1 AND 8388608),
  display_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE inventory_items (
  variant_id TEXT PRIMARY KEY REFERENCES variants(id) ON DELETE CASCADE,
  quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
  version INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);

CREATE TABLE inventory_adjustments (
  id TEXT PRIMARY KEY,
  variant_id TEXT NOT NULL REFERENCES inventory_items(variant_id),
  delta INTEGER NOT NULL CHECK (delta <> 0),
  reason TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE owner (
  id TEXT PRIMARY KEY CHECK (id = 'owner'),
  email TEXT NOT NULL COLLATE NOCASE UNIQUE,
  password_hash TEXT NOT NULL,
  password_salt TEXT NOT NULL,
  password_iterations INTEGER NOT NULL CHECK (password_iterations >= 100000),
  session_version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE login_lockouts (
  key_hash TEXT PRIMARY KEY,
  failed_count INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE admin_audit_events (
  id TEXT PRIMARY KEY,
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

Add indexes for product publication/rank, variant product/publication, collection
publication/order, media product/order, and adjustment variant/time.

Add the exact indexes and immutability triggers:

```sql
CREATE INDEX products_public_idx
  ON products(publication_state, archived_at, featured_rank);
CREATE INDEX variants_product_public_idx
  ON variants(product_id, publication_state);
CREATE INDEX collections_public_idx
  ON collections(publication_state, display_order);
CREATE INDEX product_media_product_idx
  ON product_media(product_id, display_order);
CREATE INDEX inventory_adjustments_variant_idx
  ON inventory_adjustments(variant_id, created_at);

CREATE TRIGGER inventory_adjustments_immutable_update
BEFORE UPDATE ON inventory_adjustments
BEGIN
  SELECT RAISE(ABORT, 'inventory_adjustments_immutable');
END;

CREATE TRIGGER inventory_adjustments_immutable_delete
BEFORE DELETE ON inventory_adjustments
BEGIN
  SELECT RAISE(ABORT, 'inventory_adjustments_immutable');
END;
```

- [ ] **Step 4: Add native HTTP helpers and the initial Worker**

Implement `src/http.ts` with this public surface:

```ts
export class HttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export function html(body: string, status = 200, headers?: HeadersInit): Response;
export function json(value: unknown, status = 200): Response;
export function redirect(location: string, status?: 303 | 307): Response;
export function escapeHtml(value: unknown): string;
export async function readForm(request: Request): Promise<FormData>;
export function requireSameOrigin(request: Request): void;
```

`readForm()` must reject non-form requests with `415`. `requireSameOrigin()`
must compare the request URL origin to the `Origin` header and reject a missing
or different origin with `403`.

Implement `src/index.ts` as an exported module Worker. Generate one request ID
per request, handle `GET /health` with `SELECT 1 AS ok`, return `503` if D1 is
unavailable, and fall back to `env.ASSETS.fetch(request)` for unmatched routes.
Convert `HttpError` into safe HTML or JSON according to the `/api/` prefix.
Log only request ID, method, pathname, status, duration, and safe error code.

- [ ] **Step 5: Add the Cloudflare test runtime and health checks**

Configure `vitest.config.ts` with `cloudflareTest()`, `wrangler.jsonc`,
`readD1Migrations("./d1-migrations")`, test secret values, and a
`TEST_MIGRATIONS` binding. In `test/apply-migrations.ts`, call
`applyD1Migrations(env.DB, env.TEST_MIGRATIONS)` before each test.

In `test/health.spec.ts`, use `SELF.fetch()` and assert:

```ts
const response = await SELF.fetch("https://example.com/health");
expect(response.status).toBe(200);
expect(await response.json()).toEqual({ status: "ok" });
```

Also query every required table through `env.DB` to prove the empty migration
applies successfully.

- [ ] **Step 6: Verify and commit the foundation**

Run:

```powershell
npm run types
npm run typecheck
npm test -- test/health.spec.ts
npm run db:migrate:local
npx wrangler deploy --dry-run
```

Expected: generated bindings are current, type checking passes, health tests
pass, the local migration applies once, and Wrangler builds the Worker.

Commit:

```powershell
git add package.json package-lock.json tsconfig.json wrangler.jsonc .dev.vars.example worker-configuration.d.ts d1-migrations src test vitest.config.ts .gitignore
git commit -m "feat: add Cloudflare Worker foundation"
```

---

### Task 2: Public Catalogue and Quiet Commerce Storefront

**Files:**
- Create: `src/catalogue.ts`
- Create: `src/storefront.ts`
- Create: `test/storefront.spec.ts`
- Modify: `src/index.ts`

**Interfaces:**
- Consumes: `Env.DB`, `html()`, `escapeHtml()`, and `HttpError`.
- Produces: `ProductListQuery`, `ProductCard`, `ProductDetail`, `Page<T>`, `listProducts()`, `getProduct()`, `listCollections()`, and `routeStorefront()`.
- Produces: `routeStorefront(request, env): Promise<Response | null>` for `src/index.ts`.

- [ ] **Step 1: Implement prepared catalogue reads**

Define these exact exported types in `src/catalogue.ts`:

```ts
export type PublicationState = "draft" | "published";

export interface ProductListQuery {
  search: string | null;
  silkType: string | null;
  colour: string | null;
  occasion: string | null;
  availableOnly: boolean;
  sort: "featured" | "newest" | "price_asc" | "price_desc";
  page: number;
  pageSize: number;
  collectionSlug: string | null;
}

export interface ProductCard {
  id: string;
  slug: string;
  title: string;
  silkType: string;
  colour: string | null;
  priceMinor: number;
  currency: string;
  available: boolean;
  mediaId: string | null;
  altText: string | null;
}

export interface Page<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}

export interface ProductDetail extends ProductCard {
  description: string;
  occasion: string | null;
  variants: Array<{
    id: string;
    sku: string;
    title: string;
    priceMinor: number;
    currency: string;
    weightGrams: number | null;
    available: boolean;
  }>;
  media: Array<{
    id: string;
    altText: string;
  }>;
}

export interface CollectionSummary {
  id: string;
  slug: string;
  title: string;
  description: string;
}
```

Implement `parseProductListQuery(url)`, `listProducts(db, query)`,
`getProduct(db, slug)`, and `listCollections(db)`. Build SQL only from
allowlisted filter and sort fragments, bind every user value, clamp page size
to `1..24`, and return only published products and variants whose product is
not archived. Escape `%`, `_`, and `\` before a `LIKE` search.

- [ ] **Step 2: Port the Quiet Commerce server-rendered pages**

Implement `src/storefront.ts` with:

```ts
export async function routeStorefront(
  request: Request,
  env: Env,
): Promise<Response | null>;
```

Handle:

- `GET /`
- `GET /shop`
- `GET /search`
- `GET /collections`
- `GET /collections/:slug`
- `GET /products/:slug`
- the existing editorial and guidance routes
- `GET /api/v1/catalog/products`

Port the markup from `app/templates/base.html`, `storefront/home.html`,
`catalog/list.html`, `catalog/product.html`, and their components into focused
render functions. Change asset URLs only:

- `/static/css/site.css` → `/css/site.css`
- `/static/vendor/htmx-2.0.4.min.js` → `/vendor/htmx-2.0.4.min.js`
- `/static/js/site.js` → `/js/site.js`

Keep the exact Quiet Commerce hero, navigation, disabled purchase control,
empty states, accessible labels, skip link, one `<main id="main-content">`,
and mobile disclosure markup. Return only the catalogue results fragment when
`HX-Request: true`.

- [ ] **Step 3: Route public requests through the storefront module**

In `src/index.ts`, call `routeStorefront()` after `/health` and before static
asset fallback. Preserve JSON errors for `/api/` and branded safe pages for
public `404` and unexpected `500` responses.

- [ ] **Step 4: Verify publication boundaries and presentation**

In `test/storefront.spec.ts`, insert one published product/variant, one draft
product/variant, inventory rows, and one published collection using prepared
D1 statements. Assert:

- `/` contains `Woven by Assam.` and `Worn with meaning.`
- `/shop` contains the published title and excludes the draft title
- `/api/v1/catalog/products` follows the same visibility rule
- search whitespace is normalized and page size is clamped
- an invalid API sort returns `422`
- an invalid HTML sort falls back to `featured`
- HTMX returns the results region without the document shell
- an unknown product returns the branded `404`
- one page heading, skip target, labelled navigation, and local assets remain

Run:

```powershell
npm run typecheck
npm test -- test/storefront.spec.ts
```

Expected: all public catalogue and accessibility assertions pass.

- [ ] **Step 5: Commit the public storefront**

```powershell
git add src/index.ts src/catalogue.ts src/storefront.ts test/storefront.spec.ts
git commit -m "feat: add Cloudflare catalogue storefront"
```

---

### Task 3: Single-Owner Authentication and Sessions

**Files:**
- Create: `src/auth.ts`
- Create: `test/auth.spec.ts`
- Modify: `src/index.ts`

**Interfaces:**
- Consumes: `Env.DB`, the three secret bindings, `readForm()`, `redirect()`, and `requireSameOrigin()`.
- Produces: `AdminSession`, `requireOwner()`, `requireCsrf()`, `routeAuth()`, `sessionCookie()`, and `clearSessionCookie()`.
- Produces: `routeAuth(request, env): Promise<Response | null>` for `src/index.ts`.

- [ ] **Step 1: Implement password and token primitives with Web Crypto**

In `src/auth.ts`, use PBKDF2-HMAC-SHA-256 with `600000` iterations, a random
16-byte salt, and a 32-byte derived hash. Store and compare base64url values.
Use `crypto.timingSafeEqual()` for derived hashes and SHA-256 digests of setup
or recovery tokens.

Validate owner input with:

- normalized lowercase email, `3..254` characters, containing one `@`
- password, `12..128` Unicode characters
- setup and recovery tokens, `32..512` characters

Never place any supplied credential or token in an error or log.

- [ ] **Step 2: Implement setup, recovery, login, and lockout**

Handle:

- `GET|POST /admin/setup`
- `GET|POST /admin/login`
- `POST /admin/logout`
- `GET|POST /admin/recover`

Setup inserts only the singleton owner ID `owner` and returns `409` when the
owner already exists. Recovery replaces the password hash and increments
`session_version`, invalidating prior cookies.

Call `requireSameOrigin()` before processing setup, login, recovery, or logout
POST bodies. These unauthenticated forms do not yet have a session CSRF token,
so the origin check is their request-forgery boundary.

Derive the login lockout key by hashing normalized email plus
`CF-Connecting-IP`. After five failures, set `locked_until` fifteen minutes in
the future. A successful login deletes that source's lockout record.

- [ ] **Step 3: Implement signed eight-hour sessions and CSRF**

Use this exact session shape:

```ts
export interface AdminSession {
  ownerId: "owner";
  sessionVersion: number;
  expiresAt: number;
  csrf: string;
}
```

Serialize the session as base64url JSON plus an HMAC-SHA-256 signature using
`COOKIE_SIGNING_KEY`. Verify the signature, expiry, owner ID, and current
database `session_version` on every protected request.

Set:

```text
luit_admin=<value>; Path=/admin; Max-Age=28800; HttpOnly; Secure; SameSite=Strict
```

`requireCsrf()` must call `requireSameOrigin()` and compare the submitted
`csrf` form value to the session token using a timing-safe comparison.

- [ ] **Step 4: Add auth routing and focused security verification**

Call `routeAuth()` before protected admin routing in `src/index.ts`.

In `test/auth.spec.ts`, verify:

- invalid setup token does not create an owner
- setup succeeds once and cannot run again
- incorrect login increments only the source-specific lockout
- the sixth attempt from that source is rejected during the lock window
- another network source can still log in
- a correct login returns the secure cookie
- expired, modified, and wrong-version cookies are rejected
- a protected POST without same-origin and CSRF validation is rejected
- recovery increments `session_version` and invalidates the prior cookie
- responses and captured logs do not contain supplied secrets

Run:

```powershell
npm run typecheck
npm test -- test/auth.spec.ts
```

Expected: all owner security assertions pass.

- [ ] **Step 5: Commit owner authentication**

```powershell
git add src/index.ts src/auth.ts test/auth.spec.ts
git commit -m "feat: add secure owner authentication"
```

---

### Task 4: Protected Catalogue and Collection Management

**Files:**
- Create: `src/admin.ts`
- Create: `test/admin.spec.ts`
- Modify: `src/catalogue.ts`
- Modify: `src/index.ts`

**Interfaces:**
- Consumes: `requireOwner()`, `requireCsrf()`, catalogue read functions, and D1 bindings.
- Produces from `src/catalogue.ts`: `saveProduct()`, `archiveProduct()`, `saveVariant()`, `saveCollection()`, and `setCollectionProducts()`.
- Produces from `src/admin.ts`: `routeAdmin(request, env): Promise<Response | null>`.

- [ ] **Step 1: Add strict catalogue mutation contracts**

Add these inputs to `src/catalogue.ts`:

```ts
export interface ProductInput {
  id: string | null;
  slug: string;
  title: string;
  description: string;
  silkType: string;
  colour: string | null;
  occasion: string | null;
  publicationState: PublicationState;
  featuredRank: number;
}

export interface VariantInput {
  id: string | null;
  productId: string;
  sku: string;
  title: string;
  priceMinor: number;
  currency: string;
  weightGrams: number | null;
  publicationState: PublicationState;
}

export interface CollectionInput {
  id: string | null;
  slug: string;
  title: string;
  description: string;
  publicationState: PublicationState;
  displayOrder: number;
}
```

Accept slugs matching `^[a-z0-9]+(?:-[a-z0-9]+)*$`, titles of `1..160`,
descriptions up to `5000`, silk/colour/occasion values up to `80`, SKUs of
`1..80`, safe integers for price and ranking, and uppercase currency matching
`^[A-Z]{3}$`. Translate uniqueness failures into a safe `409`.

Creating a variant must use one D1 batch to create both the variant and its
zero-quantity `inventory_items` row.

- [ ] **Step 2: Build the protected server-rendered admin**

Implement `src/admin.ts` routes:

- `GET /admin`
- `GET|POST /admin/products/new`
- `GET|POST /admin/products/:id`
- `POST /admin/products/:id/archive`
- `POST /admin/products/:id/variants`
- `POST /admin/variants/:id`
- `GET|POST /admin/collections`
- `GET|POST /admin/collections/:id`

Use ordinary accessible forms and post-redirect-get responses. Every form
includes the session CSRF value. Every mutation calls `requireCsrf()` and
records one `admin_audit_events` row with a fixed action name, target type,
target ID, and a concise summary that excludes full submitted data.

The product edit page owns variant and collection-membership forms. It leaves
inventory and media to their task-specific modules.

- [ ] **Step 3: Route protected admin requests**

In `src/index.ts`, call `routeAdmin()` after `routeAuth()` and before public
storefront routing. Task 5 inserts `routeInventory()` before `routeAdmin()`,
and Task 6 inserts `routeMedia()` before both. Unauthenticated `/admin` routes redirect to
`/admin/login`; authenticated validation errors render inside the admin shell.

- [ ] **Step 4: Verify owner catalogue workflows**

In `test/admin.spec.ts`, set up and log in the owner, then assert:

- an anonymous request cannot read the admin dashboard
- a valid product form creates a draft product
- a duplicate case-insensitive slug returns `409`
- a valid variant creates its inventory row at zero
- negative price and lowercase currency are rejected
- collection membership is replaced atomically
- publishing makes the product visible only when a published variant exists
- archiving removes the product from public reads without deleting its row
- every successful mutation creates one safe audit event

Run:

```powershell
npm run typecheck
npm test -- test/admin.spec.ts test/storefront.spec.ts
```

Expected: admin and public catalogue tests pass.

- [ ] **Step 5: Commit catalogue administration**

```powershell
git add src/index.ts src/catalogue.ts src/admin.ts test/admin.spec.ts
git commit -m "feat: add owner catalogue management"
```

---

### Task 5: Atomic Inventory Management

**Files:**
- Create: `src/inventory.ts`
- Create: `test/inventory.spec.ts`
- Modify: `src/admin.ts`
- Modify: `src/index.ts`

**Interfaces:**
- Consumes: the inventory schema trigger, `requireOwner()`, and `requireCsrf()`.
- Produces: `InventoryItem`, `InventoryAdjustmentInput`, `listInventory()`, `adjustInventory()`, and `routeInventory()`.

- [ ] **Step 1: Implement immutable inventory operations**

Use these contracts in `src/inventory.ts`:

```ts
export interface InventoryItem {
  variantId: string;
  sku: string;
  productTitle: string;
  quantity: number;
  version: number;
}

export interface InventoryAdjustmentInput {
  variantId: string;
  delta: number;
  reason: string;
  idempotencyKey: string;
  actor: "owner";
}
```

`adjustInventory()` validates a non-zero safe-integer delta, a reason of
`3..200` characters, and a UUID idempotency key. First return an existing row
for the same idempotency key. Otherwise run one D1 batch containing:

```sql
INSERT INTO inventory_adjustments (
  id, variant_id, delta, reason, idempotency_key, actor, created_at
)
SELECT ?1, ?2, ?3, ?4, ?5, ?6, ?7
WHERE EXISTS (
  SELECT 1
  FROM inventory_items
  WHERE variant_id = ?2 AND quantity + ?3 >= 0
);

UPDATE inventory_items
SET quantity = quantity + ?2,
    version = version + 1,
    updated_at = ?3
WHERE variant_id = ?1
  AND EXISTS (
    SELECT 1
    FROM inventory_adjustments
    WHERE id = ?4 AND variant_id = ?1
  );
```

Bind the first statement as adjustment ID, variant ID, delta, reason,
idempotency key, actor, timestamp. Bind the second as variant ID, delta,
timestamp, adjustment ID. D1 executes the batch as one transaction. If the
insert reports zero changes, return `409 insufficient_stock`. If a concurrent
duplicate idempotency key fails the batch, fetch and return the original
adjustment; the failed batch rolls back its stock update.

- [ ] **Step 2: Add protected inventory forms**

Handle:

- `GET /admin/inventory`
- `POST /admin/inventory/:variantId/adjust`

The GET page lists SKU, product, quantity, version, and adjustment history.
Each adjustment form contains a new `crypto.randomUUID()` idempotency key,
integer delta, reason, and CSRF token. Successful adjustment redirects back to
inventory and records one admin audit event.

- [ ] **Step 3: Verify inventory invariants**

In `test/inventory.spec.ts`, create one product, variant, and zero inventory
row, then assert:

- `+3` produces quantity `3` and one immutable history row
- retrying the same idempotency key returns the same result and leaves quantity `3`
- `-4` returns `409`, leaves quantity `3`, and creates no history row
- `-3` produces quantity `0`
- direct update or deletion of an adjustment fails
- concurrent requests using one idempotency key produce one stock change
- an anonymous or CSRF-invalid adjustment cannot write

Run:

```powershell
npm run typecheck
npm test -- test/inventory.spec.ts
```

Expected: all inventory invariants pass.

- [ ] **Step 4: Commit inventory management**

```powershell
git add src/index.ts src/admin.ts src/inventory.ts test/inventory.spec.ts
git commit -m "feat: add atomic inventory management"
```

---

### Task 6: Validated Product Media in R2

**Files:**
- Create: `src/media.ts`
- Create: `test/media.spec.ts`
- Modify: `src/admin.ts`
- Modify: `src/index.ts`
- Modify: `src/storefront.ts`

**Interfaces:**
- Consumes: `Env.MEDIA`, `Env.DB`, `requireOwner()`, `requireCsrf()`, and product publication state.
- Produces: `detectImageType()`, `uploadProductMedia()`, `getMediaResponse()`, `deleteProductMedia()`, and `routeMedia()`.

- [ ] **Step 1: Implement strict image detection and R2 storage**

In `src/media.ts`, detect:

- JPEG: bytes `FF D8 FF`
- PNG: bytes `89 50 4E 47 0D 0A 1A 0A`
- WebP: ASCII `RIFF` at bytes `0..3` and `WEBP` at bytes `8..11`

Reject empty files, files above `8388608` bytes, mismatched declared MIME
types, and every other signature with `415 invalid_image`. Require alternative
text of `1..300` characters.

Write the object as:

```text
products/<product UUID>/<media UUID>.<jpg|png|webp>
```

Set R2 `contentType`, `contentDisposition: inline`, and
`cacheControl: public, max-age=31536000, immutable`. If the D1 metadata insert
fails, delete the newly written R2 object before returning the safe error.

- [ ] **Step 2: Add protected upload/delete and safe media delivery**

Handle:

- `POST /admin/products/:productId/media`
- `POST /admin/media/:mediaId/delete`
- `GET /admin/media/:mediaId/content`
- `GET /media/:mediaId`

The protected content route requires the owner and allows draft previews. The
public route joins `product_media` to a published, non-archived product before
reading R2. Apply stored HTTP metadata and the object's ETag to the response.

On deletion, delete D1 metadata first and then the R2 object. A failed R2
delete logs only the object key and request ID; it leaves an unreferenced
object rather than a broken catalogue record.

- [ ] **Step 3: Connect media to admin and storefront rendering**

Add the upload form and protected thumbnails to the product edit page. Update
public product cards and galleries to use `/media/:mediaId`. Keep the existing
textile-colour study whenever a product has no public media.

- [ ] **Step 4: Verify media trust boundaries**

In `test/media.spec.ts`, assert:

- valid minimal JPEG, PNG, and WebP signatures upload
- declared/detected mismatch returns `415`
- an executable payload renamed `.jpg` returns `415`
- a file over 8 MiB returns `413`
- missing alternative text returns `422`
- a successful upload creates one R2 object and one D1 metadata row
- D1 failure removes the just-uploaded R2 object
- draft media is owner-visible but public `404`
- published media returns its content type, cache policy, and ETag
- deleting metadata makes the media public route return `404`

Run:

```powershell
npm run typecheck
npm test -- test/media.spec.ts test/storefront.spec.ts
```

Expected: all upload and visibility assertions pass.

- [ ] **Step 5: Commit R2 product media**

```powershell
git add src/index.ts src/admin.ts src/storefront.ts src/media.ts test/media.spec.ts
git commit -m "feat: add validated R2 product media"
```

---

### Task 7: One-Click Deployment, CI, and Operator Documentation

**Files:**
- Modify: `.github/workflows/quality.yml`
- Modify: `README.md`
- Modify: `package.json`

**Interfaces:**
- Consumes: `npm run verify`, `npm run deploy`, all Wrangler bindings, and all Phase 1 routes.
- Produces: a Deploy to Cloudflare button and repeatable owner setup/recovery instructions.

- [ ] **Step 1: Add Worker verification to GitHub Actions**

Keep the existing Python/PostgreSQL/Render checks while that fallback remains.
Add Node setup with npm caching after checkout, then run:

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: "24"
    cache: npm
- name: Install Worker dependencies
  run: npm ci
- name: Verify Cloudflare Worker
  run: npm run verify
```

Provide only fixed test secrets in the workflow environment. Never add
production Cloudflare tokens to pull-request jobs.

- [ ] **Step 2: Document one-click and local operation**

Place this button near the top of `README.md`:

```markdown
[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/tusharkrbarman/AssamHandloom)
```

Document:

1. Cloudflare asks the user to name the Worker, D1 database, and R2 bucket.
2. Cloudflare asks for three independent random secret values.
3. Deployment applies D1 migrations before publishing the Worker.
4. The owner opens `/admin/setup` once.
5. The empty production catalogue is populated through `/admin`.
6. `/health` confirms Worker and D1 readiness.
7. Recovery requires `/admin/recover` and the separate recovery token.
8. The existing Render instructions remain labelled temporary fallback.

Add local commands:

```powershell
Copy-Item .dev.vars.example .dev.vars
npm ci
npm run db:migrate:local
npm run dev
npm run verify
```

State explicitly that Phase 1 has no checkout, orders, payments, customer
accounts, or transactional email.

- [ ] **Step 3: Run the complete local acceptance gate**

Run:

```powershell
npm ci
npm run types
npm run verify
git diff --check
```

Then start local HTTPS development and manually verify:

- `/health`
- `/`
- `/shop`
- `/admin/setup`
- `/admin/login`
- product and variant creation
- collection membership
- inventory adjustment and retry
- image upload
- publication appearing on the storefront
- archive removing the product publicly

Expected: automated checks pass, all listed routes work, and no purchase
functionality appears enabled.

- [ ] **Step 4: Verify the production deployment path**

Before using real inventory, use a test Cloudflare account or temporary Worker
name to exercise the README button. Confirm:

- the repository is cloned;
- Worker, D1, and R2 are provisioned;
- secret prompts are clear;
- `0001_phase_one.sql` is applied;
- the Worker deployment succeeds;
- `/health` returns `200`;
- owner setup works once;
- no secret appears in build or Worker logs.

If the temporary deployment was created solely for verification, ask the
owner before removing it through the Cloudflare dashboard.

- [ ] **Step 5: Commit deployment and documentation**

```powershell
git add .github/workflows/quality.yml README.md package.json package-lock.json
git commit -m "docs: add Cloudflare one-click deployment"
```

- [ ] **Step 6: Run the branch completion gate**

Run:

```powershell
npm run verify
python -m pytest -q
python -m ruff check app tests migrations
python -m mypy app
git status --short
```

Expected: Worker verification and the retained Python fallback suite pass;
the worktree contains no unintended changes.

---

## Plan Completion Criteria

- The Cloudflare Worker passes every focused Phase 1 verification.
- The existing Quiet Commerce experience is preserved.
- One owner can securely manage catalogue, variants, collections, stock, and images.
- A fresh D1 database migrates from empty state.
- One Deploy to Cloudflare flow provisions Worker, D1, R2, and secret prompts.
- The public site never exposes draft or archived records.
- Inventory and media failure paths preserve data integrity.
- Phase 2 features remain absent rather than partially scaffolded.
- FastAPI/Render remains available only as a temporary rollback path.
