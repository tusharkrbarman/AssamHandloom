# Luit & Loom API

The AWS branch runs a FastAPI service backed by PostgreSQL. Setup, runtime
secrets, endpoints, the browser storefront smoke check, and the migration
status are documented in the root [AWS README](../../README.md).

Service-specific commands:

```powershell
services/api/.venv/Scripts/python.exe -m app.migrate
services/api/.venv/Scripts/python.exe -m pytest services/api/tests -q
services/api/.venv/Scripts/uvicorn app.main:app --app-dir services/api --reload
```

For a browser smoke check, open the FastAPI app directly with:

```powershell
services/api/.venv/Scripts/uvicorn app.main:app --app-dir services/api --reload
```

Then check `/`, `/shop`, `/products/{slug}`, `/cart`, `/checkout`, and a
signed `/orders/{id}` URL. This request path is served by FastAPI directly;
it does not use Wrangler.

To send queued order emails through Resend, configure `RESEND_API_KEY` and
`MAIL_FROM`, then run the one-shot worker from this directory:

```powershell
.venv/Scripts/python.exe -m app.email_worker
```

The worker sends queued confirmation, payment, shipment, cancellation, and
refund messages with retry/backoff. It exits after one batch so a scheduler
can run it repeatedly.

The owner dashboard is available at `/admin/setup` (first run), `/admin/login`,
`/admin/orders`, and `/admin/inventory`. It uses the signed `luit_admin` cookie,
same-origin CSRF checks, and the `ADMIN_SETUP_TOKEN` / `ADMIN_RECOVERY_TOKEN`
runtime secrets. Apply migrations before opening the dashboard.

The service exposes `/health` for liveness and `/ready` for PostgreSQL
readiness. Razorpay checkout remains disabled until all three Razorpay runtime
secrets are set.
