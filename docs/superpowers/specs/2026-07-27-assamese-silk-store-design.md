# Luit & Loom — Assamese Silk Store Design

**Date:** 27 July 2026  
**Status:** Revised design approved in conversation; awaiting written-spec review

## 1. Purpose

Luit & Loom will be a production ecommerce store dedicated exclusively to authentic Assamese silk sarees. It will serve customers in India and international markets while presenting each saree as a traceable work of craft rather than a generic fashion product.

The first release must combine:

- A distinctive premium-contemporary brand
- An artistic, accessible, mobile-first shopping experience
- Real payments, inventory, orders, fulfilment, and customer accounts
- Detailed artisan and product provenance
- Public authenticity certificates and QR-based verification
- A FastAPI and PostgreSQL companion service for verified provenance
- International-market, shipping, tax, and customs readiness
- Shopify-backed commerce operations that store staff can manage without code

## 2. Chosen Approach

The store will use a bespoke Shopify Online Store 2.0 theme with a focused FastAPI and PostgreSQL companion service.

Shopify will own checkout, customer records, product and inventory data, discounts, orders, refunds, fulfilment, Markets, and commerce reporting. The custom theme will own presentation, discovery, storytelling, and conversion-focused interactions.

FastAPI will own verified artisan identities, private verification evidence, saree provenance records, public authenticity certificates, QR verification destinations, Shopify webhook processing history, and the audit trail for verified provenance changes. It will not duplicate or replace Shopify commerce.

This approach was selected over:

- A headless Shopify storefront, which provides more front-end freedom but introduces unnecessary operational and maintenance complexity for the first release.
- A customized marketplace theme, which launches faster but is less capable of expressing a distinctive Assamese craft identity.
- A broad custom Python commerce backend, which would duplicate secure Shopify capabilities and create inventory, payment, and order-synchronization risk.

## 3. Brand System

### 3.1 Brand name

**Luit & Loom**

“Luit” refers to the Brahmaputra in Assam, while “Loom” expresses the making process at the centre of the brand.

### 3.2 Tagline

**Woven by Assam. Worn with meaning.**

### 3.3 Positioning

Luit & Loom is a premium-contemporary saree house: authentic Assamese heritage presented with modern refinement. It should feel elevated and collectible without becoming distant, ornate, or inaccessible.

### 3.4 Visual language

Core palette:

- Muga gold
- Warm ivory
- Deep lac red
- Betel-leaf green
- Charcoal

The visual system will pair an elegant high-contrast serif with a restrained modern sans-serif. Layouts will use generous negative space, disciplined alignment, strong typographic hierarchy, and editorial pacing.

Assamese textile geometry may appear sparingly in borders, dividers, packaging motifs, and interaction details. It must not become a dense decorative background. The overall expression should avoid generic gold gradients, crowded festival graphics, ornamental excess, and visual clichés.

Photography will emphasize natural light, full drapes, close-up weave textures, borders, pallus, blouse pieces, and honest artisan portraits.

### 3.5 Voice

The brand voice will be poetic in editorial storytelling and precise in commerce. Product facts such as silk type, dimensions, weight, colour, blouse-piece details, origin, care, dispatch, returns, and authenticity must remain easy to scan.

## 4. Information Architecture

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

- Market selector
- Search
- Customer account
- Wishlist
- Cart

Footer content:

- Contact
- FAQ
- Silk Guide
- Care Guide
- Shipping
- Returns
- Order Tracking
- Privacy
- Terms
- Newsletter
- Social channels

### 4.2 Homepage

The homepage will present the following sequence:

1. Cinematic brand hero with “Shop the Collection” and “Meet the Artisans”
2. Featured sarees curated by silk type
3. Concise “Why Assam silk” introduction
4. Muga, Pat, and Eri collection cards
5. Featured artisan and weaving process
6. Craft, provenance, and authenticity guarantees
7. Occasion-led recommendations
8. Shipping, returns, and care assurances
9. Editorial newsletter invitation

Homepage sections must be reorderable and editable through Shopify’s theme editor.

### 4.3 Collection pages

Collection pages will support:

- Filters for silk type, colour, occasion, price, weave, and availability
- Sorting by featured, newest, price, and best-selling
- A second detail image on hover-capable devices
- Product card details for silk type, price, artisan attribution, and low-stock status
- Clear no-results and filter-reset states

### 4.4 Product pages

Each product page will include:

- A gallery covering full drape, border, pallu, weave detail, and blouse-piece views
- Product title, price, inventory, dispatch estimate, and purchase controls
- Silk type, dimensions, weight, colour, blouse-piece details, and care
- Artisan profile, village or weaving region, production time, and motif meaning
- Authenticity statement and unique product identifier
- Shipping, duties, returns, and fall/pico service information
- Related sarees chosen by craft, palette, or occasion

Artisan provenance will be a first-class content block, not a secondary marketing paragraph.

### 4.5 Supporting content

The first release will include:

- Our Story
- Artisans directory and artisan profiles
- Silk Guide
- Care Guide
- Journal index and articles
- Contact
- FAQ
- Shipping policy
- Returns policy
- Privacy policy
- Terms
- Order tracking

## 5. Inaugural Collection

The launch collection is titled **River, Reed & Gold** and contains 12 editorial sample products:

- Four Muga silk statement sarees
- Four Pat silk occasion sarees
- Two Eri silk understated sarees
- Two contemporary silk-blend sarees at an accessible entry price

Each sample product will have:

- A distinct name and colour story
- Silk and weave classification
- Motif meaning
- Artisan profile
- Dimensions, weight, blouse-piece details, and care
- Realistic INR pricing
- Inventory and dispatch state
- Shipping and returns information

The initial journal will contain three articles:

1. Understanding the silks of Assam
2. How to identify authentic Muga silk
3. How to care for a handwoven silk saree

Development may use art-directed placeholder imagery and clearly labelled sample data. Before real orders are enabled, every product image, price, stock value, artisan identity, location, and provenance claim must be replaced or verified against the actual saree and weaver. Generated imagery must never be presented as documentary evidence or actual sale inventory.

## 6. Commerce Architecture

### 6.1 Shopify responsibilities

Shopify will manage:

- Products, variants, collections, and metafields
- Inventory and availability
- Customer accounts
- Discounts and gift cards
- Checkout and payments
- Orders, cancellations, refunds, and exchanges
- Fulfilment and tracking
- Markets and localized catalogues
- Taxes and customs data
- Analytics and reporting

The theme will not collect, transmit, or store raw card data.

FastAPI will not calculate prices, reserve or change inventory, process payments, create a separate checkout, issue Shopify refunds, or become the system of record for Shopify orders.

### 6.2 Product data model

Standard Shopify product data will cover title, description, media, price, compare-at price, SKU, barcode, weight, inventory, and variants.

Product metafields will cover:

- Silk type
- Weave technique
- Dominant colour
- Occasion
- Dimensions
- Blouse-piece inclusion and dimensions
- Saree weight
- Motif name and meaning
- Artisan reference
- Weaving region
- Production time
- Authenticity identifier
- Care instructions
- Dispatch window
- Fall/pico availability
- Country of origin
- Harmonized System code

Artisans will be projected into structured Shopify metaobjects so one approved public profile can be reused across multiple products and rendered in product pages and the artisans directory. FastAPI remains authoritative for artisan verification status, consent evidence, provenance approval, and certificate issuance. Only approved public fields are copied to Shopify.

### 6.3 Source-of-truth boundaries

| Data | Authoritative system | Other-system use |
| --- | --- | --- |
| Products, variants, prices, and collections | Shopify | FastAPI stores Shopify identifiers only when linking provenance |
| Inventory and availability | Shopify | FastAPI does not calculate or change inventory |
| Customers, checkout, payments, and orders | Shopify | FastAPI stores the minimum Shopify order reference needed for certificate workflows |
| Public artisan display profile | FastAPI after verification | Approved fields are projected to a Shopify metaobject |
| Private artisan identity and consent evidence | FastAPI | Never copied to Shopify storefront data |
| Saree provenance and verification state | FastAPI | Approved public facts are projected to Shopify metafields or requested by the theme |
| Authenticity certificate and revocation state | FastAPI | Shopify may link to the public verification URL |
| Webhook delivery and processing state | FastAPI | Shopify remains the event source |

Updates must flow in one direction wherever possible. A verified FastAPI record may publish approved display fields to Shopify, but changes in Shopify must not silently overwrite verified identity, evidence, certificate, or audit data.

## 7. FastAPI Companion Service

### 7.1 Responsibilities

The companion service will provide:

- Verified artisan identity and consent records
- Saree provenance records linked to Shopify products and variants
- Permanent authenticity certificate numbers
- Public certificate-verification responses and QR destinations
- Shopify webhook verification, deduplication, persistence, processing, and replay
- Links between Shopify products or orders and approved provenance
- Append-only audit events for verified-record changes

The first release will not include custom recommendations, a general analytics warehouse, a separate commerce admin, or a headless storefront gateway.

### 7.2 Data model

PostgreSQL will contain focused records:

- **Artisan:** public name, region, biography, craft speciality, portrait reference, verification state, and timestamps.
- **Artisan evidence:** private consent and verification evidence, reviewer reference, verification result, and timestamps.
- **Provenance:** Shopify product and optional variant reference, artisan reference, silk type, weaving region, motif, production dates, verification state, and timestamps.
- **Certificate:** permanent certificate number, public lookup slug, provenance reference, QR destination, issue state, issued time, optional Shopify order reference, and revocation reason.
- **Shopify event:** Shopify event ID, topic, shop identity, payload hash, processing state, attempt count, received time, and processing timestamps.
- **Audit event:** actor, action, record type, record identifier, before/after change summary, and timestamp.

Verified provenance and certificate history will not be silently deleted or rewritten. Corrections create auditable changes. Certificates can be revoked with a public explanation that does not expose private evidence.

### 7.3 API surface

Initial public endpoints:

- `GET /api/v1/certificates/{code}` returns the public authenticity status and approved provenance.
- `GET /api/v1/products/{shopify_product_id}/provenance` returns public provenance for the Shopify storefront.
- `GET /health/live` reports that the process is running.
- `GET /health/ready` reports whether required dependencies are ready.

Private administrative endpoints create, review, verify, revoke, and audit artisan, provenance, and certificate records. They require staff authentication through an OpenID Connect provider and role-based authorization. The first release exposes the protected API but does not build a separate custom admin dashboard.

Public responses will not expose personal contact information, identity documents, consent evidence, internal notes, webhook payloads, or staff audit details.

### 7.4 Shopify webhooks

Shopify sends signed webhooks for the selected product, order, refund, cancellation, and deletion events. FastAPI must validate the Shopify HMAC signature against the untouched raw request body before parsing or storing the payload.

For each valid event:

1. Record the Shopify event ID, topic, shop, and payload hash.
2. Acknowledge a duplicate event without processing it twice.
3. Persist the event and return promptly.
4. Let a separate worker claim and process the record.
5. Retry transient failures with bounded backoff.
6. Preserve permanently failed events for authorized investigation and replay.

Customer-data access, redaction, and shop-deletion webhooks required by the installed Shopify application must be handled within Shopify’s required time windows.

### 7.5 Runtime architecture

The service will use:

- FastAPI for HTTP APIs
- SQLAlchemy 2 for database access
- PostgreSQL for application state and the durable worker queue
- Alembic for versioned database migrations
- Pydantic settings for validated configuration
- Provider-neutral OpenID Connect token validation for staff access

One Docker image will run in two roles:

- **Web:** APIs, health endpoints, and webhook receipt
- **Worker:** webhook processing, retries, certificate operations, and public-data projection

The worker will claim queued database records transactionally so multiple workers do not process the same event. Redis is intentionally omitted from the first release.

Migrations run as an explicit release step, not automatically from every web instance. Production uses managed PostgreSQL with encrypted transport, least-privilege credentials, automated backups, and tested restoration.

### 7.6 Security and failure behaviour

Security controls:

- Secrets exist only in environment-managed secret storage.
- Every external connection uses encrypted transport.
- PostgreSQL roles have only the privileges required by each runtime role.
- Webhook HMAC validation precedes payload parsing or persistence.
- Staff endpoints validate issuer, audience, signature, expiry, and role claims.
- Request-size limits, rate limits, and strict input validation protect public endpoints.
- Logs exclude tokens, raw evidence, unnecessary personal data, and full webhook payloads.
- Verified-record changes produce append-only audit events.
- Raw payment-card data never enters FastAPI.

If FastAPI is slow or unavailable, Shopify browsing, cart, checkout, payments, and order management continue working. The theme displays a neutral “Provenance details temporarily unavailable” state and does not block purchase.

### 6.3 Inventory

Inventory will be tracked at the product or variant level. Unique sarees will use a quantity of one and automatically become unavailable after purchase. The interface will provide explicit in-stock, low-stock, sold-out, and made-to-order states.

A final availability check will occur through Shopify during cart and checkout operations. If an item becomes unavailable, the customer will receive a clear explanation and links to related alternatives.

### 6.4 Cart and checkout

The cart will support:

- Quantity updates where applicable
- Item removal
- Order notes
- Market-aware shipping messages
- Estimated dispatch context
- Gift options if enabled
- Clear duties messaging for international customers

Checkout will remain Shopify-hosted to preserve security, compatibility, and payment reliability.

## 8. Payments and International Markets

### 7.1 Store currency

The Shopify store currency will be INR. India is the primary market.

### 7.2 Payment approach

An eligible Shopify-supported Indian payment provider will be selected during merchant onboarding. The target payment mix is:

- Indian cards
- UPI
- Net banking
- Wallets where supported
- Optional cash on delivery with risk controls
- International cards
- PayPal where merchant and customer eligibility permit

Payment-provider availability and supported settlement behaviour must be confirmed inside the merchant’s live Shopify account before launch. Because Shopify Payments is not currently available to India-based businesses, the launch plan must account for third-party gateway fees and the possibility that international checkout is charged in the store’s default currency.

### 7.3 Markets

The initial Shopify Markets structure will be:

- India
- North America
- United Kingdom
- Europe
- Rest of World

Each market may define product availability, pricing adjustments, shipping options, delivery estimates, duties messaging, and return conditions.

### 7.4 Customs and duties

Every internationally available product must include:

- Country of origin
- Harmonized System code
- Accurate product weight
- Customs-safe product description

The store will clearly state whether shipments are Delivered Duty Paid or Delivered Duty Unpaid for each supported destination. Duty estimates must not be described as guaranteed unless the selected checkout and carrier arrangement supports guaranteed landed costs.

## 9. Order and Fulfilment Operations

The order lifecycle will include:

1. Payment authorization or confirmation
2. Inventory reservation
3. Merchant review for fraud or address concerns
4. Packing and quality check
5. Fulfilment and tracking assignment
6. Shipping notification
7. Delivery
8. Return, exchange, or refund handling where applicable

Customer notifications will use the Luit & Loom visual identity and voice for order confirmation, shipping, delivery, cancellation, return, and refund events.

The admin workflow must let staff identify one-of-a-kind products, made-to-order products, fall/pico requests, international orders, and orders requiring customs documentation.

## 10. Interaction and Error States

The theme will provide clear states for:

- Loading
- Empty cart
- Empty wishlist
- No search or filter results
- Invalid or unavailable variant
- Low stock
- Sold out
- Cart quantity adjustment after stock change
- Checkout handoff failure
- Payment failure returned by Shopify
- Network failure
- Provenance service unavailable
- Invalid, unknown, or revoked certificate
- Invalid newsletter or account input

Errors must explain what happened, preserve customer input where possible, and offer a direct recovery action.

Motion will be restrained, purposeful, and disabled or reduced when the visitor requests reduced motion.

## 11. Accessibility

The target is WCAG 2.2 AA for theme-controlled experiences.

Requirements include:

- Semantic headings and landmarks
- Keyboard-operable navigation, filters, dialogs, galleries, and cart controls
- Visible focus indicators
- Accessible names and error associations
- Sufficient colour contrast
- Text alternatives for meaningful imagery
- Captions or transcripts for meaningful video
- Touch targets suitable for mobile use
- No interaction that depends only on hover, colour, or animation
- Reduced-motion support

## 12. Performance and Search

The theme will prioritize:

- Responsive image sizes and modern formats provided through Shopify
- Lazy loading below the first viewport
- Minimal blocking scripts
- Limited third-party applications
- Stable layouts during image and font loading
- Fast mobile interaction

Search optimization will include:

- Editable titles and descriptions
- Canonical URLs
- Product, article, breadcrumb, and organization structured data
- Descriptive image alternatives
- Logical collection and article linking
- Market-aware URLs where configured
- Social-sharing metadata

## 13. Analytics and Consent

Analytics will cover:

- Product views
- Search
- Filter use
- Wishlist additions
- Add to cart
- Cart updates
- Checkout initiation
- Completed orders

Marketing and analytics integrations must respect the visitor’s consent choices and the requirements of the active market.

## 14. Testing and Acceptance

The release will be tested across current major mobile and desktop browsers.

Functional coverage will include:

- Navigation and search
- Collection filters and sorting
- Product media and information
- Product options and availability
- Cart add, update, and remove
- Checkout handoff
- Customer accounts
- Wishlist
- Market selection
- Inventory transitions
- Order notifications
- Error and empty states
- Public certificate verification and revocation
- Shopify webhook signature validation and duplicate-event handling
- Theme fallback when FastAPI is slow or unavailable

Quality coverage will include:

- Keyboard-only use
- Screen-reader spot checks
- Contrast and accessible names
- Reduced motion
- Responsive layouts
- Image loading and layout stability
- Structured data validation
- Policy and trust-link review

Backend coverage will include:

- FastAPI route and domain unit tests
- Integration tests against real PostgreSQL
- Valid, invalid, replayed, and out-of-order Shopify webhooks
- Idempotent duplicate-event handling
- Certificate issuance, lookup, correction, and revocation
- Public/private data separation
- Staff issuer, audience, signature, expiry, and role authorization
- Worker claims, retries, bounded backoff, permanent failure, and replay
- Alembic migration from an empty database
- Backup restoration
- Secret rotation
- Health-check and dependency-failure behaviour

## 15. Launch Gates

The store cannot accept real orders until all of the following are complete:

- Shopify merchant and business verification
- Approved payment gateway and verified payout account
- Final domain configuration
- Accurate tax settings
- Tested domestic and international shipping rates
- Verified returns and cancellation policies
- HS codes, origin, weights, and customs descriptions for international products
- Real and verified product photography
- Verified artisan identities and provenance claims
- Accurate prices and live inventory
- Test transactions for successful payment, failed payment, refund, cancellation, and fulfilment
- Working transactional email and order tracking
- Privacy, terms, shipping, and returns review
- Deployed FastAPI web and worker services
- Managed PostgreSQL backups and successful restoration evidence
- Shopify webhook signing secret configured and signature tests passing
- Staff OpenID Connect issuer, audience, and roles configured
- Verified public/private field separation
- Certificate QR lookup, revocation, and unavailable-service states tested
- Shopify-required customer-data deletion handling tested

## 16. Out of Scope for the First Release

The following are intentionally deferred:

- A custom-built commerce admin
- A separate provenance administration dashboard
- A headless storefront or FastAPI commerce gateway
- Custom product recommendations
- A general analytics warehouse
- Native mobile applications
- Wholesale or B2B ordering
- Marketplace onboarding for third-party sellers
- Loyalty points
- Subscription products
- Augmented-reality try-on
- Multi-vendor payouts
- Bespoke warehouse software

These features may be evaluated after the core store has real customer and operational data.

## 17. Success Criteria

The first release succeeds when:

- Customers can confidently understand the differences between Assamese silk types.
- Every purchasable saree has clear provenance and commerce information.
- Indian and supported international customers can complete a real order.
- Stock updates reliably prevent the same unique saree from being sold twice.
- Store staff can manage products, approved public artisan profiles, inventory, orders, and fulfilment through Shopify.
- Authorized provenance staff can verify artisans, evidence, provenance, and certificates through the protected FastAPI interface.
- Verified sarees can be linked to permanent public authenticity certificates.
- Invalid, unknown, and revoked certificates produce unambiguous public results.
- Shopify webhook retries do not create duplicate provenance or certificate actions.
- Private artisan verification evidence never appears in public APIs or Shopify storefront data.
- Shopify shopping and checkout remain usable when FastAPI is unavailable.
- The experience is visually distinctive, accessible, responsive, and fast enough for mobile shoppers.
- No placeholder product, artisan, policy, or operational claim remains when real orders are enabled.
