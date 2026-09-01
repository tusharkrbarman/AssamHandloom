# Luit & Loom API

This is the first AWS-port slice: a FastAPI service with separate liveness and
PostgreSQL readiness probes. The existing Cloudflare Worker remains the current
storefront until feature routes are ported here.

Run it from the repository root after installing the service dependencies:

```powershell
python -m venv services/api/.venv
services/api/.venv/Scripts/python -m pip install -e "services/api[test]"
services/api/.venv/Scripts/uvicorn app.main:app --app-dir services/api --reload
```

Run the API checks with `services/api/.venv/Scripts/python.exe -m pytest
services/api/tests -q`.

`GET /health` is safe for a load balancer liveness check. `GET /ready` returns
503 until `DATABASE_URL` points at a reachable PostgreSQL database.

Apply the checked-in PostgreSQL migrations with:

```powershell
$env:DATABASE_URL = "postgresql://localhost/luit_and_loom"
services/api/.venv/Scripts/python.exe -m app.migrate
```

The first catalogue route is available at
`GET /api/v1/catalog/products` with the existing search, filter, sort, and
pagination parameters.

Commerce routes now cover the first guest-checkout slice:

- `POST /api/cart/quote` validates variants and returns current prices and availability.
- `POST /api/orders` creates a pending order and a 30-minute inventory reservation.
- `GET /api/orders/{order_id}?token=...` reads an order with its private token, or
  with the signed `exp` and `sig` query values from `orderLink`.

Set `COOKIE_SIGNING_KEY` to a random value of at least 32 characters before
creating orders. The service currently ships within India and uses zero-cost
shipping until a shipping policy is added.

Razorpay checkout uses `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and
`RAZORPAY_WEBHOOK_SECRET`:

- `POST /api/payments/session` creates or reuses a provider order for a pending order.
- `POST /api/payments/verify` verifies the checkout callback and settles stock.
- `POST /api/webhooks/razorpay` verifies provider events and settles captured payments.

For a live deployment, set all three Razorpay values as runtime secrets. Use
the test-key set while validating checkout; never commit them to the repo.
