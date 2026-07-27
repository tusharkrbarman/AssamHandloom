# Luit & Loom — FastAPI Commerce Store Design

**Date:** 27 July 2026  
**Status:** Approved design awaiting written-spec review  
**Supersedes:** `2026-07-27-assamese-silk-store-design.md`

## 1. Purpose

Luit & Loom will be a production ecommerce store dedicated exclusively to authentic Assamese silk sarees. It will sell within India and to supported international destinations without a fixed commerce-platform subscription.

The store must combine:

- A distinctive premium-contemporary Assamese brand
- An artistic, accessible, mobile-first storefront
- Real products, inventory, carts, payments, orders, fulfilment, returns, and refunds
- Guest checkout with secure passwordless order access
- Detailed artisan and product provenance
- Public authenticity certificates with QR verification
- A protected staff administration area
- International shipping and customs readiness
- Low fixed infrastructure cost without compromising payment or customer-data security

The application may use low-cost or free development tiers, but the production business accepts unavoidable usage-based costs for its domain, hosting, PostgreSQL, storage, email, backups, monitoring, shipping services, and payment processing.

## 2. Chosen Architecture

Luit & Loom will be one integrated Python application:

- **FastAPI** serves storefront pages, staff pages, APIs, checkout workflows, payment webhooks, and health endpoints.
- **PostgreSQL** is the authoritative store for commerce, content, identity, provenance, job, and audit data.
- **SQLAlchemy 2** provides database access.
- **Alembic** provides versioned database migrations.
- **Jinja templates** render SEO-friendly storefront and staff pages.
- **HTMX** progressively enhances partial-page interactions.
- **Focused JavaScript** handles only interactions that require browser APIs, such as image galleries and Razorpay Standard Checkout.
- **Razorpay Standard Checkout** collects payment details; raw card or UPI credentials never enter the application.
- **S3-compatible object storage** holds public product media and private verification evidence in separate access domains.
- **Transactional email** delivers order messages and passwordless order-access links.

One Docker image runs with three explicit roles:

1. **Web:** storefront, staff area, APIs, checkout, health endpoints, and payment webhooks.
2. **Worker:** email, payment processing, refunds, media jobs, certificate generation, and retryable operations.
3. **Scheduler:** inventory-reservation expiry, abandoned-cart cleanup, reconciliation, and recovery jobs.

The first release is a modular monolith. A separate JavaScript frontend, microservices, Redis, Kafka, and a general analytics warehouse are intentionally excluded.

## 3. Brand System

### 3.1 Identity

**Name:** Luit & Loom  
**Tagline:** Woven by Assam. Worn with meaning.

“Luit” refers to the Brahmaputra in Assam, while “Loom” expresses the making process at the centre of the brand.

### 3.2 Positioning

Luit & Loom is a premium-contemporary saree house: authentic Assamese heritage presented with modern refinement. It should feel elevated and collectible without becoming distant, ornate, or inaccessible.

### 3.3 Visual language

Core palette:

- Muga gold
- Warm ivory
- Deep lac red
- Betel-leaf green
- Charcoal

The visual system pairs an elegant high-contrast serif with a restrained modern sans-serif. Layouts use generous negative space, disciplined alignment, strong typographic hierarchy, and editorial pacing.

Assamese textile geometry may appear sparingly in borders, dividers, packaging motifs, and interaction details. It must not become a dense decorative background. The design avoids generic gold gradients, crowded festival graphics, ornamental excess, and visual clichés.

Photography emphasizes natural light, full drapes, close-up weave textures, borders, pallus, blouse pieces, and honest artisan portraits.

### 3.4 Voice

The voice is poetic in storytelling and precise in commerce. Silk type, dimensions, weight, colour, blouse-piece details, origin, care, dispatch, returns, availability, and authenticity remain easy to scan.

## 4. Storefront Information Architecture

### 4.1 Global navigation

Primary navigation:

- New Arrivals
- Shop
- Muga Silk
- Pat Silk
- Eri Silk
- Artisans
- Our Story
- Journal

Persistent utilities:

- Search
- Region and currency context
- Wishlist
- Cart
- Order access

Footer:

- Contact
- FAQ
- Silk Guide
- Care Guide
- Shipping
- Returns
- Order Access
- Privacy
- Terms
- Newsletter
- Social channels

### 4.2 Homepage

The homepage sequence:

1. Cinematic brand hero with “Shop the Collection” and “Meet the Artisans”
2. Featured sarees curated by silk type
3. Concise “Why Assam silk” introduction
4. Muga, Pat, and Eri collection cards
5. Featured artisan and weaving process
6. Craft, provenance, and authenticity guarantees
7. Occasion-led recommendations
8. Shipping, returns, and care assurances
9. Editorial newsletter invitation

Staff can reorder, enable, disable, and edit homepage sections without changing code.

### 4.3 Collection and search

Collection pages support:

- Silk type, colour, occasion, price, weave, and availability filters
- Featured, newest, price, and best-selling sorting
- A second detail image on hover-capable devices
- Product cards with silk type, artisan, price, and availability
- Clear no-results and filter-reset states
- Pagination with stable, shareable URLs

Search covers products, artisans, collections, articles, and guidance pages. Search input is normalized and rate-limited. Results never reveal private or unpublished records.

### 4.4 Product page

Each product page includes:

- Full drape, border, pallu, weave-detail, and blouse-piece media
- Product name, price, availability, dispatch estimate, and purchase controls
- Silk type, dimensions, weight, colour, blouse-piece details, and care
- Artisan profile, weaving region, production time, and motif meaning
- Authenticity status and certificate explanation
- Shipping, duties, returns, and fall/pico service information
- Related sarees selected by explicit catalogue relationships

Unavailable products remain viewable when their story has editorial value and offer relevant alternatives.

### 4.5 Supporting content

The first release includes:

- Our Story
- Artisans directory and profiles
- Silk Guide
- Care Guide
- Journal index and articles
- Contact
- FAQ
- Shipping policy
- Returns policy
- Privacy policy
- Terms
- Order-access request page

## 5. Inaugural Catalogue

The launch concept is **River, Reed & Gold**, a 12-piece editorial sample collection:

- Four Muga silk statement sarees
- Four Pat silk occasion sarees
- Two Eri silk understated sarees
- Two contemporary silk-blend sarees at an accessible entry price

Working sample names:

1. Luit Dawn
2. Sualkuchi Gold
3. Xorai Light
4. Monsoon Reed
5. Kopou Ivory
6. Jaapi Vermilion
7. Dikhow Moon
8. Bihu Ember
9. Eri Mist
10. Forest Quiet
11. River Reed
12. Lac Horizon

Each product has a distinct name, colour story, silk and weave classification, motif meaning, verified artisan relationship, dimensions, weight, blouse-piece details, care, INR price, inventory, and dispatch state.

The initial journal contains:

1. Understanding the silks of Assam
2. How to identify authentic Muga silk
3. How to care for a handwoven silk saree

Development may use clearly labelled sample records and art-directed placeholder imagery. Before real orders are enabled, every product image, price, stock value, artisan identity, location, and provenance claim must be replaced or verified against the actual saree and weaver. Generated imagery must never be presented as actual sale inventory or documentary evidence.

## 6. Data Model and Ownership

PostgreSQL is authoritative for all application-owned data.

### 6.1 Catalogue

- **Product:** identity, title, slug, copy, publishing state, tax category, customs description, country of origin, HS code, timestamps.
- **Variant:** SKU, option values, price in INR minor units, compare-at price, weight, dimensions, inventory policy, and publishing state.
- **Collection:** identity, slug, name, description, image, publishing state, and ordering.
- **Product media:** object key, public/private class, alternative text, width, height, ordering, and processing state.
- **Product relationship:** explicit related-product and occasion relationships.

Money is stored as integer minor units with an ISO 4217 currency code. Floating-point values are never used for prices, discounts, tax, shipping, payment amounts, or refunds.

### 6.2 Inventory

- **Inventory item:** variant reference, on-hand quantity, reserved quantity, reorder threshold, and version.
- **Inventory movement:** immutable quantity delta, reason, order/reference, actor, and timestamp.
- **Inventory reservation:** cart or order reference, quantity, expiry, status, and timestamps.

Available quantity equals on-hand quantity minus active reserved quantity. Inventory movements provide the auditable stock history; current counters provide fast availability checks.

### 6.3 Customer and guest access

- **Customer contact:** normalized email, optional phone, marketing consent, and privacy timestamps.
- **Address:** encrypted or protected personal delivery fields with country-specific validation.
- **Order access token:** order reference, hashed token, expiry, use timestamp, request context, and revocation state.

The store does not maintain customer passwords. Customer contact records exist to fulfil orders, provide lawful communications, and honor privacy requests.

### 6.4 Commerce

- **Cart and cart line**
- **Order and order line snapshot**
- **Payment attempt**
- **Refund**
- **Shipment and tracking event**
- **Coupon and coupon redemption**
- **Tax and shipping rule**
- **Commerce audit event**

Order lines snapshot the purchased title, SKU, options, unit price, tax, discount, and provenance reference so later catalogue changes do not rewrite order history.

### 6.5 Provenance

- **Artisan:** approved public identity, region, biography, speciality, portrait reference, and verification state.
- **Artisan evidence:** private consent and verification records.
- **Provenance:** variant, artisan, silk type, region, motif, production dates, verification state, and reviewer.
- **Certificate:** permanent number, public slug, QR destination, issue state, issue time, optional order line, and revocation reason.
- **Audit event:** actor, action, record type, record identifier, change summary, and timestamp.

Verified provenance and certificate history is not silently deleted or rewritten. Corrections create auditable changes. Revoked certificates remain publicly resolvable with a safe explanation.

## 7. Cart, Pricing, and Inventory Reservation

Adding a product to the cart does not reserve inventory. Every server response recalculates line totals from current database values; the browser never supplies trusted prices.

At checkout:

1. Normalize and validate cart, address, coupon, shipping choice, and contact information.
2. Lock affected inventory rows in a PostgreSQL transaction.
3. Recalculate subtotal, discount, shipping, tax, and total.
4. Create an order snapshot in `pending_payment`.
5. Create a 15-minute inventory reservation.
6. Commit the transaction.
7. Create a Razorpay order using the internal order identifier and stored payment-attempt record.

The scheduler expires abandoned reservations. A confirmed payment converts the reservation into a permanent inventory movement.

If a valid captured-payment webhook arrives after reservation expiry, the worker attempts a new transactional reservation. If stock is no longer available, the order enters `payment_review`, staff are alerted, and the captured amount is refunded through an idempotent refund operation. The system must never silently confirm an oversold unique saree.

Coupons support:

- Fixed or percentage discount
- Active date range
- Minimum order
- Global and per-email usage limits
- Applicable products or collections
- Maximum discount for percentage coupons

Coupon eligibility and redemption are decided inside the checkout transaction.

## 8. Payment Processing

### 8.1 Provider

Razorpay Standard Checkout is the first payment provider. Provider code is isolated behind an internal payment interface so another gateway can be added without rewriting order rules.

The production merchant must complete Razorpay KYC and separately activate international payments. The store does not promise an international method or currency until the live merchant account confirms eligibility.

### 8.2 Payment flow

1. FastAPI creates the internal pending order and inventory reservation.
2. The backend creates a Razorpay order for the exact server-calculated amount and currency.
3. The browser opens Razorpay Standard Checkout using the returned public order data.
4. The browser callback may be signature-checked to show a provisional status, but it never confirms the order.
5. A Razorpay webhook is validated against the untouched raw request body.
6. A unique provider event ID prevents duplicate processing.
7. The worker reconciles provider payment details against the internal payment attempt.
8. Only a verified captured payment can confirm the order.

Provider event payloads are retained only to the degree required for reconciliation, audit, and dispute handling. Logs do not contain secrets or unnecessary payment/customer data.

### 8.3 Refunds

Staff initiate full or partial refunds against eligible captured payments. The application:

1. Creates a `refund_pending` record with an idempotency key.
2. Calls Razorpay from the worker.
3. Reconciles the provider response and subsequent webhook.
4. Updates order and refund state without duplicating funds.
5. Records an immutable audit event.

Failed refund attempts retry only when the error is transient. Permanent failures require staff review.

## 9. Orders and Fulfilment

Primary order states:

- `pending_payment`
- `payment_review`
- `confirmed`
- `processing`
- `shipped`
- `delivered`
- `cancelled`
- `return_requested`
- `returned`
- `refund_pending`
- `partially_refunded`
- `refunded`

State transitions are explicit domain operations, not arbitrary status edits. Every transition validates prerequisites and creates an audit event.

Orders support:

- Domestic and international addresses
- Order notes and gift messages
- Shipment carrier and tracking references
- Partial fulfilment where an order contains multiple items
- Cancellation before fulfilment
- Return review and receipt
- Full or partial refund
- Staff-visible payment and fulfilment timelines

Transactional notifications cover order receipt, confirmed payment, payment review, cancellation, shipping, delivery, return receipt, and refund.

## 10. Guest Checkout and Passwordless Order Access

Customers check out without creating a password account.

After an order is created, the store sends a single-use order-access link. Tokens:

- Contain at least 256 bits of randomness
- Are stored only as cryptographic hashes
- Expire after 20 minutes
- Become invalid after first use
- Are revoked when a replacement is issued
- Are scoped to one order

A customer can request a new link using order number and matching email. The response is identical whether the pair exists or not. Requests are rate-limited by network, normalized email, and order identifier to reduce enumeration and abuse.

Opening a valid link establishes a short-lived, server-managed session authorized only for that order. Sensitive address fields are partially masked except where needed for the current workflow.

## 11. Staff Administration

The custom staff area uses server-rendered FastAPI/Jinja pages with HTMX enhancements.

Capabilities:

- Products, variants, collections, media, prices, and publishing
- Inventory receipts, adjustments, reservations, and movement history
- Order review, fulfilment, cancellation, returns, and refunds
- Shipping zones, methods, rates, and free-shipping thresholds
- Coupon creation and usage review
- Artisan identity, evidence, consent, and provenance verification
- Certificate issuance and revocation
- Homepage curation, content pages, journal articles, and navigation
- Customer privacy export and deletion workflows
- Background-job failure and payment-reconciliation review
- Security and commerce audit history

Roles:

- **Administrator:** system configuration, staff access, and all workflows
- **Catalogue editor:** catalogue, media, editorial content, and homepage
- **Fulfilment operator:** orders, inventory, shipments, returns, and permitted refunds
- **Provenance verifier:** artisan evidence, provenance approval, and certificates

Every staff route enforces permissions on the server. Hiding a button is not authorization.

Staff authentication requires:

- Verified email
- Strong password stored with Argon2id
- Time-based one-time-password two-factor authentication
- Secure server-managed session
- Session rotation after login and privilege changes
- Rate-limited login and recovery
- Audited security-sensitive actions

## 12. International Selling, Tax, and Shipping

INR is the authoritative catalogue currency.

Before international payment activation:

- International visitors may browse.
- Optional converted display amounts are labelled estimates.
- Checkout offers only destinations and payment methods verified by the merchant.

After activation, each supported destination has:

- Enabled/disabled state
- Shipping methods and delivery estimate
- Weight, value, and free-shipping rules
- DDP or DDU duties statement
- Returns eligibility
- Required address fields

Every internationally available product includes country of origin, HS code, accurate weight, and customs-safe description.

Tax rules are stored as effective-dated configuration supplied and approved by the merchant’s tax professional. The system preserves the applied tax rule and amount in the order snapshot. It does not infer tax law from customer-facing copy.

## 13. Background Jobs

A PostgreSQL job table provides the first-release durable queue. Workers claim jobs transactionally using row locks with skip-locked semantics.

Job types:

- Transactional email
- Payment reconciliation
- Refund processing
- Payment and order recovery
- Reservation expiry
- Certificate and QR generation
- Image processing
- Privacy export and deletion
- Reconciliation reports

Jobs have:

- Stable idempotency key
- Payload version
- Attempt count
- Next-attempt timestamp
- Processing lease
- Completed or terminal-failure state
- Sanitized error summary

Transient failures use bounded exponential backoff with jitter. Terminal failures enter a staff review queue. A worker crash must not lose or permanently lock a job.

## 14. Security and Privacy

Controls include:

- Secure, HTTP-only, SameSite session cookies
- CSRF protection on every state-changing browser request
- Strict role checks on staff operations
- Argon2id password hashing
- TOTP two-factor authentication for staff
- Razorpay webhook signature validation before parsing
- Idempotent payment, webhook, email, and refund processing
- PostgreSQL transactions and row locks for inventory
- Rate limits on login, checkout, coupon, contact, access-link, and public certificate routes
- Content Security Policy compatible with Razorpay Standard Checkout
- Strict transport security and encrypted service connections
- Environment-managed secrets with documented rotation
- Separate public and private storage access
- Validated uploads with content-type, size, and image-processing limits
- Structured logs without tokens, private evidence, or full sensitive payloads
- Append-only security and commerce audit events
- Customer-data access, export, correction, retention, and deletion workflows
- Dependency, container, and database migration checks in continuous integration

Raw card, bank, wallet, or UPI credentials never enter FastAPI, PostgreSQL, logs, analytics, or object storage.

## 15. Failure Handling

- **Razorpay unavailable:** preserve the cart and reservation until its normal expiry; present retry or alternate manual-contact guidance without creating duplicate provider orders.
- **Browser callback missing:** webhook reconciliation still confirms a captured payment.
- **Webhook delayed:** order remains pending; reconciliation jobs query known payment attempts.
- **Payment captured after stock release:** attempt re-reservation; if unavailable, enter payment review and refund.
- **Email unavailable:** order remains valid; retry delivery and allow authorized staff resend.
- **Object storage unavailable:** commerce remains usable when existing image URLs are cached; uploads pause safely.
- **Worker unavailable:** jobs remain durable and resume after recovery.
- **Database unavailable:** fail closed on checkout and staff writes; do not show payment success without durable order state.
- **Invalid, unknown, or revoked certificate:** show an explicit, non-ambiguous public status.

Error messages explain recovery without exposing internal identifiers, existence of customer records, secrets, or stack traces.

## 16. Accessibility, Performance, and Search

Theme-controlled experiences target WCAG 2.2 AA.

Requirements:

- Semantic headings and landmarks
- Keyboard-operable navigation, filters, dialogs, galleries, cart, checkout, and staff workflows
- Visible focus indicators
- Accessible names and error associations
- Sufficient colour contrast
- Text alternatives for meaningful imagery
- Captions or transcripts for meaningful video
- Touch targets of at least 44 by 44 CSS pixels
- No interaction dependent only on hover, colour, or animation
- Reduced-motion support

Performance:

- Responsive image variants and modern formats
- Lazy loading below the first viewport
- Reserved image dimensions to prevent layout shift
- Minimal JavaScript and third-party code
- Server-rendered primary content
- Database indexes for catalogue, inventory, orders, tokens, jobs, and webhook idempotency
- Cache headers for immutable media and safe public content

Search optimization:

- Editable titles and descriptions
- Canonical URLs
- Product, article, breadcrumb, and organization structured data
- Descriptive image alternatives
- Logical collection and article links
- Social-sharing metadata
- Stable product, collection, artisan, article, and certificate URLs

## 17. Deployment and Operations

The first production deployment is single-region in India.

Required services:

- Container hosting for web, worker, and scheduler roles
- Managed PostgreSQL with encrypted connections
- S3-compatible object storage and CDN
- Transactional email provider
- Domain and TLS
- Error monitoring and structured log retention
- Automated encrypted backups with point-in-time recovery

Release process:

1. Build one immutable container image.
2. Run static checks, unit tests, integration tests, and security checks.
3. Back up the database according to the release policy.
4. Run Alembic migrations as a controlled release job.
5. Deploy web, worker, and scheduler from the same image.
6. Verify live and ready health checks.
7. Run production smoke tests without placing a real unapproved order.

The application exposes:

- `GET /health/live`
- `GET /health/ready`

Readiness requires database connectivity and required configuration. Optional provider degradation appears in operational status without falsely marking an otherwise safe browsing service ready for checkout.

## 18. Testing

### 18.1 Domain and unit tests

- Money and rounding
- Discounts and coupon eligibility
- Tax and shipping calculations
- Order state transitions
- Permission policies
- Token hashing, expiry, use, and revocation
- Certificate issue and revocation
- Job backoff and terminal-failure rules

### 18.2 PostgreSQL integration tests

- Inventory row locking and concurrent checkout
- Reservation creation, conversion, and expiry
- Unique webhook and idempotency constraints
- Order/payment/refund transactions
- Job claiming and worker-crash recovery
- Alembic migration from an empty database

### 18.3 Payment tests

- Correct Razorpay order amount and currency
- Valid and invalid browser signatures
- Valid, invalid, duplicated, delayed, and out-of-order webhooks
- Captured payment after reservation expiry
- Full and partial refund idempotency
- Reconciliation after missed webhook

### 18.4 Security and privacy tests

- Staff role boundaries
- TOTP enrollment, login, recovery, and replay resistance
- CSRF enforcement
- Session rotation and expiry
- Rate limits and generic order-link responses
- Public/private media separation
- Provenance evidence exclusion from public responses
- Customer export and deletion
- Log redaction

### 18.5 Storefront and accessibility tests

- Navigation, search, filters, sorting, pagination, and wishlist
- Product, cart, checkout, and order-access flows
- Empty, loading, unavailable, and failure states
- Keyboard-only use
- Screen-reader spot checks
- Reduced motion
- Responsive layouts
- Structured data
- Razorpay-unavailable and email-unavailable recovery

### 18.6 Operational tests

- Backup restoration
- Secret rotation
- Worker and scheduler restart
- Database failover behaviour
- Object-storage interruption
- Health-check accuracy
- Rollback of an application release compatible with the current schema

## 19. Launch Gates

The store cannot accept real payments until all of these are complete:

- Registered merchant details and required legal pages
- Razorpay KYC, live credentials, webhook secret, and international activation state
- Verified settlement bank account
- Domain, TLS, and sender-email authentication
- Approved tax configuration
- Tested domestic and international shipping rules
- Approved shipping, returns, privacy, and terms
- Real product photography
- Verified prices and inventory
- Verified artisan consent and provenance
- HS codes, origin, weights, and customs descriptions for international products
- Staff roles, TOTP, recovery, and least-privilege review
- Successful payment, failure, duplicate webhook, delayed webhook, refund, cancellation, fulfilment, and tracking tests
- Inventory race and late-payment tests
- Passwordless order-access and enumeration tests
- Customer export and deletion tests
- Backup restoration evidence
- Secret rotation evidence
- Production monitoring and alert routing
- Accessibility and responsive acceptance review
- No sample, placeholder, or fictional commerce/provenance data published for sale

## 20. Out of Scope for the First Release

- Shopify or another paid hosted commerce platform
- A separate React or Next.js storefront
- Native mobile applications
- Wholesale or B2B ordering
- Marketplace onboarding for third-party sellers
- Multi-vendor payouts
- Loyalty points
- Subscription products
- Augmented-reality try-on
- Custom recommendation engine
- General analytics warehouse
- Multiple payment gateways active at launch
- Multiple deployment regions
- Microservices, Kafka, or Redis
- Bespoke warehouse-management software

## 21. Success Criteria

The first release succeeds when:

- Customers can understand the differences between Assamese silk types.
- Every purchasable saree has clear, verified commerce and provenance information.
- Indian and enabled international customers can place and pay for real orders.
- Concurrent checkout cannot sell the same unique saree twice.
- Browser tampering cannot change trusted price, discount, tax, shipping, inventory, or payment state.
- Duplicate or delayed payment events do not duplicate orders, stock movements, emails, or refunds.
- Customers can access only their own order through short-lived passwordless links.
- Staff can manage catalogue, inventory, orders, fulfilment, returns, refunds, content, and provenance through role-appropriate workflows.
- Authenticity certificates are permanent, auditable, and publicly verifiable.
- Private artisan evidence never appears in public pages, APIs, logs, or public storage.
- The storefront is visually distinctive, accessible, responsive, and fast on mobile.
- The system can be restored from backup and recover durable jobs after process failure.
- No Shopify subscription or equivalent fixed commerce-platform subscription is required.
