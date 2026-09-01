# Luit & Loom — AWS

An Assamese silk saree store being migrated to an AWS-hosted Python stack.
This branch contains the FastAPI commerce API, PostgreSQL schema, guest
checkout, inventory reservations, passwordless order links, Razorpay
payment settlement, and the public storefront.

## Current AWS architecture

- FastAPI service in [`services/api`](services/api/README.md) serving the public storefront
- PostgreSQL for catalogue, orders, payments, and inventory
- Razorpay for payment sessions, callback verification, and webhooks
- Signed order links for passwordless guest access
- Legacy Worker retained only as rollback code

The Docker image, ECS service, and production AWS resources are still being
migrated.

## Run the API locally

You need Python 3.12 and a reachable PostgreSQL database:

```powershell
python -m venv services/api/.venv
services/api/.venv/Scripts/python.exe -m pip install -e "services/api[test]"
$env:DATABASE_URL = "postgresql://localhost/luit_and_loom"
$env:COOKIE_SIGNING_KEY = "replace-with-a-random-value-at-least-32-characters"
services/api/.venv/Scripts/python.exe -m app.migrate
services/api/.venv/Scripts/uvicorn app.main:app --app-dir services/api --reload
```

The migration runner applies the checked-in PostgreSQL migrations in order.
`GET /health` is the liveness probe; `GET /ready` checks database readiness.
The application strips query strings from Uvicorn access logs. Configure the
AWS edge, load balancer, and any upstream proxy to omit or redact query strings
as well, because order-link credentials are carried in the URL.

## Runtime secrets

Set these as deployment secrets, never in Git:

- `DATABASE_URL`
- `COOKIE_SIGNING_KEY` (at least 32 characters)
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`

Razorpay webhook URL:
`POST /api/webhooks/razorpay`

## API currently available

- `GET /api/v1/catalog/products` — catalogue search, filters, sorting, and pagination
- `POST /api/cart/quote` — server-side pricing and availability
- `POST /api/orders` — guest order creation with a 30-minute reservation
- `GET /api/orders/{order_id}` — token or signed-link order access
- `POST /api/payments/session` — create or reuse a Razorpay order
- `POST /api/payments/verify` — verify the browser payment callback
- `POST /api/webhooks/razorpay` — verify provider events and settle stock

## Verify the service

```powershell
services/api/.venv/Scripts/python.exe -m pytest services/api/tests -q
```

## AWS migration status

Implemented:

- FastAPI application and health/readiness probes
- PostgreSQL catalogue, order, reservation, payment, and adjustment migrations
- Guest checkout with server-side prices and stock locking
- Idempotent Razorpay capture handling and inventory deduction
- Signed, expiring passwordless order links
- Public storefront cutover to FastAPI
- GitHub CI checks for the API

Still pending:

- PostgreSQL catalogue seed/import
- Docker image and ECS deployment
- AWS networking, secrets, object storage, and observability
- Admin order management, email delivery, refunds, shipping, and tax rules
