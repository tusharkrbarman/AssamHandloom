# Luit & Loom — Cloudflare Commerce Architecture

**Date:** 28 July 2026
**Status:** Approved architecture awaiting written-spec review
**Scope:** Cloudflare migration and phased commerce backend
**Related design:** `2026-07-27-luit-and-loom-fastapi-commerce-design.md`

## 1. Purpose

Luit & Loom will move from its current FastAPI/PostgreSQL demo to a
Cloudflare-native application that can be deployed from GitHub with a Deploy
to Cloudflare button.

The first implementation will manage the catalogue, inventory, product media,
and one store owner. Cart, checkout, orders, payments, and customer
communications are deliberate later phases.

The Quiet Commerce storefront remains the visual source of truth. This
architecture changes the runtime and data layer; it does not authorize a
storefront redesign.

## 2. Constraints

- Keep the initial deployment within Cloudflare's free allowances.
- Support one owner and one store.
- Prefer a one-click deployment over preserving the Python backend.
- Preserve clear service boundaries without operating multiple services yet.
- Do not accept real payments in phase one.
- Keep deferred commerce capabilities on an explicit roadmap.
- Avoid infrastructure that has no measured current need.

## 3. Decision

The application will be one TypeScript Cloudflare Worker with:

- Cloudflare D1 as its relational database
- Cloudflare R2 for product images
- Cloudflare Workers Static Assets for storefront assets
- Cloudflare Secrets Store bindings for deployment secrets
- Cloudflare Workers Logs for basic operational visibility

The Worker will use native `Request`, `Response`, Web Crypto, R2, and D1 APIs.
D1 access will use prepared SQL directly. Phase one does not need an ORM, a
general web framework, a container, or independently deployed microservices.

The existing FastAPI, SQLAlchemy, Alembic, and PostgreSQL implementation will
remain usable until the Cloudflare replacement is ready, but they will not run
inside the new Worker.

### Why this option

Cloudflare Containers can preserve FastAPI but require the Workers Paid plan.
Several independent Workers would complicate deployment because one Deploy to
Cloudflare button does not deploy a multi-Worker monorepo. A single modular
Worker is therefore the smallest architecture that satisfies the cost and
deployment requirements while retaining boundaries for later extraction.

## 4. System Structure

```text
Browser
  |
  v
Cloudflare Worker
  |-- Storefront module
  |-- Catalogue module
  |-- Inventory module
  |-- Admin module
  `-- Media module
       |-- D1
       `-- R2
```

Each module owns a business responsibility:

- **Storefront:** Serves public HTML, static assets, and read-only catalogue
  endpoints. It owns no business tables.
- **Catalogue:** Owns products, variants, collections, publication state, silk
  attributes, and media metadata.
- **Inventory:** Owns current stock and immutable adjustment history.
- **Admin:** Authenticates the owner, validates admin requests, and coordinates
  catalogue, inventory, and media operations. It does not duplicate commerce
  data.
- **Media:** Validates image uploads and writes image objects to R2. Catalogue
  remains the owner of product-to-image relationships.

Modules may access another module's data only through that module's service
functions. D1 cannot enforce table ownership between code modules, so this
boundary is enforced by project structure and focused integration checks.

## 5. Data Ownership

### Catalogue tables

- `products`
- `variants`
- `collections`
- `collection_products`
- `product_media`

Products are archived instead of hard-deleted. Prices are stored as integer
minor units with an explicit currency code. Identifiers are UUID strings
created with `crypto.randomUUID()`.

### Inventory tables

- `inventory_items`
- `inventory_adjustments`

Every stock change includes a reason, actor, timestamp, and idempotency key.
Adjustment records are immutable. A conditional stock update and its
adjustment record execute in one D1 batch transaction. The update fails rather
than allowing available stock to become negative.

### Admin tables

- `owner`
- `admin_audit_events`
- minimal login-lockout state

Only one active owner is supported. Admin audit records capture the action,
target, timestamp, and safe change summary without storing credentials.

### Storage keys

R2 contains image objects only. D1 stores their generated object keys,
alternative text, dimensions, order, and publication metadata.

## 6. Primary Flows

### Public catalogue

1. The browser requests a storefront route.
2. Storefront calls Catalogue.
3. Catalogue reads published records from D1.
4. Storefront renders the Quiet Commerce page.

Unpublished and archived records never appear in public queries.

### Catalogue change

1. Admin verifies the owner session and request integrity.
2. Catalogue validates and normalizes the submitted fields.
3. Catalogue writes the change with prepared D1 statements.
4. Admin records a safe audit summary.

### Inventory adjustment

1. Admin verifies the owner session.
2. Inventory validates the variant, quantity delta, reason, and idempotency key.
3. D1 atomically applies the conditional quantity update and history record.
4. A repeated idempotency key returns the original result instead of changing
   stock again.

### Image upload

1. Admin verifies the owner session and CSRF token.
2. Media validates the declared and detected image type and size.
3. The Worker writes the image to R2 under a randomized key.
4. Catalogue saves the approved metadata and product relationship in D1.

Phase one intentionally sends the upload through the Worker. Direct
browser-to-R2 uploads would require extra R2 API credentials and request
signing; they can be introduced if upload volume or file size makes the simpler
flow inadequate.

## 7. Admin Security

The deployment asks for a one-time setup token, a separate break-glass
recovery token, and a cookie-signing key. On the first visit to the admin setup
route, the setup token permits creation of the owner email and password, then
setup is permanently marked complete.

- Passwords use salted PBKDF2-HMAC-SHA-256 through Web Crypto.
- The stored password record includes the algorithm and calibrated iteration
  count so it can be upgraded later.
- Successful login creates a signed, `HttpOnly`, `Secure`,
  `SameSite=Strict` cookie with an eight-hour lifetime.
- Admin mutations require the valid session, same-origin verification, and a
  CSRF token.
- Five failed login attempts for the same normalized email and network source
  lock that source for fifteen minutes without globally locking the owner out.
- Setup and recovery responses do not disclose credentials.
- Recovery requires the separate recovery token; rotating that Cloudflare
  secret invalidates the previous recovery value.
- All SQL is prepared and all input is validated at the request boundary.

Image uploads accept JPEG, PNG, or WebP only, have a fixed size ceiling, use
randomized object keys, and are served with safe content headers.

Public errors use stable error codes and helpful generic messages. Logs may
contain a request ID, route, status, duration, and error code, but never
passwords, session values, setup tokens, or complete submitted payloads.

## 8. Deployment and Updates

The public GitHub repository will contain:

- a Deploy to Cloudflare button
- the Worker source and static assets
- Wrangler resource declarations
- ordered D1 SQL migrations
- a custom deployment command
- short setup and recovery instructions

Cloudflare will clone the repository, allow the user to name the resources,
and provision the Worker, D1 database, R2 bucket, and required secret binding.
The custom deployment command will:

1. Apply pending D1 migrations using the D1 binding name.
2. Deploy the Worker.

Migrations are forward-only and backward-compatible with the currently
deployed Worker because a database migration can succeed before a Worker
deployment fails. D1 records applied migrations and creates a backup when
Wrangler applies them.

Future pushes to the configured production branch use Workers Builds to repeat
the same deployment process.

The application exposes `GET /health`. It checks that the Worker is running,
required bindings exist, and D1 can answer a trivial query. It does not mutate
data or expose configuration.

Workers Logs supplies request and error visibility in Cloudflare's dashboard.
No external monitoring vendor, staging platform, or alerting service is
required for phase one.

## 9. Verification

The repository will leave one compact runnable verification path covering:

- TypeScript type checking
- empty-database migration
- published versus unpublished catalogue reads
- owner setup, login, lockout, session, and CSRF enforcement
- image type and size rejection
- atomic, non-negative, idempotent inventory adjustment
- the health endpoint

Pure logic should use Node's built-in test runner where practical. Local
Worker/D1 behavior should be checked through the Cloudflare development
runtime. A large test framework, browser farm, and exhaustive end-to-end suite
are not phase-one requirements.

## 10. Commerce Roadmap

### Phase 2 — Selling

- Browser-based cart
- Guest checkout
- Orders with immutable product and price snapshots
- Time-limited inventory reservations in D1
- One payment provider, initially Razorpay
- Signature-validated, idempotent payment webhooks

The server recalculates prices and availability. The browser never supplies
trusted money, stock, or payment state.

### Phase 3 — After purchase

- Signed, expiring passwordless order links
- Order confirmation and status email
- Cloudflare Queues for retryable webhook and email processing
- Reservation expiry and abandoned-order cleanup

### Optional later capabilities

- Customer accounts
- Staff roles beyond the single owner
- Returns, coupons, reviews, and advanced shipping or tax integrations
- Durable Objects if measured purchase concurrency makes D1 inventory
  coordination inadequate

These items are roadmap commitments, not phase-one scaffolding.

## 11. Microservice Extraction Rules

A module becomes its own Worker only when at least one of these is true:

- it needs an independent release schedule;
- a separate team owns and operates it;
- its traffic or resource profile requires independent scaling;
- isolation measurably improves reliability or security.

Extraction will give the module its own D1 database and expose it through a
Cloudflare service binding. No module is extracted because of file count,
forecast growth, or the label "microservices."

## 12. Free-Tier Assumptions

As of 28 July 2026, the expected phase-one workload fits within:

- Workers Free: 100,000 requests per day
- D1 Free: 5 million rows read per day, 100,000 rows written per day, and
  5 GB stored
- R2 Free: 10 GB-month stored, 1 million Class A operations per month, and
  10 million Class B operations per month
- Workers Builds Free: 3,000 build minutes per month
- Workers Logs Free: 200,000 log events per day with three-day retention

These are limits, not a promise that production commerce has no cost. A custom
domain, payment processing, transactional email, SMS, taxes, shipping, or
usage above Cloudflare's allowances can incur charges.

Current references:

- [Deploy to Cloudflare buttons](https://developers.cloudflare.com/workers/platform/deploy-buttons/)
- [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- [D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/)
- [R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [Workers Builds pricing](https://developers.cloudflare.com/workers/ci-cd/builds/limits-and-pricing/)
- [Workers Logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/)

## 13. Phase-One Acceptance Criteria

Phase one is complete when:

- one Deploy to Cloudflare flow provisions and publishes the application;
- the Quiet Commerce storefront reads its catalogue from D1;
- unpublished products remain private;
- the owner can complete setup and sign in securely;
- the owner can manage products, variants, collections, images, and stock;
- repeated stock requests cannot duplicate an adjustment;
- stock cannot become negative;
- image uploads are validated and stored in R2;
- migrations succeed from an empty D1 database;
- logs and public errors do not reveal secrets;
- the compact verification path passes locally and during deployment;
- no cart, order, payment, email, or customer feature is presented as complete.
