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

The service exposes `/health` for liveness and `/ready` for PostgreSQL
readiness. Razorpay checkout remains disabled until all three Razorpay runtime
secrets are set.
