# Luit & Loom — FastAPI Storefront Cutover

**Date:** 1 September 2026  
**Status:** Approved design awaiting written-spec review  
**Scope:** Public Quiet Commerce storefront and guest checkout  
**Source of truth:** Existing Worker storefront and browser assets

## 1. Goal

Move the public storefront from the legacy Worker runtime to FastAPI while
preserving the current Quiet Commerce experience: URLs, page structure, copy,
CSS classes, accessibility behavior, bag interactions, guest checkout, signed
order links, and Razorpay payment actions.

The browser should use one origin for pages, assets, and JSON APIs. The Worker
remains available as a rollback until the AWS storefront passes smoke checks;
it is not part of the new request path.

## 2. Scope

Included:

- Public catalogue pages and editorial pages
- Product detail pages and variant selection
- Local-storage bag and server-side cart quotes
- Guest checkout form and 30-minute reservations
- Passwordless order pages and signed order links
- Razorpay payment screen and callback flow
- Existing CSS, `bag.js`, and `pay.js`
- FastAPI route and rendering tests

Not included in this cutover:

- Owner admin pages or admin authentication
- Customer accounts
- Media upload or S3 integration
- Email delivery, refunds, shipping rules, or tax rules
- Docker, ECS, RDS, or other production infrastructure
- A new frontend framework or visual redesign

## 3. Decision

FastAPI will serve the pages with Jinja2 templates and Starlette static-file
mounts. The existing CSS and browser scripts remain the visual and interaction
source of truth. Existing Python catalogue, order, link, and payment services
remain the business-logic source of truth.

This keeps the cutover same-origin, so the current browser calls to
`/api/cart/quote`, `/api/payments/session`, and `/api/payments/verify` continue
to work without a CORS layer or a second frontend build.

## 4. Route Contract

### HTML routes

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/` | Quiet Commerce home page with featured products |
| GET | `/shop` | Catalogue listing with filters and pagination |
| GET | `/search` | Catalogue listing in search mode |
| GET | `/collections` | Published collection index |
| GET | `/collections/{slug}` | Published collection listing |
| GET | `/products/{slug}` | Product detail and variant choices |
| GET | `/artisans`, `/our-story`, `/journal` | Existing editorial pages |
| GET | `/pages/{page}` | Existing guidance pages |
| GET | `/cart` | Bag shell hydrated by `bag.js` |
| GET | `/checkout` | Checkout form and bag summary shell |
| POST | `/checkout` | Parse the existing form, create an order, redirect to its order page |
| GET | `/orders/{order_id}` | Order confirmation and payment action |

The existing JSON API paths and response shapes remain unchanged:

- `GET /api/v1/catalog/products`
- `POST /api/cart/quote`
- `POST /api/orders`
- `GET /api/orders/{order_id}`
- `POST /api/payments/session`
- `POST /api/payments/verify`
- `POST /api/webhooks/razorpay`

### Static assets

FastAPI mounts the checked-in `app/static/css` and `app/static/js` directories
at `/css` and `/js`. The HTML keeps the existing asset URLs, so no browser
script changes are required for the basic bag and payment flows.

Product media uses the existing textile placeholder in this phase unless a
known local media URL is available. No `/media` or S3 dependency is added here;
public S3-backed media is a separate follow-up.

## 5. Components and Boundaries

### Web rendering module

Create `services/api/app/web.py` for public route handlers and template
context assembly. It may call catalogue and order service functions, but it
does not execute SQL or recalculate prices.

Create a small template set under `services/api/templates/`:

- `base.html` — document shell, header, footer, canonical link, asset tags
- `home.html` — hero, trust strip, featured weaves, material and artisan sections
- `catalogue.html` — filters, product grid, pagination
- `product.html` — gallery, variant form, specifications, related products
- `commerce.html` — bag, checkout, and order page shells
- `editorial.html` — static story and guidance pages

Templates preserve the existing class names and accessible labels. Shared
markup belongs in `base.html` and small includes only where it removes real
duplication.

### Catalogue service

Extend `services/api/app/catalogue.py` with the read operations needed by the
HTML routes: a product detail lookup, published collection lookup, and the
existing list query. These functions return plain dictionaries matching the
template context and must apply the same publication and archive filters as
the JSON endpoint.

### Commerce adapter

The HTML checkout route is a thin adapter over `orders.create_order`. It parses
the existing form field names, calls the service with the same validation and
reservation rules, and redirects to `/orders/{order_id}?token=...`. The JSON
order endpoint remains available for future clients.

Install only the form parser required by FastAPI (`python-multipart`) and the
template engine (`jinja2`). No SPA framework, API client library, or ORM is
needed.

## 6. Request Flow

```text
Browser
  | GET /shop, /products/*, /checkout, /orders/*
  v
FastAPI web routes
  | read-only catalogue/order service calls
  v
PostgreSQL

Browser -- bag.js --> POST /api/cart/quote --> PostgreSQL
Browser -- checkout form --> POST /checkout --> create_order --> redirect
Browser -- pay.js --> payment session/verify --> Razorpay + PostgreSQL
```

The server is authoritative for prices, publication state, stock, order
tokens, reservation expiry, and payment state. The browser only stores variant
IDs and quantities in local storage.

## 7. Error Handling

- Browser routes render the existing branded HTML error shell for 404 and 500.
- JSON routes retain their current structured error responses.
- Checkout validation errors re-render the form with safe submitted values and
  the existing inline alert style.
- Missing or invalid order tokens and signatures return the same not-found
  response as the current storefront.
- Static asset misses return 404 without exposing filesystem paths.
- Unexpected failures receive a request ID in logs and a generic public message.

No secrets, full tokens, payment signatures, or submitted address payloads are
written to logs.

## 8. Verification

Add FastAPI tests covering:

- Home, listing, search, collection, product, and editorial route status/body
- Published versus draft catalogue visibility
- Existing CSS and JavaScript asset URLs
- Cart and checkout HTML shells
- Checkout form redirect and validation error rendering
- Signed order-link acceptance and tamper rejection
- Payment controls appearing only when Razorpay settings are present
- Existing JSON API tests continuing to pass

Run the service checks with:

```powershell
services/api/.venv/Scripts/python.exe -m pytest services/api/tests -q
```

The cutover is ready for deployment when the tests pass and a local browser
smoke check confirms the home page, product page, bag, checkout, order page,
and payment button retain the current design and interactions.

## 9. Rollout and Cleanup

1. Run the FastAPI service against the seeded PostgreSQL catalogue.
2. Verify every included route locally and through the AWS service endpoint.
3. Point the AWS public origin at FastAPI and keep the Worker available for
   rollback during the smoke-check window.
4. Remove the Worker storefront only after the AWS origin serves the same
   public paths successfully.

The legacy Worker code, D1 migrations, and Wrangler toolchain are deliberately
left untouched during this cutover so rollback remains possible. They become a
separate cleanup task after the frontend is proven on AWS.

## 10. Acceptance Criteria

- The AWS origin serves the same public URLs as the current storefront.
- The Quiet Commerce visual layout, copy, classes, and accessibility hooks are
  unchanged.
- Catalogue pages read published data from PostgreSQL.
- The existing bag script can quote items and remove lines.
- The checkout form creates the same pending order and reservation behavior.
- Passwordless order links and Razorpay payment actions still work.
- No admin, account, media-upload, or infrastructure scope is pulled into this
  phase.
- FastAPI tests pass in CI using the AWS-only workflow.
