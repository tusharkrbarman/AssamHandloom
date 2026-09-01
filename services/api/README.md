# Luit & Loom API

The AWS branch runs a FastAPI service backed by PostgreSQL. Setup, runtime
secrets, endpoints, and the migration status are documented in the root
[AWS README](../../README.md).

Service-specific commands:

```powershell
services/api/.venv/Scripts/python.exe -m app.migrate
services/api/.venv/Scripts/python.exe -m pytest services/api/tests -q
services/api/.venv/Scripts/uvicorn app.main:app --app-dir services/api --reload
```

The service exposes `/health` for liveness and `/ready` for PostgreSQL
readiness. Razorpay checkout remains disabled until all three Razorpay runtime
secrets are set.
